"""Captured current/last-known sector proxies under the user's research policy.

No classification is a certified point-in-time sector history. Saved snapshots
freeze source captures and every per-symbol decision; backtests never fetch.
"""

import csv
import hashlib
import io
import json
from collections import Counter, defaultdict
from datetime import date

import httpx

from .domain import ResearchError
from .sector_evidence import (
    ALIASES,
    BUSINESS_INFERENCES,
    FUNDS,
    REVIEWED,
    VERSION as REVIEW_VERSION,
    WARRANTS,
)
from .store import decode, now

VERSION = "current-last-known-sectors-v1"
URL = "https://raw.githubusercontent.com/lawcal/sp500-components-history/main/data/components_history.csv"
NOTE = "Sector caps use captured current or last-known classifications, including reviewed issuer-business proxies when necessary. These static labels may use information after a historical decision and can introduce classification look-ahead bias; they are not point-in-time sector history."
LABELS = (
    "Energy",
    "Materials",
    "Industrials",
    "Consumer Discretionary",
    "Consumer Staples",
    "Health Care",
    "Financials",
    "Information Technology",
    "Communication Services",
    "Utilities",
    "Real Estate",
)
NORMALIZED = {s.lower().replace(" ", "_"): s for s in LABELS}
NORMALIZED.update(
    {
        "technology": "Information Technology",
        "healthcare": "Health Care",
        "communication": "Communication Services",
        "telecommunication_services": "Communication Services",
    }
)


def normalize(value):
    return NORMALIZED.get(
        str(value).strip().lower().replace(" ", "_").replace("-", "_"), "Unknown"
    )


def parse(text):
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")), strict=True)
    if reader.fieldnames != [
        "symbol",
        "cik",
        "name",
        "sector",
        "date_added",
        "date_removed",
        "created_at",
    ]:
        raise ResearchError(
            "Sector archive format changed. Existing snapshots are unchanged."
        )
    rows = []
    try:
        for record in reader:
            if (
                len(rows) >= 10000
                or None in record
                or normalize(record["sector"]) == "Unknown"
            ):
                raise ValueError("invalid classification")
            for key in ("date_added", "date_removed", "created_at"):
                if record[key]:
                    date.fromisoformat(record[key].rstrip("*"))
            if (
                not record["symbol"]
                or not record["name"]
                or not record["cik"].isdigit()
            ):
                raise ValueError("missing issuer")
            rows.append(
                {
                    **record,
                    "sector": normalize(record["sector"]),
                    "cik": record["cik"].zfill(10),
                }
            )
    except (csv.Error, KeyError, TypeError, ValueError):
        raise ResearchError(
            "Sector archive contains incomplete or invalid records. No classification snapshot was saved."
        ) from None
    if len(rows) < 450:
        raise ResearchError(
            "Sector archive is unexpectedly incomplete. No classification snapshot was saved."
        )
    return rows


def capture(store, *, refresh=False, client=None):
    cached = store.cached("sectors", URL, 0 if refresh else 86400)
    if cached:
        body, observation = cached
        # Revalidate cached inputs too; cached data is not an integrity bypass.
        return parse(body["csv"]), {k: v for k, v in body.items() if k != "csv"} | {
            "observation_id": observation
        }
    owned = client is None
    client = client or httpx.Client(timeout=45, follow_redirects=False)
    try:
        response = client.get(
            URL,
            headers={
                "User-Agent": "Aperture public research sector capture",
                "Accept": "text/csv",
            },
        )
        if not response.is_success or len(response.content) > 2 * 1024 * 1024:
            raise ResearchError(
                "Sector archive could not be downloaded completely. Retry the sector stage; existing snapshots are unchanged."
            )
        rows = parse(response.text)
        body = {
            "url": URL,
            "sha256": hashlib.sha256(response.content).hexdigest(),
            "captured_at": now(),
            "csv": response.text,
            "attribution": "Calvin Law, sp500-components-history; Wikipedia constituent classifications. Retrospective public data, not an official GICS history.",
        }
        observation = store.observe(
            "sectors", URL, json.dumps(body, sort_keys=True).encode()
        )
        return rows, {k: v for k, v in body.items() if k != "csv"} | {
            "observation_id": observation
        }
    except httpx.RequestError:
        raise ResearchError(
            "Sector archive could not be reached. Retry the sector stage; existing snapshots are unchanged."
        ) from None
    finally:
        if owned:
            client.close()


def classify(summary, declared, rows, source):
    meta = summary.get("metadata", {})
    membership = meta.get("membership") or {}
    current = membership.get(
        "current", membership if membership.get("kind") == "current" else {}
    )
    current = {r["symbol"]: r for r in current.get("members", [])}
    archive = defaultdict(list)
    coverage = {r["symbol"]: r for r in meta.get("coverage", [])}
    for row in rows:
        archive[row["symbol"]].append(row)
    records = {}
    for symbol in summary["symbols"]:
        record = {
            "symbol": symbol,
            "sector": "Unknown",
            "method": "unresolved",
            "reason": "No unambiguous sector evidence; all unknown stocks share the sector cap.",
        }
        if symbol == "SPY" or symbol in FUNDS:
            name, url = (
                (
                    "SPY benchmark ETF",
                    "https://www.ssga.com/us/en/intermediary/etfs/spdr-sp-500-etf-trust-spy",
                )
                if symbol == "SPY"
                else FUNDS[symbol]
            )
            record = {
                "symbol": symbol,
                "sector": None,
                "method": "not_applicable",
                "name": name,
                "source": url,
                "reason": "Pooled fund / benchmark, not an operating-company sector. Classification does not grant stock eligibility.",
            }
        elif symbol in ALIASES:
            quote, until, link = ALIASES[symbol]
            candidates = [
                r
                for r in archive[quote]
                if r["date_added"].rstrip("*") <= until
                and (not r["date_removed"] or r["date_removed"].rstrip("*") >= until)
            ]
            if len({r["sector"] for r in candidates}) == 1:
                record = {
                    **candidates[-1],
                    "symbol": symbol,
                    "method": "reviewed_historical_alias",
                    "source": source["url"],
                    "identity_source": link,
                    "quote_symbol": quote,
                    "identity_through": until,
                    "reason": "Classification only; original identity/action restrictions remain unchanged.",
                }
        elif symbol in WARRANTS:
            sector, name, link = WARRANTS[symbol]
            record = {
                "symbol": symbol,
                "sector": sector,
                "method": "reviewed_warrant_issuer",
                "name": name,
                "source": link,
                "reason": "Issuer-sector exposure proxy for a warrant; not an ordinary-stock eligibility decision.",
            }
        elif (
            symbol in current and normalize(current[symbol].get("sector")) != "Unknown"
        ):
            r = current[symbol]
            record = {
                **r,
                "sector": normalize(r["sector"]),
                "method": "captured_current_roster",
                "source": membership.get("current", membership).get(
                    "source",
                    "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
                ),
            }
        elif symbol in REVIEWED:
            sector, name, evidence_date, link = REVIEWED[symbol]
            record = {
                "symbol": symbol,
                "sector": sector,
                "name": name,
                "evidence_date": evidence_date,
                "source": link,
                "method": "reviewed_business_proxy"
                if symbol in BUSINESS_INFERENCES
                else "dated_public_classification",
                "reason": "Static current/last-known research proxy, not a complete sector timeline.",
            }
        elif archive[symbol]:
            span = coverage.get(symbol, {})
            first = span.get("start") or summary["start"]
            last = span.get("end") or summary["end"]
            candidates = [
                r
                for r in archive[symbol]
                if r["date_added"].rstrip("*") <= last
                and (not r["date_removed"] or r["date_removed"].rstrip("*") >= first)
            ]
            if not candidates and len({r["cik"] for r in archive[symbol]}) == 1:
                # Leaving an index does not expire a business classification.
                # Only one archived issuer may supply this last-known fallback.
                candidates = archive[symbol]
            sectors = {r["sector"] for r in candidates}
            # Recycled symbols with conflicting classifications require review.
            if len(sectors) == 1:
                r = max(candidates, key=lambda r: (r["date_added"], r["created_at"]))
                record = {
                    **r,
                    "method": "archived_constituent_last_known",
                    "source": source["url"],
                    "reason": "Retrospective last-known label; membership dates do not certify the sector's effective date.",
                }
            else:
                record["reason"] = (
                    "Conflicting sectors across archived issuer identities; no ticker-only choice was made."
                )
        elif normalize(declared.get(symbol)) != "Unknown":
            record = {
                "symbol": symbol,
                "sector": normalize(declared[symbol]),
                "method": "declared_snapshot_sector",
                "source": summary["source"],
            }
        records[symbol] = record
    unknown = [
        s
        for s, r in records.items()
        if r["method"] != "not_applicable" and r["sector"] == "Unknown"
    ]
    excluded = [s for s, r in records.items() if r["method"] == "not_applicable"]
    digest = hashlib.sha256(
        json.dumps(
            {"version": VERSION, "reviewed": REVIEW_VERSION, "records": records},
            sort_keys=True,
        ).encode()
    ).hexdigest()
    audit = {
        "version": VERSION,
        "policy": "current_or_last_known_static",
        "warning": NOTE,
        "reviewed_version": REVIEW_VERSION,
        "classification_digest": digest,
        "captured_at": source["captured_at"],
        "sources": [source],
        "records": records,
        "classified_count": len(records) - len(unknown) - len(excluded),
        "unresolved_count": len(unknown),
        "unresolved_symbols": unknown,
        "not_applicable_count": len(excluded),
        "symbol_count": len(records),
        "method_counts": dict(Counter(r["method"] for r in records.values())),
    }
    return {s: r["sector"] or "Unknown" for s, r in records.items()}, audit


def attach(
    store, identifier, progress=lambda *args: None, *, refresh=False, client=None
):
    with store.connect() as db:
        saved = db.execute(
            "SELECT summary,body FROM datasets WHERE id=?", (identifier,)
        ).fetchone()
        if saved is None:
            raise ResearchError("That dataset was not found. Choose a saved dataset.")
        summary, body = json.loads(saved["summary"]), decode(saved["body"])
    if summary["kind"] == "synthetic":
        raise ResearchError(
            "Practice sectors are fictional; choose actual market data."
        )
    progress(10, "Downloading current and former-constituent sector evidence")
    rows, source = capture(store, refresh=refresh, client=client)
    sectors, audit = classify(summary, body["sectors"], rows, source)
    old = summary.get("metadata", {}).get("sector_classification", {})
    if (
        old.get("classification_digest") == audit["classification_digest"]
        and old.get("sources", [{}])[0].get("sha256") == source["sha256"]
    ):
        return {**summary, "already_imported": True}
    progress(
        80,
        f"Saving sectors: {audit['classified_count']} classified, {audit['unresolved_count']} unresolved",
    )
    metadata = {
        **summary.get("metadata", {}),
        "sector_classification": audit,
        "sector_basis": NOTE,
        "sector_parent_dataset_id": identifier,
    }
    raw = json.dumps(
        {
            "base_digest": summary["digest"],
            "sector_policy": VERSION,
            "classifications": audit["classification_digest"],
            "sources": source["sha256"],
        },
        sort_keys=True,
    ).encode()
    return store.save_metadata_snapshot(
        identifier, hashlib.sha256(raw).hexdigest(), sectors, metadata, raw, NOTE
    )
