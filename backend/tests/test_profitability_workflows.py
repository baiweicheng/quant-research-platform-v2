"""Prepare uses corrected filing inputs without approving or sending orders."""

import json
from datetime import date
from decimal import Decimal as D
from pathlib import Path

from aperture import calendar
from aperture.domain import Bar, Dataset
from aperture.fundamentals import attach
from aperture.paper import plan, prepare, reconcile, save_configuration
from aperture.store import Store
from test_paper import FakeBroker

FIXTURES = Path(__file__).parent / "fixtures" / "profitability"


def test_readonly_paper_prepare_acquires_corrected_profitability(tmp_path, monkeypatch):
    # Exercise the historical acquisition pipeline independently of recipe availability.
    monkeypatch.setattr("aperture.domain.ARCHIVED_STRATEGIES", frozenset())
    decision = date(2017, 3, 1)
    monkeypatch.setattr(calendar, "latest_complete", lambda *args, **kwargs: decision)
    store = Store(tmp_path / "prepare.sqlite3")
    bars = {
        sym: tuple(
            Bar(
                sym, d, *([D(100)] * 4), 100000, available_at=calendar.available_time(d)
            )
            for d in calendar.sessions(date(2016, 1, 4), decision)
        )
        for sym in ("TMO", "CNC", "SPY")
    }
    ds = Dataset(
        "prices",
        "Captured price fixture",
        "imported",
        1,
        bars,
        {"TMO": "Health Care", "CNC": "Health Care"},
        "Deterministic test prices",
        "fixture-prices",
        {"provider": "alpaca"},
    )
    store.save_dataset(ds, b"price fixture", [])
    companies = {
        sym: json.loads((FIXTURES / f"{sym}.json").read_text())["company"]
        for sym in ("TMO", "CNC")
    }

    class Captured:
        def __init__(self):
            self.observations = []

        def get(self, provider, url, **kwargs):
            if "tickers_exchange" in url:
                return {
                    "fields": ["cik", "ticker"],
                    "data": [[97745, "TMO"], [1071739, "CNC"]],
                }
            cik = int(url.split("CIK")[-1].split(".")[0])
            sym = "TMO" if cik == 97745 else "CNC"
            if "submissions" in url:
                return {"cik": cik, "entityType": "operating", "tickers": [sym]}
            return companies[sym]

        def document(self, url):
            if url.endswith("FilingSummary.xml"):
                return b"<FilingSummary><MyReports><Report><MenuCategory>Statements</MenuCategory><ShortName>Consolidated Statements of Operations</ShortName><Position>2</Position><HtmlFileName>R2.htm</HtmlFileName></Report></MyReports></FilingSummary>"
            sym = "TMO" if "/97745/" in url else "CNC"
            return (FIXTURES / f"{sym}-income.htm").read_bytes()

    monkeypatch.setattr(
        "aperture.bundles.download",
        lambda s, payload, progress: attach(s, ds.id, progress, Captured()),
    )
    broker = FakeBroker()
    broker.at = calendar.available_time(decision)
    cfg = save_configuration(
        store,
        {
            "strategy_id": "quality",
            "mode": "manual",
            "symbols": ["TMO", "CNC"],
            "data_start": "2016-01-04",
            "positions": 25,
            "max_weight": ".05",
            "sector_cap": ".25",
            "cash_reserve": ".02",
            "max_drift": ".03",
        },
    )
    reconcile(store, broker)
    result = prepare(
        store, {"payload": {"config_hash": cfg["hash"]}}, lambda *args: None, broker
    )
    frozen = plan(store, result["plan_id"])
    assert [s["symbol"] for s in frozen["signals"]] == ["TMO"]
    assert D(frozen["signals"][0]["components"]["profitability"]) == D(8369100000) / D(
        45907500000
    )
    assert any(x["symbol"] == "CNC" for x in frozen["excluded"])
    assert frozen["factor_coverage"]["factors"]["profitability"] == {
        "positive": 1,
        "nonpositive": 0,
        "unavailable": 1,
    }
    assert not broker.submissions
    assert not store.preference("paper_approval")
