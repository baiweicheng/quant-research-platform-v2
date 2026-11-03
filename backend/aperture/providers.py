"""Bounded, captured provider reads. No credential is persisted with a request."""

import hashlib
import json
import time
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from urllib.parse import quote
from zoneinfo import ZoneInfo

import httpx

from . import calendar
from .config import DATA_URL, PAPER_URL, Settings, settings
from .domain import Bar, Dataset, ONE, ResearchError, ZERO, decimal
from .ingest import WARNING
from .store import Store, now

DEFAULT_SYMBOLS = "AAPL MSFT NVDA GOOGL AMZN META JPM BAC V MA JNJ MRK ABBV PG KO PEP COST WMT XOM CVX CAT DE UNP LMT NEE DUK SO ECL APD AMT SPY".split()
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
        self.observations: list[str] = []

    def close(self):
        if self.owned:
            self.client.close()

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
            if provider == "sec":
                time.sleep(
                    0.15
                )  # Single worker, below SEC's ten requests/second ceiling.
            return body
        raise ResearchError("Provider retries exhausted.")

    def pages(self, path: str, params: dict, key: str) -> list[dict]:
        output, seen = [], set()
        for _ in range(100):
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
    import re

    result = list(dict.fromkeys(s.strip().upper() for s in symbols if s.strip()))
    if not 1 <= len(result) <= 100 or any(
        not re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,11}", s) for s in result
    ):
        raise ResearchError(
            "Choose 1–100 US stock symbols, using letters, digits, dots or hyphens."
        )
    if "SPY" not in result:
        result.append("SPY")
    if len(result) > 100:
        raise ResearchError("Leave one of the 100 symbol slots for the SPY benchmark.")
    return result


def download_market(
    store: Store, payload: dict, progress, provider: Provider | None = None
) -> dict:
    symbols = validate_symbols(payload["symbols"])
    start, end = (
        date.fromisoformat(payload["start"]),
        date.fromisoformat(payload["end"]),
    )
    latest = calendar.latest_complete()
    if start < date(2016, 1, 4) or end > latest or start >= end:
        raise ResearchError(
            f"Choose dates from 2016-01-04 through the latest completed session, {latest}."
        )
    expected = calendar.sessions(start, end)
    if len(expected) * len(symbols) > 80000:
        raise ResearchError(
            "This request exceeds 80,000 daily bars. Reduce the period or stock list."
        )
    api = provider or Provider(store)
    try:
        securities = []
        for index, symbol in enumerate(symbols):
            progress(
                2 + round(index / len(symbols) * 15), f"Checking US listing: {symbol}"
            )
            asset = api.get(
                "alpaca", PAPER_URL + "/v2/assets/" + quote(symbol, safe=""), ttl=86400
            )
            if (
                asset.get("class") != "us_equity"
                or asset.get("exchange")
                not in ("NYSE", "NASDAQ", "AMEX", "ARCA", "BATS", "NYSEARCA")
                or asset.get("status") != "active"
            ):
                raise ResearchError(
                    f"{symbol} is not a supported active US exchange listing. It was not silently removed."
                )
            import re

            if symbol != "SPY" and re.search(
                r"\b(ETF|ETN|Fund|iShares|SPDR)\b", asset.get("name", ""), re.IGNORECASE
            ):
                raise ResearchError(
                    f"{symbol} appears to be a fund, rather than an ordinary company listing. SPY is reserved for the benchmark."
                )
            securities.append(
                {
                    k: asset.get(k)
                    for k in (
                        "id",
                        "symbol",
                        "name",
                        "exchange",
                        "tradable",
                        "fractionable",
                    )
                }
            )
        # Date-only end parameters are midnight, so explicitly include the entire
        # last NY session, while staying outside the latest 15-minute SIP window.
        query = {
            "symbols": ",".join(symbols),
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
        bar_pages = api.pages("/v2/stocks/bars", query, "bars")
        bars: dict[str, dict[date, Bar]] = {s: {} for s in symbols}
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
                    if day not in expected:
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
                        available_at=calendar.available_time(day),
                    )
        progress(40, "Checking split and dividend events")
        action_pages = api.pages(
            "/v1/corporate-actions",
            {
                "symbols": ",".join(symbols),
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
            if symbol is None or not start <= day <= end or kind == "name_changes":
                continue
            if kind not in ("forward_splits", "reverse_splits", "cash_dividends"):
                raise ResearchError(
                    f"{symbol} has an unsupported {kind.replace('_', ' ')} on {day}. Choose a supported period; the event cannot be ignored."
                )
            if day not in bars[symbol]:
                raise ResearchError(
                    f"Missing {symbol} bar on corporate-action date {day}."
                )
            bar = bars[symbol][day]
            if kind == "cash_dividends":
                if (
                    (event.get("foreign") and event.get("currency") != "USD")
                    or event.get("due_bill_on_date")
                    or event.get("due_bill_off_date")
                    or event.get("currency") not in (None, "", "USD")
                ):
                    raise ResearchError(
                        f"{symbol} has a foreign/special/due-bill dividend requiring separate accounting. It was not treated as an ordinary USD dividend."
                    )
                if not event.get("payable_date"):
                    raise ResearchError(
                        f"{symbol} dividend on {day} lacks a pay date. Cash timing cannot be guessed."
                    )
                pay = date.fromisoformat(event["payable_date"])
                if bar.dividend and bar.pay_date != pay:
                    raise ResearchError(
                        "Same-day dividends have different pay dates; separate entitlements are required."
                    )
                bars[symbol][day] = replace(
                    bar, dividend=bar.dividend + decimal(event["rate"]), pay_date=pay
                )
            else:
                old, new = decimal(event["old_rate"]), decimal(event["new_rate"])
                if old <= ZERO or new <= ZERO:
                    raise ResearchError("Split ratios must be positive.")
                bars[symbol][day] = replace(bar, split=bar.split * new / old)
            applied.append(event)
        progress(65, "Cross-checking action adjustments and missing sessions")
        # Compare the raw/split-adjusted factor change with the independently
        # returned split event. This catches wrong units and missing split rows.
        split_pages = api.pages(
            "/v2/stocks/bars", {**query, "adjustment": "split"}, "bars"
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
            if not rows:
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
                lower = (current_adjusted - half_cent) / (previous_adjusted + half_cent)
                upper = (current_adjusted + half_cent) / (previous_adjusted - half_cent)
                expected_return = current.close * current.split / before.close
                if (
                    not lower - Decimal("0.00000001")
                    <= expected_return
                    <= upper + Decimal("0.00000001")
                ):
                    raise ResearchError(
                        f"Split/action disagreement for {symbol} on {current.session}. No dataset was published."
                    )
            missing = sorted(set(expected) - bars[symbol].keys())
            health.append(
                {
                    "symbol": symbol,
                    "rows": len(rows),
                    "expected": len(expected),
                    "missing_count": len(missing),
                    "missing_examples": [str(d) for d in missing[:10]],
                    "start": str(rows[0].session),
                    "end": str(rows[-1].session),
                }
            )
        provenance = {
            "contract": "alpaca-raw-v1",
            "normalizer_version": "1.0.0",
            "sectors": {s: SECTORS.get(s, "Unknown") for s in symbols},
            "bar_pages": bar_pages,
            "actions": action_pages,
            "split_pages": split_pages,
            "securities": securities,
            "query": query,
        }
        raw = json.dumps(provenance, sort_keys=True, separators=(",", ":")).encode()
        digest = hashlib.sha256(raw).hexdigest()
        metadata = {
            "provider": "alpaca",
            "feed": "sip",
            "price_basis": "as_traded",
            "identity_asof": str(latest),
            "retrieved_at": now(),
            "securities": securities,
            "coverage": health,
            "action_count": len(applied),
            "observation_ids": api.observations,
            "download": {"symbols": symbols, "start": str(start), "end": str(end)},
            "universe": "Current fixed watchlist; historical membership/delistings not certified",
            "sector_basis": "Static research labels; Unknown for unmapped custom names",
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
            {s: SECTORS.get(s, "Unknown") for s in symbols},
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
        if any(h["missing_count"] for h in health):
            warnings.append(
                "Some symbols have missing sessions. Signal warm-up excludes incomplete history; a missing held price stops a backtest."
            )
        progress(95, "Saving the immutable market snapshot")
        return store.save_dataset(dataset, raw, warnings)
    finally:
        if provider is None:
            api.close()
