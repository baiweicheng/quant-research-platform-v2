"""Bounded, captured provider reads. No credential is persisted with a request."""

import hashlib
import json
import time
import base64
import threading
import logging
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from decimal import Decimal
from urllib.parse import quote
from zoneinfo import ZoneInfo

import httpx

from . import calendar
from .config import DATA_URL, PAPER_URL, Settings, settings
from .domain import Bar, Dataset, ResearchError, ZERO, decimal
from .ingest import WARNING
from . import membership
from .store import Store, now

SECTORS = {
    s: sector
    for sector, names in {
        "Technology": "AAPL MSFT NVDA",
        "Communication": "GOOGL META",
        "Consumer discretionary": "AMZN",
        "Financials": "JPM BAC V MA",
        "Healthcare": "JNJ MRK ABBV",
        "Consumer staples": "PG KO PEP COST WMT",
        "Energy": "XOM CVX",
        "Industrials": "CAT DE UNP LMT",
        "Utilities": "NEE DUK SO",
        "Materials": "LIN ECL APD",
        "Real estate": "AMT",
    }.items()
    for s in names.split()
}


class ResourceMissing(ResearchError):
    """An official resource returned HTTP 404; other failures stay fatal."""


class EvidenceLimit(ResearchError):
    """A bounded filing read cannot verify this accession's share units."""


MAX_FILING_BYTES = 96 * 1024 * 1024
SEC_REQUEST_INTERVAL = 0.125
LOG = logging.getLogger(__name__)


class Provider:
    def __init__(
        self,
        store: Store,
        client: httpx.Client | None = None,
        cfg: Settings | None = None,
    ):
        self.store, self.cfg = store, cfg or settings()
        self.client = client or httpx.Client(timeout=30, follow_redirects=False)
        self.owned = client is None
        self._fresh_retry_clients = self.owned
        self.observations: list[str] = []
        self._sec_gate = {"lock": threading.Lock(), "next": 0.0}

    def fork(self):
        """An independent evidence/source list, sharing one bounded HTTP client."""
        child = Provider(self.store, self.client, self.cfg)
        child._sec_gate = self._sec_gate
        child._fresh_retry_clients = self._fresh_retry_clients
        return child

    @contextmanager
    def _document_client(self, attempt):
        # An owned transport can retry a stalled filing on fresh connections.
        # Keep caller-provided transports intact, including test/offline clients.
        if attempt and self._fresh_retry_clients:
            with httpx.Client(timeout=30, follow_redirects=False) as client:
                yield client
        else:
            yield self.client

    def _wait_sec(self):
        # All accession readers share this gate: at most eight request starts
        # per second, including retries, rather than a per-thread sleep.
        with self._sec_gate["lock"]:
            delay = self._sec_gate["next"] - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            self._sec_gate["next"] = time.monotonic() + SEC_REQUEST_INTERVAL

    def close(self):
        if self.owned:
            self.client.close()

    def document(self, url: str) -> bytes:
        """Capture a specific immutable SEC filing; never forward broker keys."""
        import re

        if not re.fullmatch(
            r"https://www\.sec\.gov/Archives/edgar/data/\d+/\d{18}/[A-Za-z0-9_.-]+\.(?:html?|xml)",
            url,
        ):
            raise ResearchError("Choose an official SEC filing document.")
        if "@" not in self.cfg.sec_agent:
            raise ResearchError(
                "Configure SEC_USER_AGENT before reading filed share classes."
            )
        resource = url + "#filed-document-v1"
        cached = self.store.cached("sec", resource, 315360000)
        if cached:
            self.observations.append(cached[1])
            return (
                base64.b64decode(cached[0]["base64"])
                if isinstance(cached[0], dict)
                else cached[0].encode()
            )
        limited = self.store.cached("sec", resource + "#size-limit", 86400)
        if limited and limited[0].get("limit_bytes") == MAX_FILING_BYTES:
            self.observations.append(limited[1])
            raise EvidenceLimit(
                "Filed evidence exceeds the supported bounded document size; EPS remains unverified."
            )
        for attempt in range(3):
            try:
                self._wait_sec()
                with (
                    self._document_client(attempt) as client,
                    client.stream(
                        "GET",
                        url,
                        timeout=httpx.Timeout(60.0, connect=10.0, pool=10.0),
                        headers={
                            "User-Agent": self.cfg.sec_agent,
                            "Accept-Encoding": "gzip, deflate",
                        },
                    ) as response,
                ):
                    if (
                        response.status_code in (429, 500, 502, 503, 504)
                        and attempt < 2
                    ):
                        time.sleep(0.5 * (attempt + 1))
                        continue
                    if response.status_code == 404:
                        raise ResourceMissing("SEC filing document was not found.")
                    if not response.is_success:
                        raise ResearchError(
                            f"SEC filing evidence returned HTTP {response.status_code}. Retry acquisition; no unverified EPS was substituted."
                        )
                    body = bytearray()
                    for chunk in response.iter_bytes(chunk_size=65536):
                        if len(body) + len(chunk) > MAX_FILING_BYTES:
                            self.observations.append(
                                self.store.observe(
                                    "sec",
                                    resource + "#size-limit",
                                    json.dumps(
                                        {"limit_bytes": MAX_FILING_BYTES, "url": url}
                                    ).encode(),
                                )
                            )
                            raise EvidenceLimit(
                                "Filed evidence exceeds the supported bounded document size; EPS remains unverified."
                            )
                        body.extend(chunk)
                    raw = bytes(body)
            except httpx.RequestError as error:
                LOG.warning(
                    "SEC filing transport attempt %s/3: %s for %s",
                    attempt + 1,
                    type(error).__name__,
                    url,
                )
                if attempt < 2:
                    time.sleep(0.3 * (attempt + 1))
                    continue
                raise ResearchError(
                    "SEC filed share-class evidence could not be reached. Retry; earlier snapshots remain unchanged."
                ) from None
            self.observations.append(
                self.store.observe(
                    "sec",
                    resource,
                    json.dumps({"base64": base64.b64encode(raw).decode()}).encode(),
                )
            )
            return raw
        raise ResearchError("SEC filing retries exhausted.")

    def get(
        self, provider: str, url: str, params: dict | None = None, ttl: int = 300
    ) -> dict | list:
        if provider == "alpaca":
            if not url.startswith((DATA_URL + "/", PAPER_URL + "/")):
                raise ResearchError(
                    "The Alpaca connection is restricted to approved paper/data hosts."
                )
            headers = self.cfg.headers()
        elif provider == "sec":
            if not url.startswith(
                ("https://data.sec.gov/", "https://www.sec.gov/files/")
            ):
                raise ResearchError("SEC downloads must use official SEC hosts.")
            if "@" not in self.cfg.sec_agent:
                raise ResearchError(
                    "Set SEC_USER_AGENT to a descriptive name and contact email in .env."
                )
            headers = {
                "User-Agent": self.cfg.sec_agent,
                "Accept-Encoding": "gzip, deflate",
            }
        else:
            raise ResearchError("Unknown data provider.")
        resource = url + "?" + json.dumps(params or {}, sort_keys=True)
        cached = self.store.cached(provider, resource, ttl)
        if cached:
            self.observations.append(cached[1])
            return cached[0]
        for attempt in range(3):
            try:
                if provider == "sec":
                    self._wait_sec()
                response = self.client.get(url, params=params, headers=headers)
            except httpx.RequestError:
                if attempt < 2:
                    time.sleep(0.3 * (attempt + 1))
                    continue
                raise ResearchError(
                    f"{provider.title()} could not be reached. Check the connection and retry; existing snapshots are unchanged."
                ) from None
            if response.status_code in (429, 500, 502, 503, 504) and attempt < 2:
                time.sleep(0.5 * (attempt + 1))
                continue
            if not response.is_success:
                explanation = {
                    401: "credentials were rejected",
                    403: "access was denied for this resource",
                    404: "the requested security/resource was not found",
                    429: "the rate limit was reached",
                }.get(response.status_code, f"returned HTTP {response.status_code}")
                if response.status_code == 404:
                    self.observations.append(
                        self.store.observe(
                            provider, resource + "#not-found", response.content
                        )
                    )
                    raise ResourceMissing(
                        f"{provider.title()} {explanation}. No fallback feed or partial dataset was used."
                    )
                raise ResearchError(
                    f"{provider.title()} {explanation}. No fallback feed or partial dataset was used."
                )
            if len(response.content) > 32 * 1024 * 1024:
                raise ResearchError(
                    "Provider response exceeded the 32 MB safety limit. Use a smaller universe or period."
                )
            try:
                body = response.json()
            except ValueError:
                raise ResearchError(
                    f"{provider.title()} returned an unreadable response. Retry later."
                ) from None
            self.observations.append(
                self.store.observe(provider, resource, response.content)
            )
            return body
        raise ResearchError("Provider retries exhausted.")

    def pages(self, path: str, params: dict, key: str) -> list[dict]:
        output, seen = [], set()
        for _ in range(500):
            body = self.get("alpaca", DATA_URL + path, params)
            if not isinstance(body, dict) or not isinstance(body.get(key), dict):
                raise ResearchError(
                    "The provider response format changed; the incomplete snapshot was discarded."
                )
            output.append(body)
            token = body.get("next_page_token")
            if not token:
                return output
            if token in seen:
                raise ResearchError(
                    "Provider repeated a pagination token. The incomplete download was discarded."
                )
            seen.add(token)
            params = {**params, "page_token": token}
        raise ResearchError("Provider pagination exceeded the supported limit.")


def validate_symbols(symbols: list[str]) -> list[str]:
    result = membership.symbols(symbols)
    if "SPY" not in result:
        result.append("SPY")
    if len(result) > membership.MAX_SYMBOLS:
        raise ResearchError(
            "Leave one of the 1,500 symbol slots for the SPY benchmark."
        )
    return result


def batch_pages(api, path, query, key):
    names = query["symbols"].split(",")
    output = []
    for offset in range(0, len(names), 100):
        output.extend(
            api.pages(
                path, {**query, "symbols": ",".join(names[offset : offset + 100])}, key
            )
        )
    return output


def download_market(
    store: Store,
    payload: dict,
    progress,
    provider: Provider | None = None,
    *,
    persist=True,
    resolved=None,
) -> dict:
    start, end = (
        date.fromisoformat(payload["start"]),
        date.fromisoformat(payload["end"]),
    )
    latest = calendar.latest_complete()
    if start < date(2016, 1, 4) or end > latest or start >= end:
        raise ResearchError(
            f"Choose dates from 2016-01-04 through the latest completed session, {latest}."
        )
    symbols, membership_audit, member_sectors = resolved or membership.resolve(
        store, payload, start, end
    )
    symbols = membership.symbols(symbols) if resolved else validate_symbols(symbols)
    expected = calendar.sessions(start, end)
    available_at = {day: calendar.available_time(day) for day in expected}
    if len(expected) * len(symbols) > membership.MAX_BARS:
        raise ResearchError(
            "This request exceeds 4,000,000 daily bars. Reduce the period or stock list."
        )
    api = provider or Provider(store)
    try:
        securities = []
        combined = membership_audit and membership_audit["kind"] == "combined"
        capture_available = combined or bool(payload.get("capture_available"))
        historical = membership_audit and membership_audit["kind"] in (
            "historical",
            "combined",
        )
        history = membership_audit["historical"] if combined else membership_audit
        historical_symbols = (
            {s for row in history["rosters"] for s in row["symbols"]}
            if historical and history
            else set()
        )
        required_symbols = set(symbols)
        unavailable = {}
        identity_audit = {}
        if combined:
            required_symbols = (
                historical_symbols
                | set(membership_audit["additional_symbols"])
                | {"SPY"}
            )
            if str(start) <= membership_audit["current"]["coverage_start"] <= str(end):
                required_symbols.update(
                    m["symbol"] for m in membership_audit["current"]["members"]
                )
        asset_map = None
        if len(symbols) > 100:
            asset_map = {}
            candidates = {}
            for status in ["active", "inactive"]:
                assets = api.get(
                    "alpaca",
                    PAPER_URL + "/v2/assets",
                    {"status": status, "asset_class": "us_equity"},
                    ttl=86400,
                )
                if not isinstance(assets, list):
                    raise ResearchError("The provider asset directory changed format.")
                for asset in assets:
                    key = asset.get("symbol")
                    if key in symbols:
                        candidates.setdefault(key, {})[asset.get("id")] = asset
            current_members = (
                {m["symbol"]: m for m in membership_audit["current"]["members"]}
                if combined
                else {}
            )
            for key, by_id in candidates.items():
                rows = list(by_id.values())
                if len(rows) == 1:
                    asset_map[key] = rows[0]
                    continue
                active = [a for a in rows if a.get("status") == "active"]
                observed = current_members.get(key, {})
                first_member = min(
                    (
                        max(str(start), r["effective"])
                        for r in (history or {}).get("rosters", [])
                        if key in r["symbols"]
                    ),
                    default=str(end),
                )
                same_listing = len(
                    {
                        (
                            a.get("symbol"),
                            a.get("name"),
                            a.get("exchange"),
                            a.get("class"),
                        )
                        for a in rows
                    }
                ) == 1 and all(a.get("name") and a.get("exchange") for a in rows)
                current_only = not historical or (
                    combined and key not in historical_symbols
                )
                supported_listing = (
                    combined
                    and same_listing
                    and observed.get("date_added")
                    and first_member >= observed["date_added"]
                )
                identity_audit[key] = {
                    "candidate_ids": sorted(by_id),
                    "basis": "unresolved",
                }
                if len(active) == 1 and (current_only or supported_listing):
                    resolved = (
                        api.get(
                            "alpaca",
                            PAPER_URL + "/v2/assets/" + quote(key, safe=""),
                            ttl=86400,
                        )
                        if supported_listing
                        else active[0]
                    )
                    if (
                        resolved.get("id") == active[0].get("id")
                        and resolved.get("symbol") == key
                        and all(
                            resolved.get(k) == active[0].get(k)
                            for k in ("name", "exchange", "class")
                        )
                    ):
                        asset_map[key] = resolved
                        identity_audit[key].update(
                            basis="provider_symbol_lookup_matching_listing"
                            if supported_listing
                            else "observed_current_listing",
                            selected_id=resolved["id"],
                            date_added=observed.get("date_added"),
                        )
                        continue
                reason = f"Ambiguous historical identity for {key}; ticker reuse cannot be guessed."
                if not capture_available:
                    raise ResearchError(reason)
                unavailable[key] = reason
        for index, symbol in enumerate(symbols):
            progress(
                2 + round(index / len(symbols) * 15), f"Checking US listing: {symbol}"
            )
            if symbol in unavailable:
                continue
            try:
                asset = (
                    asset_map[symbol]
                    if asset_map is not None and symbol in asset_map
                    else api.get(
                        "alpaca",
                        PAPER_URL + "/v2/assets/" + quote(symbol, safe=""),
                        ttl=86400,
                    )
                )
            except ResearchError as error:
                if (
                    not capture_available
                    or "security/resource was not found" not in str(error)
                ):
                    raise
                unavailable[symbol] = (
                    f"{symbol}: provider listing metadata is unavailable."
                )
                continue
            if (
                asset.get("class") != "us_equity"
                or asset.get("exchange")
                not in ("NYSE", "NASDAQ", "AMEX", "ARCA", "BATS", "NYSEARCA")
                or asset.get("status") not in ("active", "inactive")
            ):
                reason = f"{symbol} has no unambiguous supported US exchange listing in the provider directory."
                if not capture_available:
                    raise ResearchError(reason)
                unavailable[symbol] = reason
                continue
            import re

            if symbol != "SPY" and re.search(
                r"\b(ETF|ETN|Fund|iShares|SPDR)\b", asset.get("name", ""), re.IGNORECASE
            ):
                reason = f"{symbol} maps to a fund rather than an ordinary company listing; historical identity requires resolution."
                if not capture_available:
                    raise ResearchError(reason)
                unavailable[symbol] = reason
                continue
            securities.append(
                {
                    k: asset.get(k)
                    for k in (
                        "id",
                        "symbol",
                        "name",
                        "exchange",
                        "status",
                        "tradable",
                        "fractionable",
                    )
                }
            )
        # Date-only end parameters are midnight, so explicitly include the entire
        # last NY session, while staying outside the latest 15-minute SIP window.
        available_symbols = [s for s in symbols if s not in unavailable]
        if not available_symbols:
            raise ResearchError(
                "No securities have a resolved provider identity; no dataset was saved."
            )
        query = {
            "symbols": ",".join(available_symbols),
            "timeframe": "1Day",
            "start": start.isoformat(),
            "end": calendar.close_time(expected[-1]).isoformat(),
            "limit": 10000,
            "feed": "sip",
            "adjustment": "raw",
            "asof": latest.isoformat(),
            "sort": "asc",
        }
        progress(20, "Downloading consolidated daily bars")
        bar_pages = batch_pages(api, "/v2/stocks/bars", query, "bars")
        bars: dict[str, dict[date, Bar]] = {s: {} for s in symbols}

        def reject_symbol(symbol, reason, *, keep_prices=False):
            if not capture_available:
                raise ResearchError(reason)
            unavailable.setdefault(symbol, reason)
            if not keep_prices:
                bars[symbol] = {}

        for page in bar_pages:
            for symbol, items in page.get("bars", {}).items():
                if symbol not in bars:
                    raise ResearchError("Provider returned an unexpected symbol.")
                for row in items:
                    day = (
                        datetime.fromisoformat(row["t"].replace("Z", "+00:00"))
                        .astimezone(ZoneInfo("America/New_York"))
                        .date()
                    )
                    if day not in available_at:
                        continue
                    if day in bars[symbol]:
                        raise ResearchError(f"Duplicate provider bar: {symbol} {day}.")
                    volume = decimal(row["v"], "Raw volume")
                    if volume != volume.to_integral_value():
                        raise ResearchError(
                            f"{symbol} {day} has fractional raw volume, which this dataset contract cannot silently round."
                        )
                    bars[symbol][day] = Bar(
                        symbol,
                        day,
                        *(decimal(row[k], k) for k in ("o", "h", "l", "c")),
                        int(volume),
                        available_at=available_at[day],
                    )
        progress(40, "Checking split and dividend events")
        action_pages = batch_pages(
            api,
            "/v1/corporate-actions",
            {
                "symbols": ",".join(available_symbols),
                "start": str(start - timedelta(days=90)),
                "end": str(latest + timedelta(days=90)),
                "limit": 1000,
                "data_quality": "all",
            },
            "corporate_actions",
        )
        events: dict[str, dict] = {}
        for page in action_pages:
            for kind, items in page.get("corporate_actions", {}).items():
                for item in items:
                    event_id = item.get("id")
                    if not event_id:
                        raise ResearchError(
                            "Corporate action has no stable identifier."
                        )
                    if event_id in events and events[event_id] != {
                        "kind": kind,
                        **item,
                    }:
                        raise ResearchError(
                            "Conflicting revisions of one corporate action were returned."
                        )
                    events[event_id] = {"kind": kind, **item}
        # Provider asof pins identity to today's requested listing. Preserve
        # explicit rename aliases; do not treat ticker text as a permanent ID.
        aliases = {s: s for s in symbols}
        for event in reversed(
            sorted(events.values(), key=lambda e: e.get("process_date", ""))
        ):
            if event["kind"] == "name_changes" and event.get("new_symbol") in aliases:
                aliases[event["old_symbol"]] = aliases[event["new_symbol"]]
        from dataclasses import replace

        applied = []
        for event in events.values():
            kind = event["kind"]
            symbol = aliases.get(
                event.get("symbol")
                or event.get("source_symbol")
                or event.get("acquiree_symbol")
                or event.get("old_symbol")
            )
            effective = (
                event.get("ex_date")
                or event.get("effective_date")
                or event.get("process_date")
            )
            if not effective:
                raise ResearchError("A corporate action is missing its effective date.")
            day = date.fromisoformat(effective)
            if (
                symbol is None
                or symbol not in available_symbols
                or not start <= day <= end
                or kind == "name_changes"
            ):
                continue
            if kind not in ("forward_splits", "reverse_splits", "cash_dividends"):
                reject_symbol(
                    symbol,
                    f"{symbol} has an unsupported {kind.replace('_', ' ')} on {day}. Choose a supported period; the event cannot be ignored.",
                    keep_prices=True,
                )
                continue
            if day not in bars[symbol]:
                reject_symbol(
                    symbol,
                    f"Missing {symbol} bar on corporate-action date {day}.",
                    keep_prices=True,
                )
                continue
            bar = bars[symbol][day]
            if kind == "cash_dividends":
                if (
                    (event.get("foreign") and event.get("currency") != "USD")
                    or event.get("due_bill_on_date")
                    or event.get("due_bill_off_date")
                    or event.get("currency") not in (None, "", "USD")
                ):
                    reject_symbol(
                        symbol,
                        f"{symbol} has a foreign/special/due-bill dividend requiring separate accounting. It was not treated as an ordinary USD dividend.",
                        keep_prices=True,
                    )
                    continue
                if not event.get("payable_date"):
                    reject_symbol(
                        symbol,
                        f"{symbol} dividend on {day} lacks a pay date. Cash timing cannot be guessed.",
                        keep_prices=True,
                    )
                    continue
                pay = date.fromisoformat(event["payable_date"])
                if pay < day:
                    reject_symbol(
                        symbol,
                        f"{symbol} dividend on {day} has a pay date before its ex-date. Cash timing requires resolution.",
                        keep_prices=True,
                    )
                    continue
                if bar.dividend and bar.pay_date != pay:
                    reject_symbol(
                        symbol,
                        "Same-day dividends have different pay dates; separate entitlements are required.",
                        keep_prices=True,
                    )
                    continue
                bars[symbol][day] = replace(
                    bar, dividend=bar.dividend + decimal(event["rate"]), pay_date=pay
                )
            else:
                old, new = decimal(event["old_rate"]), decimal(event["new_rate"])
                if old <= ZERO or new <= ZERO:
                    reject_symbol(
                        symbol, "Split ratios must be positive.", keep_prices=True
                    )
                    continue
                bars[symbol][day] = replace(bar, split=bar.split * new / old)
            applied.append(event)
        progress(65, "Cross-checking action adjustments and missing sessions")
        # Compare the raw/split-adjusted factor change with the independently
        # returned split event. This catches wrong units and missing split rows.
        split_pages = batch_pages(
            api, "/v2/stocks/bars", {**query, "adjustment": "split"}, "bars"
        )
        adjusted = {s: {} for s in symbols}
        for page in split_pages:
            for symbol, items in page.get("bars", {}).items():
                for row in items:
                    day = (
                        datetime.fromisoformat(row["t"].replace("Z", "+00:00"))
                        .astimezone(ZoneInfo("America/New_York"))
                        .date()
                    )
                    adjusted[symbol][day] = decimal(row["c"])
        health = []
        for symbol in symbols:
            rows = sorted(bars[symbol].values(), key=lambda b: b.session)
            try:
                if not rows and symbol in required_symbols:
                    raise ResearchError(f"No bars were returned for {symbol}.")
                for before, current in zip(rows, rows[1:]):
                    if (
                        before.session not in adjusted[symbol]
                        or current.session not in adjusted[symbol]
                    ):
                        raise ResearchError(
                            "The split cross-check has incomplete coverage."
                        )
                    previous_adjusted = adjusted[symbol][before.session]
                    current_adjusted = adjusted[symbol][current.session]
                    half_cent = Decimal("0.005")
                    if min(previous_adjusted, current_adjusted) <= half_cent:
                        raise ResearchError(
                            f"Adjusted-price precision is insufficient to verify {symbol} on {current.session}."
                        )
                    # Adjusted USD prices are cent-rounded by this feed. Check
                    # compatible rounding intervals rather than exact ratios.
                    lower = (current_adjusted - half_cent) / (
                        previous_adjusted + half_cent
                    )
                    upper = (current_adjusted + half_cent) / (
                        previous_adjusted - half_cent
                    )
                    expected_return = current.close * current.split / before.close
                    if (
                        not lower - Decimal("0.00000001")
                        <= expected_return
                        <= upper + Decimal("0.00000001")
                    ):
                        raise ResearchError(
                            f"Split/action disagreement for {symbol} on {current.session}. No dataset was published."
                        )
            except ResearchError as error:
                reject_symbol(symbol, str(error), keep_prices=True)
            missing = sorted(set(expected) - bars[symbol].keys())
            health.append(
                {
                    "symbol": symbol,
                    "rows": len(rows),
                    "expected": len(expected),
                    "missing_count": len(missing),
                    "reason": unavailable.get(symbol),
                    "missing_examples": [str(d) for d in missing[:10]],
                    "start": str(rows[0].session) if rows else None,
                    "end": str(rows[-1].session) if rows else None,
                }
            )
        provenance = {
            "contract": "alpaca-raw-v1",
            "normalizer_version": "1.2.0",
            "sectors": {
                s: member_sectors.get(s, "Unknown")
                if historical
                else member_sectors.get(s, SECTORS.get(s, "Unknown"))
                for s in symbols
            },
            "bar_pages": bar_pages,
            "actions": action_pages,
            "split_pages": split_pages,
            "securities": securities,
            "query": query,
            "membership": membership_audit,
            "identity_resolution": identity_audit,
            "unavailable_symbols": unavailable,
        }
        raw = json.dumps(provenance, sort_keys=True, separators=(",", ":")).encode()
        digest = hashlib.sha256(raw).hexdigest()
        metadata = {
            "membership": membership_audit,
            "provider": "alpaca",
            "feed": "sip",
            "price_basis": "as_traded",
            "identity_asof": str(latest),
            "retrieved_at": now(),
            "securities": securities,
            "coverage": health,
            "unavailable_symbols": unavailable,
            "identity_resolution": identity_audit,
            "action_count": len(applied),
            "observation_ids": api.observations,
            "download": {"symbols": symbols, "start": str(start), "end": str(end)},
            "universe": membership_audit["mode"]
            if membership_audit
            else "Explicit fixed list; historical membership/delistings not certified",
            "sector_basis": "Unknown historical sectors; no current classification backfill"
            if historical
            else "Current GICS roster sectors with static research labels for supplements; not historical sector evidence",
        }
        dataset = Dataset(
            digest[:24],
            payload.get("name") or "US stock watchlist",
            "imported",
            1,
            {
                s: tuple(sorted(rows.values(), key=lambda b: b.session))
                for s, rows in bars.items()
            },
            {
                s: member_sectors.get(s, "Unknown")
                if historical
                else member_sectors.get(s, SECTORS.get(s, "Unknown"))
                for s in symbols
            },
            "Alpaca SIP · raw daily bars + corporate actions",
            digest,
            metadata,
        )
        warnings = [
            WARNING,
            "Alpaca can publish corporate actions late. Split factors were cross-checked; dividend completeness is not guaranteed by an empty response.",
            "Daily prices follow provider trade-condition aggregation and are not a guarantee of auction fills. Volume can include extended-hours trades.",
            "Historical availability is modeled as close + 15 minutes; retrieved raw payloads are archived with observation times.",
            "Static sectors are exploratory research classifications, not verified historical sector membership.",
        ]
        if any(a.get("status") == "inactive" for a in securities):
            warnings.append(
                "Inactive listings were retained for historical price coverage. Their inclusion is not evidence that they can currently be traded; paper execution checks tradability separately."
            )
        if any(h["missing_count"] for h in health):
            warnings.append(
                "Some symbols have missing sessions. Signal warm-up excludes incomplete history; a missing held price stops a backtest."
            )
        if combined:
            if history:
                try:
                    membership.validate_coverage(
                        dataset,
                        date.fromisoformat(history["coverage_start"]),
                        date.fromisoformat(history["coverage_end"]),
                    )
                except ResearchError as error:
                    metadata["validation_issues"] = [str(error)]
                    warnings.append(
                        "Downloaded available data; historical validation is blocked: "
                        + str(error)
                    )
            warnings[0] = membership.HISTORY_NOTE
            warnings.append(
                "Combined current and historical S&P 500 download. Price coverage "
                "does not extend verified membership history. Supported backtest "
                f"membership: {history['coverage_start']} through {history['coverage_end']}."
                if history
                else "Combined S&P 500 download has no supported historical membership "
                "overlap in this price period; historical backtests are blocked."
            )
            if unavailable:
                warnings.append(
                    f"{len(unavailable)} securities have unresolved identity or accounting inputs. Available raw prices and per-stock reasons are retained. Tests/reviews requiring these inputs are blocked; members are never silently removed."
                )
        elif historical:
            membership.validate_coverage(dataset, start, end)
            warnings[0] = membership.HISTORY_NOTE
        elif membership_audit:
            warnings[0] = (
                "Current S&P 500 roster plus optional supplements, for current reviews only. Historical backtests are blocked on this snapshot; download S&P 500 current and historical members instead."
            )
        if membership_audit and membership_audit["additional_symbols"]:
            warnings.append(
                "Additional symbols are an explicitly selected fixed supplement, not a historical index; their selection can introduce survivorship/selection bias."
            )
        if capture_available and not combined and unavailable:
            warnings.append(
                f"{len(unavailable)} backfill securities need input verification. Raw prices, when available, and per-stock reasons are retained; affected research/trading is blocked."
            )
        progress(95, "Saving the immutable market snapshot")
        if not any(bars.values()):
            raise ResearchError(
                "No usable price rows were returned. Captured provider observations are retained; no empty dataset was published."
            )
        return (
            store.save_dataset(dataset, raw, warnings)
            if persist
            else (dataset, raw, warnings)
        )
    finally:
        if provider is None:
            api.close()
