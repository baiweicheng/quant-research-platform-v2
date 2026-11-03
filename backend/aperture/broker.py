"""Paper-only Alpaca adapter. Reads may retry; order writes never retry blindly."""

from datetime import UTC, date, datetime, timedelta
from urllib.parse import quote
from zoneinfo import ZoneInfo

import httpx

from . import calendar
from .config import DATA_URL, PAPER_URL, settings
from .domain import ZERO, ResearchError, decimal

NY = ZoneInfo("America/New_York")
TERMINAL = {"filled", "canceled", "expired", "rejected", "replaced"}


class ReconciliationPending(ResearchError):
    """A moving account must be read again before any new order."""


class Broker:
    def __init__(self, client=None, cfg=None):
        self.client = client or httpx.Client(timeout=20, follow_redirects=False)
        self.owned = client is None
        self.cfg = cfg or settings()

    def close(self):
        if self.owned:
            self.client.close()

    def read(self, path, params=None, missing=False, data=False):
        if not path.startswith("/v2/"):
            raise ResearchError("Only supported paper/data resources are allowed.")
        for attempt in range(3):
            try:
                r = self.client.get(
                    (DATA_URL if data else PAPER_URL) + path,
                    params=params,
                    headers=self.cfg.headers(),
                )
            except httpx.RequestError:
                if attempt < 2:
                    continue
                raise ResearchError(
                    "Paper broker could not be reached. No order was retried."
                ) from None
            if r.status_code == 404 and missing:
                return None
            if r.status_code in (429, 500, 502, 503, 504) and attempt < 2:
                continue
            if not r.is_success:
                raise ResearchError(
                    f"Paper broker returned HTTP {r.status_code}. Check access and retry reconciliation."
                )
            try:
                return r.json()
            except ValueError:
                raise ResearchError(
                    "Paper broker returned an unreadable response."
                ) from None
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

    def snapshot(self, at=None):
        at = at or datetime.now(UTC)
        account = self.read("/v2/account")
        positions = self.read("/v2/positions")
        orders = self.read(
            "/v2/orders", {"status": "open", "limit": 500, "nested": "false"}
        )
        clock = self.read("/v2/clock")
        activities = self.activities((at - timedelta(days=10)).date().isoformat())
        if (
            not isinstance(positions, list)
            or not isinstance(orders, list)
            or len(orders) >= 500
        ):
            raise ResearchError(
                "The complete position/open-order list could not be reconciled."
            )
        # Read again around the collection to detect a concurrent fill or transfer.
        after = self.read("/v2/account")
        for key in ("cash",):
            if decimal(account.get(key, "NaN")) != decimal(after.get(key, "NaN")):
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
        if (
            cash < ZERO
            or equity <= ZERO
            or decimal(account.get("short_market_value", "0")) != ZERO
        ):
            issues.append(
                "This account has borrowing, short exposure or nonpositive equity. Resolve it at the broker first."
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
        # Neither account buying_power nor margin multipliers can fund this planner.
        nonmargin = decimal(account.get("non_marginable_buying_power", cash))
        spendable = max(ZERO, min(cash, nonmargin) - unsettled - funding_reserve)
        if any(
            a.get("activity_type")
            in ("JNLS", "JNLT", "ACATC", "ACATS", "MA", "REORG", "SSO")
            for a in activities
        ):
            issues.append(
                "Recent journal/asset-transfer activity needs manual broker review before new paper orders."
            )
        import hashlib

        binding = hashlib.sha256(str(account.get("id", "")).encode()).hexdigest()
        if not account.get("id"):
            raise ResearchError("Paper account identity is missing.")
        return {
            "account_key": binding,
            "source": "Alpaca paper broker",
            "checked_at": at.isoformat(),
            "cash": str(cash),
            "equity": str(equity),
            "spendable_cash": str(spendable),
            "unsettled_sales": str(unsettled),
            "recent_funding_reserve": str(funding_reserve),
            "positions": clean,
            "open_orders": orders,
            "clock": clock,
            "issues": issues,
            "account_type": "Paper account; margin buying power is ignored",
            "settlement_policy": "Conservative T+1 sale-proceeds exclusion; broker restrictions can be stricter.",
        }

    def asset(self, symbol):
        a = self.read("/v2/assets/" + quote(symbol, safe=""))
        if (
            a.get("class") != "us_equity"
            or a.get("status") != "active"
            or not a.get("tradable")
            or not a.get("fractionable")
        ):
            raise ResearchError(
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
        clock = self.read("/v2/clock")
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

    def submit(self, payload):
        """Exactly one HTTP attempt; timeout/server errors are ambiguous, never absent."""
        try:
            r = self.client.post(
                PAPER_URL + "/v2/orders", json=payload, headers=self.cfg.headers()
            )
        except httpx.RequestError:
            return None, "unknown"
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
        try:
            r = self.client.delete(
                PAPER_URL + "/v2/orders/" + quote(broker_id, safe=""),
                headers=self.cfg.headers(),
            )
        except httpx.RequestError:
            raise ResearchError(
                "Cancellation outcome is uncertain. Reconcile; do not assume the order stopped."
            ) from None
        if r.status_code not in (200, 204, 404, 422):
            raise ResearchError(
                f"Cancellation returned HTTP {r.status_code}. Reconcile the actual order state."
            )
