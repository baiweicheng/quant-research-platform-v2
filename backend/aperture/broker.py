"""Paper-only Alpaca adapter. Reads may retry; order writes never retry blindly."""

import fcntl
import hashlib
import os
import tempfile
import time
from datetime import UTC, date, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

import httpx

from . import calendar
from .config import DATA_URL, PAPER_URL, settings
from .domain import ZERO, ResearchError, decimal

NY = ZoneInfo("America/New_York")
TERMINAL = {
    "filled",
    "canceled",
    "expired",
    "rejected",
    "replaced",
    "not_sent",
    "closed_unconfirmed",
}
CORPORATE_ACTIVITY = {"MA", "NC", "REORG", "SC", "SSO", "SSP"}
CASH_ADJUSTMENT_ACTIVITY = {
    "CGD",
    "CIL",
    "DIV",
    "DIVCGL",
    "DIVCGS",
    "DIVFEE",
    "DIVFT",
    "DIVNRA",
    "DIVROC",
    "DIVTXEX",
    "FEE",
    "INT",
    "INTNRA",
    "INTTW",
    "PTC",
    "PTR",
}


class ReconciliationPending(ResearchError):
    """A moving account must be read again before any new order."""


class SubmissionNotSent(ResearchError):
    """A local guard prevented the POST from being attempted."""


class AssetIneligible(ResearchError):
    """The broker confirmed that a symbol cannot be traded fractionally."""


class TradingPace:
    """Share the request budget across the API, worker and cancellation lane."""

    def __init__(self, key):
        digest = hashlib.sha256(key.encode()).hexdigest()
        self.path = (
            Path(tempfile.gettempdir()) / f"aperture-paper-{os.getuid()}-{digest}.pace"
        )

    def _slot(self, now, delay, *, defer=False):
        fd = os.open(self.path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "r+") as slot:
            fcntl.flock(slot, fcntl.LOCK_EX)
            previous = float(slot.read() or 0)
            if defer or previous <= now:
                slot.seek(0)
                slot.write(str(max(previous, now + delay)))
                slot.truncate()
                slot.flush()
            return max(0, previous - now)

    def acquire(self):
        limit = time.time() + 4
        while True:
            now = time.time()
            delay = self._slot(now, 0.36)
            if not delay:
                return
            if now + delay > limit:
                raise ReconciliationPending(
                    "Alpaca's request budget is temporarily unavailable. Wait for it to reset and refresh."
                )
            time.sleep(delay)

    def defer(self, delay):
        self._slot(time.time(), min(delay, 900), defer=True)


def retry_delay(response, attempt):
    retry_after = response.headers.get("Retry-After")
    if retry_after:
        try:
            return max(0.25, float(retry_after))
        except ValueError:
            try:
                return max(
                    0.25, parsedate_to_datetime(retry_after).timestamp() - time.time()
                )
            except (TypeError, ValueError, OverflowError):
                pass
    reset = response.headers.get("X-RateLimit-Reset")
    if response.status_code == 429 and reset:
        try:
            return max(0.25, float(reset) - time.time())
        except ValueError:
            pass
    return 0.5 * (2**attempt)


class Broker:
    def __init__(self, client=None, cfg=None):
        self.client = client or httpx.Client(timeout=20, follow_redirects=False)
        self.owned = client is None
        self.cfg = cfg or settings()
        self.pace = TradingPace(self.cfg.key)

    def close(self):
        if self.owned:
            self.client.close()

    def read(self, path, params=None, missing=False, data=False):
        if not path.startswith("/v2/"):
            raise ResearchError("Only supported paper/data resources are allowed.")
        headers = self.cfg.headers()
        for attempt in range(3):
            if not data:
                self.pace.acquire()
            try:
                r = self.client.get(
                    (DATA_URL if data else PAPER_URL) + path,
                    params=params,
                    headers=headers,
                )
            except httpx.RequestError:
                if attempt < 2:
                    time.sleep(0.5 * (2**attempt))
                    continue
                failure = ResearchError if data else ReconciliationPending
                raise failure(
                    "Paper broker could not be reached. No order was retried."
                ) from None
            if r.status_code == 404 and missing:
                return None
            if r.status_code in (429, 500, 502, 503, 504):
                delay = retry_delay(r, attempt)
                if r.status_code == 429 and not data:
                    self.pace.defer(delay)
                if attempt < 2 and delay <= 4:
                    time.sleep(delay)
                    continue
                if not data:
                    raise ReconciliationPending(
                        f"Paper broker temporarily returned HTTP {r.status_code}. Reconcile before continuing."
                    )
            if not r.is_success:
                raise ResearchError(
                    f"Paper broker returned HTTP {r.status_code}. Check access and retry reconciliation."
                )
            try:
                body = r.json()
            except ValueError:
                raise ResearchError(
                    "Paper broker returned an unreadable response."
                ) from None
            if missing and (not isinstance(body, dict) or not body):
                raise ResearchError(
                    "The broker returned an incomplete client-order lookup."
                )
            return body
        raise ResearchError("Paper read retries exhausted.")

    def activities(self, after):
        output, token = [], None
        for _ in range(500):
            params = {"after": after, "direction": "asc", "page_size": 100}
            if token:
                params["page_token"] = token
            rows = self.read("/v2/account/activities", params)
            if not isinstance(rows, list):
                raise ResearchError(
                    "Account activity format changed; reconciliation stopped."
                )
            output.extend(rows)
            if len(rows) < 100:
                return output
            next_token = rows[-1].get("id")
            if not next_token or next_token == token:
                break
            token = next_token
        raise ResearchError(
            "Account activity history exceeded its safety limit. No partial reconciliation was used."
        )

    def order_list(self, status, *, after=None):
        params = {"status": status, "limit": 500, "nested": "false"}
        if after:
            params["after"] = after
        output = []
        for _ in range(5):
            rows = self.read("/v2/orders", params)
            if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows):
                break
            output.extend(rows)
            if len(rows) < 500:
                return output
            cursor = rows[-1].get("id")
            if not cursor or cursor == params.get("before_order_id"):
                break
            params.pop("after", None)  # Alpaca's ID cursor supersedes the time filter.
            params["before_order_id"] = cursor
        raise ResearchError("The complete paper order list could not be reconciled.")

    @staticmethod
    def account_key(account):
        if not account.get("id"):
            raise ResearchError("Paper account identity is missing.")
        return hashlib.sha256(str(account["id"]).encode()).hexdigest()

    def clock(self):
        return self.read("/v2/clock")

    def staging_snapshot(self):
        # Between full checks, use the current broker cash, positions, buying
        # power and open orders. The frozen plan still caps usable cash.
        return self.snapshot(staging=True)

    def snapshot(self, at=None, *, staging=False):
        at = at or datetime.now(UTC)
        account = self.read("/v2/account")
        positions = self.read("/v2/positions")
        orders = self.order_list("open")
        clock = None if staging else self.clock()
        activities = (
            []
            if staging
            else self.activities((at - timedelta(days=10)).date().isoformat())
        )
        if not isinstance(positions, list):
            raise ResearchError(
                "The complete position/open-order list could not be reconciled."
            )
        # Read again around the collection to detect a concurrent fill or transfer.
        if not staging:
            after = self.read("/v2/account")
            if self.account_key(account) != self.account_key(after) or decimal(
                account.get("cash", "NaN")
            ) != decimal(after.get("cash", "NaN")):
                raise ReconciliationPending(
                    "The account changed during reconciliation. Refresh after pending activity settles."
                )
            after_positions = self.read("/v2/positions")
            if sorted((p.get("symbol"), p.get("qty")) for p in positions) != sorted(
                (p.get("symbol"), p.get("qty")) for p in after_positions
            ):
                raise ReconciliationPending(
                    "Positions changed during reconciliation; waiting for a stable account read."
                )
        cash = decimal(account.get("cash", "NaN"))
        equity = decimal(account.get("equity", "NaN"))
        issues = []
        if account.get("status") != "ACTIVE" or account.get("currency") != "USD":
            issues.append("Use an active USD paper account.")
        if any(
            account.get(k, False)
            for k in ("trading_blocked", "account_blocked", "trade_suspended_by_user")
        ):
            issues.append("The broker has blocked trading on this account.")
        if equity <= ZERO or decimal(account.get("short_market_value", "0")) != ZERO:
            issues.append(
                "This account has short exposure or nonpositive equity. Resolve it at the broker first."
            )
        clean = []
        for p in positions:
            qty = decimal(p.get("qty", "NaN"))
            if (
                qty <= ZERO
                or p.get("side") != "long"
                or p.get("asset_class") != "us_equity"
            ):
                issues.append(
                    f"{p.get('symbol', 'Position')}: only long US equities are supported."
                )
            clean.append(
                {
                    k: p.get(k)
                    for k in (
                        "symbol",
                        "qty",
                        "market_value",
                        "current_price",
                        "avg_entry_price",
                        "unrealized_pl",
                        "asset_class",
                        "side",
                    )
                }
            )
        unsettled = ZERO
        day = at.astimezone(NY).date()
        for a in activities:
            if a.get("activity_type") != "FILL" or a.get("side") != "sell":
                continue
            try:
                traded = (
                    datetime.fromisoformat(a["transaction_time"]).astimezone(NY).date()
                )
                settle = calendar.settlement_session(traded)
            except (KeyError, ValueError):
                raise ResearchError(
                    "A sell activity has no supported settlement date."
                ) from None
            if day < settle:
                unsettled += decimal(a["qty"]) * decimal(a["price"])
        # Cash deposits/journals are external funding, not an asset-transfer error.
        # Reserve positive same-session funding until the next exchange session.
        funding_reserve = ZERO
        for a in activities:
            if a.get("activity_type") not in ("CSD", "JNLC"):
                continue
            amount = decimal(a.get("net_amount", "NaN"))
            if amount <= ZERO:
                continue
            funded = date.fromisoformat(
                str(a.get("date") or a.get("transaction_time"))[:10]
            )
            if funded >= day:
                funding_reserve += amount
        # Preserve both measures. The explicitly approved funding policy decides
        # whether paper margin may fund orders; cash-only plans still ignore it.
        nonmargin = decimal(account.get("non_marginable_buying_power", cash))
        spendable = max(ZERO, min(cash, nonmargin) - unsettled - funding_reserve)
        if any(
            a.get("activity_type") in ("JNLS", "JNLT", "ACATC", "ACATS")
            for a in activities
        ):
            issues.append(
                "Recent journal/asset-transfer activity needs manual broker review before new paper orders."
            )
        return {
            "account_key": self.account_key(account),
            "source": "Alpaca paper broker",
            "checked_at": at.isoformat(),
            "cash": str(cash),
            "equity": str(equity),
            "spendable_cash": str(spendable),
            "buying_power": str(
                max(
                    ZERO,
                    min(
                        decimal(account.get("buying_power", cash)),
                        decimal(
                            account.get(
                                "regt_buying_power", account.get("buying_power", cash)
                            )
                        ),
                    ),
                )
            ),
            "margin_debit": str(max(ZERO, -cash)),
            "unsettled_sales": str(unsettled),
            "recent_funding_reserve": str(funding_reserve),
            "positions": clean,
            "open_orders": orders,
            "clock": clock,
            "issues": issues,
            "broker_activities": [
                {
                    key: a[key]
                    for key in (
                        "activity_type",
                        "id",
                        "date",
                        "net_amount",
                        "symbol",
                        "transaction_time",
                        "order_id",
                    )
                    if key in a
                }
                for a in activities
                if a.get("activity_type")
                in CORPORATE_ACTIVITY | CASH_ADJUSTMENT_ACTIVITY | {"FILL"}
            ],
            "account_type": "Paper account; funding follows the approved platform policy",
            "settlement_policy": "Conservative T+1 sale-proceeds exclusion; broker restrictions can be stricter.",
        }

    def asset(self, symbol):
        a = self.read("/v2/assets/" + quote(symbol, safe=""), missing=True)
        if (
            a is None
            or a.get("class") != "us_equity"
            or a.get("status") != "active"
            or not a.get("tradable")
            or not a.get("fractionable")
        ):
            raise AssetIneligible(
                f"{symbol}: an active, tradable, fractional US equity is required."
            )
        return a

    def price(self, symbol, side, at):
        data = self.read(
            "/v2/stocks/" + quote(symbol, safe="") + "/quotes/latest",
            {"feed": "iex"},
            data=True,
        )
        q = data.get("quote", {})
        try:
            stamp = datetime.fromisoformat(q["t"])
        except (KeyError, ValueError):
            raise ResearchError(
                f"{symbol}: a timestamped IEX quote is required."
            ) from None
        # Network/account reconciliation can outlast the caller's start time.
        # A quote newer than that start is valid; check at actual receipt.
        if not -2 <= (datetime.now(UTC) - stamp).total_seconds() <= 60:
            raise ReconciliationPending(
                f"{symbol}: quote is stale. Reconcile during regular market hours."
            )
        bid, ask = decimal(q.get("bp", 0)), decimal(q.get("ap", 0))
        if bid <= ZERO or ask < bid or (ask - bid) / ask > decimal(".02"):
            raise ReconciliationPending(
                f"{symbol}: quote is missing, crossed or wider than the 2% spread limit."
            )
        return ask if side == "buy" else bid

    def market_open(self):
        # Recheck at submission time; a slow reconciliation can cross the close.
        clock = self.clock()
        at = datetime.now(UTC)
        day = at.astimezone(NY).date()
        return (
            bool(clock.get("is_open"))
            and day in calendar.sessions(day, day)
            and calendar.open_time(day) <= at < calendar.close_time(day)
        )

    def find_order(self, client_id):
        return self.read(
            "/v2/orders:by_client_order_id",
            {"client_order_id": client_id},
            missing=True,
        )

    def cancellation_view(self):
        return self.account_key(self.read("/v2/account")), self.order_list("open")

    def submit(self, payload, *, before_send=None):
        """Exactly one HTTP attempt; timeout/server errors are ambiguous, never absent."""
        headers = self.cfg.headers()
        try:
            self.pace.acquire()
        except ReconciliationPending as error:
            raise SubmissionNotSent(str(error)) from error
        options = {}
        if before_send is not None:
            options["timeout"] = 5
            before_send()
        try:
            r = self.client.post(
                PAPER_URL + "/v2/orders", json=payload, headers=headers, **options
            )
        except httpx.RequestError:
            return None, "unknown"
        if r.status_code == 429:
            self.pace.defer(retry_delay(r, 0))
        if r.status_code >= 500 or r.status_code in (408, 409, 429):
            return None, "unknown"
        if not r.is_success:
            return {
                "status": "rejected",
                "reason": f"Broker rejected request (HTTP {r.status_code}).",
            }, "rejected"
        try:
            body = r.json()
        except ValueError:
            return None, "unknown"
        return body, "received"

    def cancel(self, broker_id):
        headers = self.cfg.headers()
        self.pace.acquire()
        try:
            r = self.client.delete(
                PAPER_URL + "/v2/orders/" + quote(broker_id, safe=""),
                headers=headers,
                timeout=5,
            )
        except httpx.RequestError:
            raise ResearchError(
                "Cancellation outcome is uncertain. Reconcile; do not assume the order stopped."
            ) from None
        if r.status_code == 429:
            self.pace.defer(retry_delay(r, 0))
        if r.status_code not in (200, 204, 404, 422):
            raise ResearchError(
                f"Cancellation returned HTTP {r.status_code}. Reconcile the actual order state."
            )
