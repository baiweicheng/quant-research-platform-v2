from datetime import date

import httpx
import pytest

from aperture.config import DATA_URL, Settings, settings
from aperture.domain import ResearchError
from aperture.providers import Provider, download_market, validate_symbols
from aperture.store import Store


@pytest.fixture
def market(tmp_path, monkeypatch):
    monkeypatch.setattr("aperture.providers.time.sleep", lambda _: None)
    store = Store(tmp_path / "data.sqlite")
    events = {
        "forward_splits": [
            {
                "id": "split-1",
                "symbol": "ABC",
                "ex_date": "2024-05-08",
                "process_date": "2024-05-08",
                "old_rate": 1,
                "new_rate": 2,
            }
        ],
        "cash_dividends": [
            {
                "id": "div-1",
                "symbol": "ABC",
                "ex_date": "2024-05-09",
                "process_date": "2024-05-15",
                "payable_date": "2024-05-15",
                "rate": 0.5,
                "foreign": False,
                "special": False,
            }
        ],
    }
    calls = []

    def handler(request):
        calls.append(request)
        if "/assets/" in request.url.path:
            symbol = request.url.path.rsplit("/", 1)[-1]
            return httpx.Response(
                200,
                json={
                    "id": symbol + "-stable-id",
                    "symbol": symbol,
                    "class": "us_equity",
                    "exchange": "NASDAQ",
                    "status": "active",
                    "name": symbol + " Common Stock",
                    "tradable": True,
                    "fractionable": True,
                },
            )
        if request.url.path.endswith("corporate-actions"):
            return httpx.Response(
                200, json={"corporate_actions": events, "next_page_token": None}
            )
        adjusted = request.url.params.get("adjustment") == "split"
        body = {}
        for symbol in ("ABC", "SPY"):
            rows = []
            for day, price in zip(
                range(6, 11),
                [100, 100, 50, 49.5, 49.5] if symbol == "ABC" else [100] * 5,
            ):
                if adjusted and symbol == "ABC" and day < 8:
                    price /= 2
                rows.append(
                    {
                        "t": f"2024-05-{day:02}T04:00:00Z",
                        "o": price,
                        "h": price,
                        "l": price,
                        "c": price,
                        "v": 10000,
                    }
                )
            body[symbol] = rows
        return httpx.Response(200, json={"bars": body, "next_page_token": None})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = Provider(
        store,
        client,
        Settings("example-key", "example-secret", "Aperture qa@example.com"),
    )
    yield store, provider, events, calls
    client.close()


def request():
    return {
        "name": "Test stocks",
        "universe": "custom",
        "symbols": ["ABC", "SPY"],
        "start": "2024-05-06",
        "end": "2024-05-10",
    }


def test_real_contract_splits_paydates_provenance_and_idempotence(market):
    store, provider, events, calls = market
    saved = download_market(store, request(), lambda *args: None, provider)
    dataset = store.dataset(saved["id"])
    assert dataset.bars["ABC"][2].split == 2
    assert dataset.bars["ABC"][3].dividend == 0.5
    assert dataset.bars["ABC"][3].pay_date == date(2024, 5, 15)
    assert saved["metadata"]["coverage"][0]["missing_count"] == 0
    assert saved["metadata"]["securities"][0]["id"] == "ABC-stable-id"
    assert saved["metadata"]["observation_ids"]
    count = len(calls)
    assert download_market(store, request(), lambda *args: None, provider)[
        "already_imported"
    ]
    assert len(calls) == count  # bounded local cache; no repeated downloads
    with store.connect() as db:
        assert not any(
            "example-secret" in r[0] or "example-key" in r[0]
            for r in db.execute("SELECT resource FROM observations")
        )


@pytest.mark.parametrize(
    "change, match",
    [
        ("missing_split", "Split/action disagreement"),
        ("wrong_split", "Split/action disagreement"),
        ("no_pay_date", "lacks a pay date"),
        ("spin_off", "unsupported spin offs"),
        ("currency", "requiring separate accounting"),
    ],
)
def test_actions_never_silently_disappear(market, change, match):
    store, provider, events, calls = market
    if change == "missing_split":
        events.pop("forward_splits")
    if change == "wrong_split":
        events["forward_splits"][0]["new_rate"] = 3
    if change == "no_pay_date":
        events["cash_dividends"][0].pop("payable_date")
    if change == "spin_off":
        events["spin_offs"] = [
            {"id": "spin", "source_symbol": "ABC", "ex_date": "2024-05-08"}
        ]
    if change == "currency":
        events["cash_dividends"][0]["currency"] = "EUR"
    with pytest.raises(ResearchError, match=match):
        download_market(store, request(), lambda *args: None, provider)
    assert store.datasets() == []


def test_repeated_page_token_is_a_failure_not_partial_success(market):
    store, provider, _, _ = market
    provider.get = lambda *args, **kwargs: {"bars": {}, "next_page_token": "same"}
    with pytest.raises(ResearchError, match="repeated"):
        provider.pages("/v2/stocks/bars", {}, "bars")


def test_provider_errors_are_redacted_and_retried(tmp_path, monkeypatch):
    monkeypatch.setattr("aperture.providers.time.sleep", lambda _: None)
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(
            429, json={"message": "example-secret must not be displayed"}
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        provider = Provider(
            Store(tmp_path / "a.sqlite"), client, Settings("key", "secret")
        )
        with pytest.raises(ResearchError, match="rate limit") as error:
            provider.get("alpaca", DATA_URL + "/v2/stocks/bars")
        assert "example-secret" not in str(error.value)
        assert len(calls) == 3
        with pytest.raises(ResearchError, match="approved"):
            provider.get("alpaca", "https://example.com/steal")


def test_credentials_are_local_and_redacted(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text(
        "ALPACA_API_KEY=example-key\nALPACA_SECRET_KEY=example-secret\nSEC_USER_AGENT=Aperture qa@example.com\n"
    )
    monkeypatch.setenv("APERTURE_ENV_FILE", str(env))
    cfg = settings()
    assert cfg.configured
    assert "example-key" not in repr(cfg) and "example-secret" not in repr(cfg)
    monkeypatch.setenv("ALPACA_API_KEY", "override")
    assert settings().key == "override"


def test_symbol_validation_never_silently_truncates():
    assert validate_symbols([" aapl", "AAPL", "XYZ"]) == ["AAPL", "XYZ", "SPY"]
    with pytest.raises(ResearchError):
        validate_symbols(["../secret"])
    with pytest.raises(ResearchError):
        validate_symbols([f"S{i}" for i in range(1500)])


def test_cent_rounded_adjusted_prices_do_not_create_false_splits(market):
    store, provider, events, calls = market
    events.clear()
    original = provider.get

    def rounded(provider_name, url, params=None, **kwargs):
        body = original(provider_name, url, params, **kwargs)
        if url.endswith("/bars"):
            prices = (
                [30.12, 29.29, 27.60, 28.18, 27.25]
                if params.get("adjustment") == "split"
                else [301.21, 292.90, 276.04, 281.78, 272.47]
            )
            for row, price in zip(body["bars"]["ABC"], prices):
                for key in ("o", "h", "l", "c"):
                    row[key] = price
        return body

    provider.get = rounded
    saved = download_market(store, request(), lambda *args: None, provider)
    assert all(bar.split == 1 for bar in store.dataset(saved["id"]).bars["ABC"])


def test_api_configuration_is_redacted_and_download_payloads_have_no_keys(
    tmp_path, monkeypatch
):
    from fastapi.testclient import TestClient
    from aperture.api import create_app

    env = tmp_path / "config.env"
    monkeypatch.setenv("APERTURE_ENV_FILE", str(env))
    with TestClient(create_app(tmp_path / "app.sqlite", None)) as client:
        assert not client.get("/api/providers").json()["alpaca_configured"]
        assert (
            client.post(
                "/api/providers/check", json={}, headers={"X-Aperture-Client": "1"}
            ).status_code
            == 422
        )
        env.write_text(
            "ALPACA_API_KEY=example-key\nALPACA_SECRET_KEY=example-secret\nSEC_USER_AGENT=Test test@example.com\n"
        )
        info = client.get("/api/providers")
        assert info.json()["alpaca_configured"]
        assert "example-secret" not in info.text and "example-key" not in info.text
        job = client.post(
            "/api/downloads", json=request(), headers={"X-Aperture-Client": "1"}
        )
        assert job.status_code == 202
        assert "example-secret" not in job.text and "example-key" not in job.text
        assert "SPY" in client.get("/api/providers").json()["watchlist"]["symbols"]
