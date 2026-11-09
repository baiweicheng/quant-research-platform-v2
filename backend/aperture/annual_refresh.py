"""Refetch financial histories on annual filing changes, with periodic rechecks."""

import hashlib
import json

from .domain import ResearchError

MAX_REUSE_SECONDS = 30 * 86400


def annual_signature(submissions):
    recent = submissions.get("filings", {}).get("recent", {})
    if (
        not isinstance(recent.get("form"), list)
        or not isinstance(recent.get("accessionNumber"), list)
        or len(recent["form"]) != len(recent["accessionNumber"])
    ):
        return None  # Incomplete change evidence cannot authorize reuse.
    columns = ["form", "accessionNumber", "filingDate", "reportDate", "primaryDocument"]
    annuals = []
    for index, form in enumerate(recent.get("form", [])):
        if form not in {"10-K", "10-K/A"}:
            continue
        row = [
            recent[key][index]
            if isinstance(recent.get(key), list) and index < len(recent[key])
            else None
            for key in columns
        ]
        if not all(isinstance(value, str) and value for value in row):
            return None
        annuals.append(row)
    value = {
        "cik": submissions.get("cik"),
        "entityType": submissions.get("entityType"),
        "annuals": sorted(annuals, key=str),
        "archives": submissions.get("filings", {}).get("files", []),
    }
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def companyfacts(api, cik, submissions, *, force=False):
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    resource = url + "?{}"
    store = getattr(api, "store", None)
    key = f"annual-facts-v1:{cik}"
    signature = annual_signature(submissions)
    state = store.preference(key, {}) if store else {}
    stats = getattr(api, "annual_cache_stats", None)
    if stats is None:
        stats = api.annual_cache_stats = {"reused": 0, "downloaded": 0}
    if store and signature and not force and state.get("signature") == signature:
        cached = store.cached("sec", resource, MAX_REUSE_SECONDS)
        if cached:
            with store.connect() as db:
                row = db.execute(
                    "SELECT digest FROM observations WHERE id=?", (cached[1],)
                ).fetchone()
            if (
                row
                and row["digest"] == state.get("digest")
                and isinstance(cached[0], dict)
                and str(cached[0].get("cik", "")).zfill(10) == cik
            ):
                api.observations.append(cached[1])
                stats["reused"] += 1
                return cached[0]
    result = api.get("sec", url, ttl=0)
    stats["downloaded"] += 1
    if not isinstance(result, dict) or str(result.get("cik", "")).zfill(10) != cik:
        raise ResearchError("SEC issuer identity mismatch in financial history.")
    # Only an actual captured response can authorize future reuse. Test clients
    # without a store still exercise normalization without persistent state.
    if store and signature:
        with store.connect() as db:
            row = db.execute(
                "SELECT digest FROM observations WHERE provider='sec' AND resource=? ORDER BY fetched_at DESC,rowid DESC LIMIT 1",
                (resource,),
            ).fetchone()
        if row:
            store.set_preference(key, {"signature": signature, "digest": row["digest"]})
    return result
