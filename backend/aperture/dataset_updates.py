"""Incremental acquisition, immutable research vintages and explicit lineage."""

import hashlib
import json
from dataclasses import replace
from datetime import date, timedelta

from . import calendar, membership
from .domain import ResearchError
from .providers import Provider, download_market
from .store import now

OVERLAP_DAYS = 10
NOTE = "Incremental update: existing symbols refresh the last 10 calendar days plus new sessions; new symbols receive full backfill. Earlier prices/actions stay frozen. Use a full download to revalidate older history."


def update(store, identifier, progress, provider=None):
    requested = next((d for d in store.datasets() if d["id"] == identifier), None)
    if requested is None:
        raise ResearchError("That dataset was not found. Choose one from Data.")
    base = store.dataset(
        requested.get("metadata", {}).get("price_dataset_id", identifier)
    )
    if base.metadata.get("normalizer_version") == "dated-research-inputs-v1":
        from .bundles import download

        audit = base.metadata.get("membership")
        if audit:
            progress(2, "Refreshing membership before the incremental update")
            membership.refresh_all(store)
        return download(
            store,
            {
                "name": base.name,
                "universe": "sp500" if audit else "custom",
                "symbols": audit.get("additional_symbols", [])
                if audit
                else base.metadata.get("custom_symbols", list(base.bars)),
                "start": base.metadata["download"]["start"],
                "end": str(calendar.latest_complete()),
            },
            progress,
            provider,
            base=base,
            refresh=True,
        )
    if base.kind == "synthetic" or base.metadata.get("provider") != "alpaca":
        raise ResearchError(
            "Update dataset supports downloaded Alpaca snapshots. Import a new CSV for other sources."
        )
    latest = calendar.latest_complete()
    start = date.fromisoformat(base.metadata["download"]["start"])
    old_end = max(b.session for rows in base.bars.values() for b in rows)
    if latest < old_end:
        raise ResearchError(
            "The saved dataset is ahead of the latest completed session; check the clock."
        )
    audit = base.metadata.get("membership")
    mode = "sp500" if audit else "custom"
    extras = audit.get("additional_symbols", []) if audit else sorted(base.bars)
    progress(2, "Refreshing membership evidence and planning the incremental update")
    if audit:
        membership.refresh_all(store)
    names, new_audit, sectors = membership.resolve(
        store, {"universe": mode, "symbols": extras}, start, latest
    )
    # Retain departed names and every existing series. No universe refresh can
    # silently remove an input or a held/departed security's prices.
    names = membership.symbols(set(names) | set(base.bars))
    if len(calendar.sessions(start, latest)) * len(names) > membership.MAX_BARS:
        raise ResearchError("Updated snapshot exceeds 4,000,000 daily bars.")
    overlap = max(start, old_end - timedelta(days=OVERLAP_DAYS))
    existing, newcomers = sorted(set(base.bars)), sorted(set(names) - set(base.bars))
    api = provider or Provider(store)
    pieces = []
    try:
        for stocks, first, label in [
            (existing, overlap, "Refreshing recent prices/actions"),
            (newcomers, start, "Backfilling new members"),
        ]:
            if not stocks:
                continue
            progress(8 if not pieces else 48, label)
            piece, raw, _ = download_market(
                store,
                {
                    "name": "Update inputs",
                    "universe": mode,
                    "symbols": extras,
                    "start": str(first),
                    "end": str(latest),
                    "capture_available": True,
                },
                lambda n, t: progress((8 if not pieces else 48) + round(n * 0.35), t),
                api,
                persist=False,
                resolved=(stocks, new_audit, sectors),
            )
            pieces.append((piece, raw, first))
        bars = {s: {b.session: b for b in rows} for s, rows in base.bars.items()}
        unavailable = dict(base.metadata.get("unavailable_symbols", {}))
        securities = {s["symbol"]: s for s in base.metadata.get("securities", [])}
        observations = list(base.metadata.get("observation_ids", []))
        for piece, _, first in pieces:
            for security in piece.metadata["securities"]:
                old = securities.get(security["symbol"])
                if old and old.get("id") != security.get("id"):
                    raise ResearchError(
                        f"{security['symbol']}: provider identity changed. Incremental prices cannot be spliced across securities; run a full identity review/download."
                    )
                securities[security["symbol"]] = security
            for symbol, rows in piece.bars.items():
                # Replace the complete overlap, including deleted/corrected
                # bars and removed actions. Retaining missing old rows would
                # conceal a provider correction or acquisition failure.
                bars[symbol] = {
                    d: b for d, b in bars.get(symbol, {}).items() if d < first
                }
                bars[symbol].update((b.session, b) for b in rows)
            for symbol, reason in piece.metadata.get("unavailable_symbols", {}).items():
                prior = unavailable.get(symbol)
                unavailable[symbol] = (
                    prior + "; " + reason
                    if prior and reason not in prior
                    else (prior or reason)
                )
            observations.extend(piece.metadata.get("observation_ids", []))
        expected = set(calendar.sessions(start, latest))
        health = [
            {
                "symbol": s,
                "rows": len(rows),
                "expected": len(expected),
                "missing_count": len(expected - rows.keys()),
                "missing_examples": [
                    str(d) for d in sorted(expected - rows.keys())[:10]
                ],
                "start": str(min(rows)) if rows else None,
                "end": str(max(rows)) if rows else None,
                "reason": unavailable.get(s),
            }
            for s, rows in sorted(bars.items())
        ]
        lineage = {
            "contract": "incremental-snapshot-v1",
            "parent_dataset_id": base.id,
            "parent_digest": base.digest,
            "membership": new_audit,
            "overlap_start": str(overlap),
            "end": str(latest),
            "pieces": [store.capture_source(raw) for _, raw, _ in pieces],
        }
        raw = json.dumps(lineage, sort_keys=True).encode()
        digest = hashlib.sha256(raw).hexdigest()
        metadata = {
            **base.metadata,
            "membership": new_audit,
            "securities": list(securities.values()),
            "unavailable_symbols": unavailable,
            "coverage": health,
            "observation_ids": sorted(set(observations)),
            "download": {"symbols": names, "start": str(start), "end": str(latest)},
            "universe": new_audit["mode"]
            if new_audit
            else base.metadata.get("universe"),
            "sector_basis": "Unknown historical sectors; no current classification backfill"
            if new_audit
            else base.metadata.get("sector_basis"),
            "retrieved_at": now(),
            "identity_asof": str(latest),
            "identity_resolution": {
                **base.metadata.get("identity_resolution", {}),
                **{
                    s: evidence
                    for p, _, _ in pieces
                    for s, evidence in p.metadata.get("identity_resolution", {}).items()
                },
            },
            "action_count": sum(
                (b.split != 1) + (b.dividend > 0)
                for rows in bars.values()
                for b in rows.values()
            ),
            "action_count_basis": "Normalized split/dividend days, including frozen earlier history",
            "update": {**lineage, "membership": None},
            "validation_issues": [
                reason
                for reason in base.metadata.get("validation_issues", [])
                if not reason.startswith(
                    (
                        "Historical S&P 500",
                        "This price snapshot has no supported historical",
                    )
                )
            ],
        }
        candidate = replace(
            base,
            id=digest[:24],
            digest=digest,
            name=base.name,
            revision=base.revision + 1,
            bars={
                s: tuple(rows[d] for d in sorted(rows))
                for s, rows in sorted(bars.items())
            },
            metadata=metadata,
            sectors={
                s: "Unknown" if new_audit else base.sectors.get(s, "Unknown")
                for s in names
            },
            fundamentals={},
        )
        if new_audit and new_audit.get("historical"):
            history = new_audit["historical"]
            try:
                membership.validate_coverage(
                    candidate,
                    date.fromisoformat(history["coverage_start"]),
                    date.fromisoformat(history["coverage_end"]),
                )
            except ResearchError as error:
                metadata["validation_issues"].append(str(error))
        original = next(s for s in store.datasets() if s["id"] == base.id)
        warnings = [
            w
            for w in original["warnings"]
            if not w.startswith(
                (
                    "Combined current and historical",
                    "Combined S&P 500 download",
                    "Incremental update:",
                )
            )
        ]
        warnings.append(NOTE)
        if new_audit and new_audit.get("historical"):
            h = new_audit["historical"]
            warnings.append(
                f"Supported backtest membership: {h['coverage_start']} through {h['coverage_end']}. Required-member prices/actions must also be verified."
            )
        progress(78, "Saving shared price blocks and immutable lineage")
        store.share_dataset_storage(base.id)
        saved = store.save_dataset(candidate, raw, warnings)
        from .sectors import attach as attach_sectors

        saved = attach_sectors(
            store,
            saved["id"],
            lambda n, t: progress(78 + round(n * 0.02), t),
            refresh=True,
        )
        if requested.get("metadata", {}).get("fundamentals"):
            from .fundamentals import attach

            progress(80, "Refreshing filing-versioned SEC data")
            try:
                saved = attach(
                    store,
                    saved["id"],
                    lambda n, t: progress(80 + round(n * 0.18), t),
                    api,
                    refresh=True,
                )
            except ResearchError as error:
                raise ResearchError(
                    f"Updated prices were saved as {saved['name']} ({saved['id']}), but SEC refresh failed. Add SEC fundamentals to that new price snapshot to retry. {error}"
                ) from None
        return saved
    finally:
        if provider is None:
            api.close()
