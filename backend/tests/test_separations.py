import copy
import hashlib
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal as D
from types import SimpleNamespace

import pytest

from aperture.domain import Bar, Portfolio, ResearchError
from aperture.ledger import apply_actions, reinvest_research_income
from aperture.research_data import security_events
from aperture import separations as subject
from test_dated_research import vendor  # noqa: F401


def bar(symbol, day, opening, close=None, split="1"):
    opening, close = D(opening), D(close or opening)
    return Bar(
        symbol,
        day,
        opening,
        max(opening, close),
        min(opening, close),
        close,
        1000,
        split=D(split),
    )


@pytest.fixture
def evidence(monkeypatch):
    raw = b"Independent dated primary separation fixture"
    for proof in (subject.ARCONIC, subject.DOW, subject.CORTEVA, subject.INCEPTION):
        monkeypatch.setitem(proof, "sha256", hashlib.sha256(raw).hexdigest())
    return SimpleNamespace(document=lambda url: raw)


def identities(*symbols):
    return {
        s: {
            "candidate_ids": [subject.LISTINGS[s]],
            "asof": {"ARNC": "2020-04-03", "DWDP": "2019-05-31"}.get(s, "2026-11-09"),
        }
        for s in symbols
    }


def native(*wanted):
    result = []
    for identifier in wanted:
        symbol, day, kind, ratio = subject.PROXIES[identifier]
        result.append(
            dict(
                id=identifier,
                symbol=symbol,
                ex_date=day,
                process_date=day,
                kind=kind,
                new_rate=ratio,
                old_rate="1",
            )
        )
    return result


def arconic():
    day = date(2020, 4, 1)
    prefix = {
        day - timedelta(days=d): bar("ARNC", day - timedelta(days=d), "16.06")
        for d in (1, 2, 5, 6, 7, 8, 9, 12)
    }
    rows = {
        "ARNC": {**prefix, day: bar("ARNC", day, "15", "6.92", ".25")},
        "HWM": {day: bar("HWM", day, "15.4", "13.2")},
    }
    observed = copy.deepcopy(rows)
    events = [
        dict(
            id="5382e441-ecf1-4bcd-8d03-8a93e2ce3a29",
            kind="cash_mergers",
            source="ARNC",
            effective="2023-08-21",
            cash="30",
            ratio="0",
            target=None,
            source_record={"acquiree_cusip": "03966V107"},
        )
    ]
    return rows, observed, events


def run_arconic(rows, observed, events, api, ids=None, natives=None):
    income, issues = {}, []
    events, receipts = subject.apply(
        rows,
        ids or identities("ARNC", "HWM"),
        natives
        if natives is not None
        else native("ba1fd3b3-0526-4aab-aefe-40a9901f2a67"),
        events,
        income,
        date(2016, 1, 4),
        date(2026, 11, 9),
        api,
        lambda *a: issues.append(a),
        lambda *a: observed,
    )
    return events, receipts, income, issues


def test_arconic_retains_howmet_parent_and_values_child_without_a_reverse_split(
    evidence,
):
    rows, observed, events = arconic()
    events, receipts, income, issues = run_arconic(rows, observed, events, evidence)
    day = date(2020, 4, 1)
    assert rows["ARNC"][day].split == 1 and rows["ARNC"][day].close == D("13.2")
    assert rows["ARNC"][day].research_distribution == D("1.73")
    assert rows["HWM"][day].research_distribution == D("1.73")
    assert income[str(day)] == {"HWM": "3.75", "ARNC": "3.75"}
    assert rows["HWM"][date(2020, 3, 31)] == replace(
        observed["ARNC"][date(2020, 3, 31)], symbol="HWM"
    )
    assert all(i[3] == "cash_payment" for i in issues)
    portfolio = Portfolio(D(0), {"ARNC": D(4)})
    apply_actions(
        portfolio, day, {"ARNC": rows["ARNC"][day]}, "ex_date", {"ARNC": D("3.75")}
    )
    assert portfolio.positions == {"ARNC": D(4)}
    assert portfolio.research_income == [("ARNC", D("6.92"))]
    assert portfolio.value({"ARNC": D("15.4")}) == D("76.6")
    reinvest_research_income(portfolio, day, {"ARNC": rows["ARNC"][day]})
    assert portfolio.value({"ARNC": D("13.2")}) == D("59.72")
    held = dict(portfolio.positions)
    security_events(portfolio, date(2023, 8, 21), events, {}, "ex_date")
    assert portfolio.positions == held
    rejection = next(e for e in events if e["id"].startswith("5382"))
    assert rejection["kind"] == "rejected_native_merger"
    assert rejection["source_record"]["acquiree_cusip"] == "03966V107"
    assert receipts["ARNC"]["continuation"] == "HWM"


def test_arconic_update_is_idempotent_and_preserves_later_parent_dividends(evidence):
    rows, observed, events = arconic()
    later = date(2020, 6, 1)
    rows["HWM"][later] = replace(bar("HWM", later, "20"), research_dividend=D(".02"))
    events, _, income, _ = run_arconic(rows, observed, events, evidence)
    before = copy.deepcopy(rows)
    again, _, income2, _ = run_arconic(rows, observed, events, evidence)
    assert rows == before and again == events and income2 == income
    assert rows["ARNC"][later].research_dividend == D(".02")


@pytest.mark.parametrize(
    "mutation",
    ["listing", "vintage", "source", "quote", "prefix", "native", "later_merger"],
)
def test_changed_arconic_cohort_cannot_inherit_repair(evidence, mutation):
    rows, observed, events = arconic()
    ids = identities("ARNC", "HWM")
    natives = native("ba1fd3b3-0526-4aab-aefe-40a9901f2a67")
    if mutation == "listing":
        ids["HWM"]["candidate_ids"] = ["unrelated equity"]
    if mutation == "vintage":
        ids["ARNC"]["asof"] = "2023-08-17"
    if mutation == "source":
        evidence.document = lambda url: b"Changed terms"
    if mutation == "quote":
        rows["HWM"][date(2020, 4, 1)] = bar("HWM", date(2020, 4, 1), "19")
    if mutation == "prefix":
        rows["ARNC"].pop(date(2020, 3, 31))
    if mutation == "native":
        natives[0]["new_rate"] = ".5"
    if mutation == "later_merger":
        events[0]["cash"] = "31"
    with pytest.raises(ResearchError):
        run_arconic(rows, observed, events, evidence, ids, natives)


def dupont():
    apr, jun = date(2019, 4, 2), date(2019, 6, 3)
    rows = {
        s: {
            date(2016, 1, 4): bar(s, date(2016, 1, 4), "65"),
            date(2017, 9, 1): bar(s, date(2017, 9, 1), "67.18"),
            apr: bar(s, apr, "36.52", "36.49", "1.487" if s == "DWDP" else "1"),
            jun: bar(s, jun, "65.67", "76.1", ".4725" if s == "DD" else "1"),
        }
        for s in ("DWDP", "DD")
    }
    rows["DOW"] = {apr: bar("DOW", apr, "55.12", "56.25")}
    rows["CTVA"] = {jun: bar("CTVA", jun, "26.54", "24.81")}
    rows["DD.OLD"] = {date(2016, 1, 4): bar("DD.OLD", date(2016, 1, 4), "67")}
    observed = copy.deepcopy(rows)
    # The old DWDP vintage supplies post-rename DD quotes, not the DD ticker.
    observed["DD"] = {day: bar("DD", day, "83.93") for day in (apr, jun)}
    return rows, observed


def run_dupont(rows, observed, api):
    income, issues = {}, []
    events, _ = subject.apply(
        rows,
        identities("DWDP", "DD", "DOW", "CTVA"),
        native(
            "646911b1-d521-4e71-8729-04dfde18632b",
            "b4fcc1fc-5210-458d-9e9e-c08b52cd9b7b",
        ),
        [],
        income,
        date(2016, 1, 4),
        date(2026, 11, 9),
        api,
        lambda *a: issues.append(a),
        lambda *a: observed,
    )
    return events, income, issues


def test_dow_distribution_is_not_a_fictitious_parent_share_issuance(evidence):
    rows, observed = dupont()
    events, income, _ = run_dupont(rows, observed, evidence)
    apr = date(2019, 4, 2)
    for symbol in ("DWDP", "DD"):
        assert date(2016, 1, 4) not in rows[symbol]
        assert rows[symbol][apr].split == 1
        portfolio = Portfolio(D(0), {symbol: D(3)})
        apply_actions(
            portfolio,
            apr,
            {symbol: rows[symbol][apr]},
            "ex_date",
            {symbol: D(income[str(apr)][symbol])},
        )
        assert portfolio.positions[symbol] == 3
        assert abs(portfolio.research_income[0][1] - D("56.25")) < D("1e-24")
        reinvest_research_income(portfolio, apr, {symbol: rows[symbol][apr]})
        assert abs(
            portfolio.value({symbol: D("36.49")}) - (D(3) * D("36.49") + D("56.25"))
        ) < D("1e-20")
    assert rows["DD.OLD"] == observed["DD.OLD"]
    assert any(e.get("lifetime_start") == "2017-09-01" for e in events)


def test_corteva_and_reverse_split_keep_pre_and_post_split_share_units_distinct(
    evidence,
):
    rows, observed = dupont()
    events, income, _ = run_dupont(rows, observed, evidence)
    day = date(2019, 6, 3)
    for symbol in ("DWDP", "DD"):
        row = rows[symbol][day]
        assert row.split == D(1) / 3 and row.research_distribution == D("24.81")
        assert D(income[str(day)][symbol]) == D("26.54")
        portfolio = Portfolio(D(0), {symbol: D(3)})
        apply_actions(portfolio, day, {symbol: row}, "ex_date", {symbol: D("26.54")})
        assert abs(portfolio.positions[symbol] - 1) < D("1e-24")
        assert abs(portfolio.research_income[0][1] - D("24.81")) < D("1e-24")
        reinvest_research_income(portfolio, day, {symbol: row})
        assert abs(portfolio.value({symbol: D("76.1")}) - D("100.91")) < D("1e-20")
    before = copy.deepcopy(rows)
    again, income2, _ = run_dupont(rows, observed, evidence)
    assert rows == before and again == events and income == income2


def test_unknown_native_separation_instruction_blocks_override(evidence):
    rows, observed = dupont()
    wrong = native("646911b1-d521-4e71-8729-04dfde18632b")
    wrong[0]["id"] = "new instruction"
    with pytest.raises(ResearchError, match="unreviewed native"):
        subject.apply(
            rows,
            identities("DWDP", "DD", "DOW", "CTVA"),
            wrong,
            [],
            {},
            date(2016, 1, 4),
            date(2026, 11, 9),
            evidence,
            lambda *a: None,
            lambda *a: observed,
        )


def test_reviewed_repair_runs_after_frozen_blocks_are_assembled(vendor, monkeypatch):  # noqa: F811
    from aperture.research_data import download
    from test_dated_research import payload

    store, api, state = vendor
    old = store.dataset(download(store, payload(), lambda *a: None, api)["id"])
    first = old.bars["ABC"][0]
    state["latest"] = date(2017, 2, 10)
    real = subject.apply
    seen = []

    def repair(bars, ids, native, events, income, begin, end, api, issue, quotes):
        seen.append(bars["ABC"][first.session])
        bars["ABC"][first.session] = replace(
            first, high=first.high + 1, close=first.close + 1
        )
        return real(bars, ids, native, events, income, begin, end, api, issue, quotes)

    monkeypatch.setattr(subject, "apply", repair)
    new = store.dataset(
        download(
            store, {**payload(), "end": "2017-02-10"}, lambda *a: None, api, base=old
        )["id"]
    )
    assert seen == [first]
    assert new.bars["ABC"][0].close == first.close + 1
    assert store.dataset(old.id).bars["ABC"][0] == first
