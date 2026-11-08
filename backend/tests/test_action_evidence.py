from copy import deepcopy
from datetime import date
from decimal import Decimal as D
from types import SimpleNamespace

import pytest

from aperture.action_evidence import CONTINUATIONS, continuation
from aperture.domain import Portfolio
from aperture.research_data import security_events, input_issues


def event_for(identifier):
    proof = CONTINUATIONS[identifier]
    return dict(
        id=identifier,
        kind="stock_mergers",
        acquiree_symbol=proof["symbol"],
        acquiree_cusip=proof["old_cusip"],
        acquirer_cusip=proof["new_cusip"],
        acquirer_symbol="",
        acquiree_rate=1,
        acquirer_rate=1,
        effective_date=proof["effective"],
    )


@pytest.mark.parametrize("identifier", list(CONTINUATIONS))
def test_only_exact_reviewed_security_exchange_has_no_economic_share_change(identifier):
    raw = event_for(identifier)
    proof = continuation(raw)
    assert proof and proof["url"].startswith("https://")
    p = Portfolio(D(123), {proof["symbol"]: D("12.345678")})
    original = deepcopy(p)
    event = dict(
        kind="identity_continuations",
        source=proof["symbol"],
        target=proof["symbol"],
        ratio="1",
        cash="0",
        effective=proof["effective"],
        reviewed_evidence=proof,
        source_record=raw,
    )
    security_events(p, date.fromisoformat(proof["effective"]), [event], {}, "ex_date")
    assert p == original
    original_event = {**event, "kind": "stock_mergers", "target": ""}
    assert input_issues(
        SimpleNamespace(metadata={"corporate_actions": [original_event]})
    )
    assert not input_issues(SimpleNamespace(metadata={"corporate_actions": [event]}))


@pytest.mark.parametrize(
    "field,value",
    [
        ("id", "unknown"),
        ("kind", "cash_mergers"),
        ("acquiree_symbol", "OTHER"),
        ("effective_date", "2023-01-01"),
        ("acquiree_cusip", "wrong"),
        ("acquirer_cusip", "wrong"),
        ("acquirer_rate", "1.149"),
        ("acquiree_rate", 2),
        ("acquirer_symbol", "OTHER"),
        ("cash_rate", 1),
    ],
)
def test_changed_or_unreviewed_provider_terms_remain_unresolved(field, value):
    raw = event_for(next(iter(CONTINUATIONS)))
    assert continuation({**raw, field: value}) is None


def test_reviewed_source_body_must_match_its_published_fingerprint(monkeypatch):
    import hashlib
    from types import SimpleNamespace
    from aperture.action_evidence import verified_continuation
    from aperture.domain import ResearchError

    key = next(iter(CONTINUATIONS))
    raw = b"Captured primary filing fixture"
    monkeypatch.setitem(CONTINUATIONS[key], "sha256", hashlib.sha256(raw).hexdigest())
    assert verified_continuation(
        event_for(key), SimpleNamespace(document=lambda url: raw)
    )
    with pytest.raises(ResearchError, match="fingerprint changed"):
        verified_continuation(
            event_for(key), SimpleNamespace(document=lambda url: b"changed")
        )


@pytest.mark.parametrize(
    "case",
    [
        "valid",
        "already_supplied",
        "contradictory",
        "adjusted_prices",
        "wrong_identity",
        "missing_check",
        "changed_source",
    ],
)
def test_missing_split_requires_exact_identity_primary_evidence_and_price_units(
    monkeypatch, case
):
    import hashlib
    from aperture.action_evidence import MISSING_SPLITS, supplement_splits
    from aperture.domain import Bar, ResearchError
    from aperture.ledger import apply_actions

    raw = b"Primary split fixture"
    proof = MISSING_SPLITS["CP"]
    monkeypatch.setitem(proof, "sha256", hashlib.sha256(raw).hexdigest())
    before, day = date(2021, 5, 13), date(2021, 5, 14)

    def b(day, price, split=1):
        return Bar("CP", day, *([D(price)] * 4), 1000, split=D(split))

    rows = {
        before: b(before, 80 if case == "adjusted_prices" else 400),
        day: b(
            day,
            80,
            5 if case == "already_supplied" else 10 if case == "contradictory" else 1,
        ),
    }
    checks = {before: b(before, 80), day: b(day, 80)}
    identities = {
        "CP": {
            "candidate_ids": [
                "wrong" if case == "wrong_identity" else proof["listing_id"]
            ]
        }
    }
    if case == "missing_check":
        checks.pop(day)
    calls = []

    def document(url):
        calls.append(url)
        return b"changed" if case == "changed_source" else raw

    if case == "changed_source":
        with pytest.raises(ResearchError, match="fingerprint changed"):
            supplement_splits(
                {"CP": rows},
                {"CP": checks},
                identities,
                SimpleNamespace(document=document),
            )
        assert rows[day].split == 1
        return
    corrections = supplement_splits(
        {"CP": rows}, {"CP": checks}, identities, SimpleNamespace(document=document)
    )
    if case != "valid":
        assert not corrections and not calls
        return
    assert len(corrections) == 1 and len(calls) == 1 and rows[day].split == 5
    portfolio = Portfolio(D(0), {"CP": D(10)})
    apply_actions(portfolio, day, {"CP": rows[day]}, "ex_date")
    assert portfolio.positions == {"CP": D(50)}
    assert portfolio.value({"CP": D(80)}) == D(4000)
