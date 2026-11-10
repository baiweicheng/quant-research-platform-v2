from dataclasses import replace
from datetime import date
from types import SimpleNamespace

from aperture.eps_policy import assess, WARNING
from aperture.fundamentals import normalize, attach
from aperture.store import Store
from test_fundamentals import source, CIK, ACC, dataset  # noqa: F401


def normalized(company=None, cik=CIK, symbol="ABC"):
    company = company or source()
    checks = assess(symbol, cik, company, "2022-01-01", "2024-12-31")
    return normalize(symbol, cik, company, {"entityType": "operating"}, checks)[0]


def test_lightweight_assumption_preserves_basic_values_and_is_not_class_verified():
    check = assess("ABC", CIK, source(), "2022-01-01", "2024-12-31")[ACC]
    assert check["compatible"] and not check["class_verified"]
    assert check["reason"] == WARNING
    row = normalized()[0]
    assert row.eps == 4 and row.assets == 200 and row.gross_profit == 40
    assert row.sources["eps_policy"] == "structured-eps-v1"
    assert "share_class_evidence" not in row.sources


def test_berkshire_never_receives_guessed_class_scaling_even_under_an_alias():
    company = source()
    company["facts"]["us-gaap"]["EarningsPerShareDiluted"]["units"]["USD/shares"][0][
        "val"
    ] = 62000
    for symbol in ["BRK.B", "BRK.A", "HISTORICAL-ALIAS"]:
        row = normalized(company, "0001067983", symbol)[0]
        assert row.eps is None and not row.eps_compatible
        assert row.gross_profit == 40
        assert any("Berkshire" in issue for issue in row.issues)


def test_lightweight_eps_keeps_conflict_currency_period_and_availability_guards():
    company = source()
    facts = company["facts"]["us-gaap"]["EarningsPerShareDiluted"]["units"][
        "USD/shares"
    ]
    facts.append({**facts[0], "val": 4000})
    row = normalized(company)[0]
    assert row.eps is None and any("Conflicting" in s for s in row.issues)
    company = source()
    units = company["facts"]["us-gaap"]["EarningsPerShareDiluted"]["units"]
    units["EUR/shares"] = units.pop("USD/shares")
    assert normalized(company)[0].eps is None
    company = source()
    company["facts"]["us-gaap"]["EarningsPerShareDiluted"]["units"]["USD/shares"][0][
        "start"
    ] = "2022-10-01"
    assert normalized(company)[0].eps is None
    row = normalized()[0]
    assert row.available_at.date() == date(2023, 2, 13)
    assert not assess("ABC", CIK, source(), "2024-01-01", "2024-12-31")


def _with_eps_elements(**values):
    company = source()
    gaap = company["facts"]["us-gaap"]
    template = gaap.pop("EarningsPerShareDiluted")["units"]["USD/shares"][0]
    for tag, value in values.items():
        gaap[tag] = {"units": {"USD/shares": [{**template, "val": value}]}}
    return company


def test_continuing_operations_eps_is_used_only_without_a_net_element():
    tag = "IncomeLossFromContinuingOperationsPerDilutedShare"
    row = normalized(_with_eps_elements(**{tag: 3}))[0]
    assert row.eps == 3 and row.eps_compatible and row.sources["eps"] == tag
    # A whole-entity net element in the same accession/period takes precedence.
    row = normalized(_with_eps_elements(**{tag: 3, "EarningsPerShareDiluted": 2}))[0]
    assert row.eps == 2 and row.sources["eps"] == "EarningsPerShareDiluted"
    row = normalized(
        _with_eps_elements(**{tag: 3, "EarningsPerShareBasicAndDiluted": 2.5})
    )[0]
    assert row.eps == 2.5 and row.sources["eps"] == "EarningsPerShareBasicAndDiluted"
    # Conflicting values in the selected element are not replaced by a later one.
    company = _with_eps_elements(**{tag: 3})
    facts = company["facts"]["us-gaap"][tag]["units"]["USD/shares"]
    facts.append({**facts[0], "val": 7})
    assert normalized(company)[0].eps is None


def test_eps_above_the_share_price_is_rejected_as_a_scale_error(dataset):  # noqa: F811
    from aperture.fundamentals import IMPLAUSIBLE_EPS, inputs

    decision = date(2023, 8, 31)
    scaled = replace(
        dataset,
        fundamentals={
            "ABC": tuple(
                replace(row, eps=row.eps * 1_000_000)
                for row in dataset.fundamentals["ABC"]
            )
        },
    )
    values, reason = inputs(scaled, "ABC", decision)
    assert reason is None and "earnings_yield" not in values
    assert values["valuation_issue"] == IMPLAUSIBLE_EPS
    values, _ = inputs(dataset, "ABC", decision)
    assert values["eps_asof"] == 4 and values["earnings_yield"] > 0
    # A loss larger than the share price is a valid (negative) input.
    loss = replace(
        dataset,
        fundamentals={
            "ABC": tuple(
                replace(row, eps=-row.eps * 100) for row in dataset.fundamentals["ABC"]
            )
        },
    )
    values, _ = inputs(loss, "ABC", decision)
    assert values["eps_asof"] == -400 and values["earnings_yield"] < 0


def test_attach_never_downloads_full_filings_and_does_not_count_assumptions_as_verified(
    tmp_path,
    dataset,  # noqa: F811
):
    store = Store(tmp_path / "lite.sqlite3")
    original = replace(dataset, fundamentals={})
    saved = store.save_dataset(original, b"Fixture", [])

    def get(provider, url, **kw):
        if url.endswith("company_tickers_exchange.json"):
            return {"fields": ["cik", "ticker"], "data": [[1, "ABC"]]}
        if "/submissions/" in url:
            return {"cik": 1, "entityType": "operating", "tickers": ["ABC", "ABC.B"]}
        return source()

    def document(url):
        raise AssertionError(
            "Full report download is forbidden in the lightweight path"
        )

    result = attach(
        store,
        saved["id"],
        lambda *a: None,
        SimpleNamespace(get=get, document=document, observations=[]),
    )
    meta = result["metadata"]["fundamentals"]
    assert meta["eps_policy"] == "structured-eps-v1"
    row = meta["coverage"][0]
    assert row["eps_checks"] == row["eps_accepted"] == 1
    assert "share_class_verified" not in row
    assert store.dataset(result["id"]).fundamentals["ABC"][0].eps == 4


def test_current_research_review_discloses_assumption_without_paper_activation(
    tmp_path,
    monkeypatch,
    dataset,  # noqa: F811
):
    from aperture.worker import process_one

    store = Store(tmp_path / "review.sqlite3")
    ds = replace(
        dataset,
        metadata={
            "fundamentals": {"eps_policy": "structured-eps-v1", "share_basis": WARNING}
        },
    )
    saved = store.save_dataset(ds, b"Fixture", [])
    monkeypatch.setattr("aperture.calendar.latest_complete", lambda: date(2024, 8, 30))
    store.enqueue("review", {"dataset_id": saved["id"], "strategy_id": "quality_value"})
    assert process_one(store)
    results = store.results("review")
    assert len(results) == 1
    review = store.result(results[0]["id"])
    assert WARNING in review["notes"] and review["status"] == "research_only"
    with store.connect() as db:
        for table in ["paper_orders", "paper_plans", "paper_approvals"]:
            assert db.execute("SELECT count(*) FROM " + table).fetchone()[0] == 0
