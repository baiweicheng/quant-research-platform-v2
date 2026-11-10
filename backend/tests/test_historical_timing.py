import copy
import hashlib
from dataclasses import replace
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from aperture.domain import Bar, ResearchError
from aperture.historical_timing import TIMING, apply_timing, verified_nontrading_tail
from aperture.lifecycles import terminal_events
from test_lifecycles import dataset


def sample(symbol, monkeypatch):
    proof = TIMING[symbol]
    raw = b"Primary completed-transaction and suspension fixture"
    monkeypatch.setitem(proof, "sha256", hashlib.sha256(raw).hexdigest())
    if proof.get("terms_source"):
        monkeypatch.setitem(
            proof["terms_source"], "sha256", hashlib.sha256(raw).hexdigest()
        )
    event = dict(
        id=proof["event_id"],
        source=symbol,
        kind=proof["kind"],
        effective=proof["legal_effective"],
        target=proof["target"],
        cash=proof["cash"],
        ratio=proof["ratio"],
        pay_date=None,
        source_record=dict(
            acquiree_cusip=proof["cusip"],
            acquirer_cusip=proof.get("target_cusip"),
            effective_date=proof["legal_effective"],
        ),
    )
    last = date.fromisoformat(proof["last_trading"])
    rows = {last: Bar(symbol, last, *([Decimal(90)] * 4), 1000)}
    if "zero_volume_mark" in proof:
        day = date.fromisoformat(proof["zero_volume_mark"])
        rows[day] = Bar(symbol, day, *([Decimal(90)] * 4), 0)
    identities = {symbol: {"candidate_ids": [proof["listing_id"]]}}
    api = SimpleNamespace(document=lambda url: raw)
    return event, identities, {symbol: rows}, api


@pytest.mark.parametrize("symbol", list(TIMING))
def test_reviewed_market_date_preserves_native_terms_and_source(monkeypatch, symbol):
    event, ids, bars, api = sample(symbol, monkeypatch)
    issues = []
    before = copy.deepcopy(event)
    fixed = apply_timing([event], ids, bars, api, lambda *v: issues.append(v))[0]
    assert not issues and event == before
    assert fixed["effective"] == TIMING[symbol]["effective"]
    assert fixed["legal_effective"] == before["effective"]
    for key in ("cash", "ratio", "target", "source_record", "pay_date"):
        assert fixed[key] == before[key]
    assert fixed["reviewed_market_timing"]["url"] == TIMING[symbol]["url"]
    ds = replace(
        dataset(),
        bars={symbol: tuple(bars[symbol].values())},
        metadata={"input_issues": [], "corporate_actions": [fixed]},
    )
    assert symbol in terminal_events(ds)
    # Rechecking a previously corrected immutable input is idempotent.
    assert apply_timing([fixed], ids, bars, api, lambda *v: issues.append(v)) == [fixed]


@pytest.mark.parametrize(
    "mutation", ["listing", "cash", "recipient", "quote", "source", "alternative"]
)
def test_changed_inputs_cannot_inherit_reviewed_timing(monkeypatch, mutation):
    event, ids, bars, api = sample("AGN", monkeypatch)
    issues = []
    events = [event]
    if mutation == "listing":
        ids["AGN"]["candidate_ids"] = ["unrelated"]
    elif mutation == "cash":
        event["cash"] = "121"
    elif mutation == "recipient":
        event["source_record"]["acquirer_cusip"] = "unrelated"
    elif mutation == "quote":
        bars["AGN"][date(2020, 5, 11)] = Bar(
            "AGN", date(2020, 5, 11), *([Decimal(90)] * 4), 1000
        )
    elif mutation == "source":
        api.document = lambda url: b"Changed source"
    elif mutation == "alternative":
        events.append({**event, "id": "alternative", "cash": "125"})
    if mutation == "source":
        with pytest.raises(ResearchError, match="fingerprint changed"):
            apply_timing(events, ids, bars, api, lambda *v: issues.append(v))
    else:
        result = apply_timing(events, ids, bars, api, lambda *v: issues.append(v))
        assert (
            issues
            and result[0]["effective"] == "2020-05-08"
            and "reviewed_market_timing" not in result[0]
        )


def test_halted_flat_zero_volume_mark_is_not_a_generic_last_quote_rule(monkeypatch):
    event, ids, bars, api = sample("ATVI", monkeypatch)
    fixed = apply_timing([event], ids, bars, api, lambda *v: None)[0]
    rows = list(bars["ATVI"].values())
    assert verified_nontrading_tail(fixed, rows)
    assert not verified_nontrading_tail(event, rows)
    assert not verified_nontrading_tail(fixed, [rows[0], replace(rows[1], volume=1)])
    assert not verified_nontrading_tail(
        fixed, [rows[0], replace(rows[1], high=Decimal(91))]
    )
    assert not verified_nontrading_tail(
        fixed, [*rows, replace(rows[-1], session=date(2023, 10, 16))]
    )
