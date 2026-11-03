"""Small immutable financial contracts; monetary accounting uses Decimal."""

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Literal

ZERO = Decimal("0")
ONE = Decimal("1")
CENT = Decimal("0.01")
SHARE = Decimal("0.000001")


class ResearchError(ValueError):
    """An actionable domain failure safe to display in the interface."""


def decimal(value: object, label: str = "Value") -> Decimal:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ResearchError(f"{label} must be a finite number.") from None
    if not number.is_finite():
        raise ResearchError(f"{label} must be a finite number.")
    return number


@dataclass(frozen=True)
class Bar:
    symbol: str
    session: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    split: Decimal = ONE
    dividend: Decimal = ZERO
    pay_date: date | None = None
    available_at: datetime | None = None

    def __post_init__(self):
        prices = (self.open, self.high, self.low, self.close)
        if any(not value.is_finite() or value <= ZERO for value in prices):
            raise ResearchError(
                f"{self.symbol} {self.session}: prices must be positive and finite."
            )
        if (
            self.low > min(self.open, self.close)
            or self.high < max(self.open, self.close)
            or self.low > self.high
        ):
            raise ResearchError(
                f"{self.symbol} {self.session}: OHLC prices are inconsistent."
            )
        if self.volume < 0 or not self.split.is_finite() or self.split <= ZERO:
            raise ResearchError(
                f"{self.symbol} {self.session}: invalid volume or split ratio."
            )
        if not self.dividend.is_finite() or self.dividend < ZERO:
            raise ResearchError(
                f"{self.symbol} {self.session}: dividends cannot be negative."
            )
        if self.dividend > ZERO and (
            self.pay_date is None or self.pay_date < self.session
        ):
            raise ResearchError(
                f"{self.symbol} {self.session}: a dividend needs a pay date on or after its ex-date."
            )
        if self.available_at is not None and self.available_at.tzinfo is None:
            raise ResearchError(
                "Price availability timestamps must include a timezone."
            )


@dataclass(frozen=True)
class Dataset:
    id: str
    name: str
    kind: Literal["imported", "synthetic"]
    revision: int
    bars: dict[str, tuple[Bar, ...]]
    sectors: dict[str, str]
    source: str
    digest: str
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Policy:
    positions: int = 25
    max_weight: Decimal = Decimal("0.05")
    sector_cap: Decimal = Decimal("0.25")
    cash_reserve: Decimal = Decimal("0.02")
    slippage_bps: Decimal = Decimal("5")
    fee_bps: Decimal = Decimal("1")

    def __post_init__(self):
        for name in (
            "max_weight",
            "sector_cap",
            "cash_reserve",
            "slippage_bps",
            "fee_bps",
        ):
            if not getattr(self, name).is_finite():
                raise ResearchError("Risk limits and costs must be finite numbers.")
        if not 1 <= self.positions <= 100:
            raise ResearchError("Choose between 1 and 100 positions.")
        if not ZERO < self.max_weight <= ONE or not ZERO < self.sector_cap <= ONE:
            raise ResearchError(
                "Position and sector limits must be above zero and at most 100%."
            )
        if not ZERO <= self.cash_reserve < ONE:
            raise ResearchError("The cash reserve must be between 0% and 99%.")
        if not ZERO <= self.slippage_bps <= Decimal(
            "500"
        ) or not ZERO <= self.fee_bps <= Decimal("500"):
            raise ResearchError(
                "Trading cost assumptions must be between 0 and 500 basis points."
            )


@dataclass(frozen=True)
class RankedStock:
    symbol: str
    score: float
    sector: str


@dataclass
class Portfolio:
    cash: Decimal
    positions: dict[str, Decimal] = field(default_factory=dict)
    receivables: list[tuple[date, Decimal]] = field(default_factory=list)

    def value(self, prices: dict[str, Decimal]) -> Decimal:
        missing = [
            symbol
            for symbol, quantity in self.positions.items()
            if quantity > ZERO and symbol not in prices
        ]
        if missing:
            raise ResearchError(
                "Cannot value held stocks without a price: "
                + ", ".join(sorted(missing))
            )
        return (
            self.cash
            + sum(
                (
                    quantity * prices[symbol]
                    for symbol, quantity in self.positions.items()
                ),
                ZERO,
            )
            + sum((amount for _, amount in self.receivables), ZERO)
        )


STRATEGIES = [
    {
        "id": "momentum",
        "version": "1.0.0",
        "name": "12–1 Momentum",
        "category": "Technical",
        "description": "Rank persistent price winners over 12 months, excluding the latest month.",
        "risk": "Sharp reversals can unwind recent winners quickly.",
        "inputs": "253 complete trading sessions, split and dividend events.",
        "implemented": True,
    },
    {
        "id": "low_volatility",
        "version": "1.0.0",
        "name": "Defensive Low Volatility",
        "category": "Technical",
        "description": "Favor stocks with steadier daily total returns over the past year.",
        "risk": "Can lag strongly rising markets and still lose money.",
        "inputs": "253 complete trading sessions, split and dividend events.",
        "implemented": True,
    },
    {
        "id": "quality",
        "version": "pending",
        "name": "Profitability / Quality",
        "category": "Fundamental",
        "description": "Favor businesses that turn their resources into profits.",
        "risk": "Strong businesses can be expensive; accounting differs by industry.",
        "inputs": "Verified point-in-time financial statements.",
        "implemented": False,
    },
    {
        "id": "quality_value",
        "version": "pending",
        "name": "Quality Value",
        "category": "Fundamental",
        "description": "Combine inexpensive valuation with business profitability.",
        "risk": "Cheap companies can stay cheap or deteriorate further.",
        "inputs": "Point-in-time statements and historical valuation denominators.",
        "implemented": False,
    },
    {
        "id": "value_momentum",
        "version": "pending",
        "name": "Value + Momentum",
        "category": "Technical + fundamental",
        "description": "Combine what a business costs with how its stock is behaving.",
        "risk": "Value underperformance and momentum reversals can coincide.",
        "inputs": "Validated fundamental history plus price momentum.",
        "implemented": False,
    },
]


def strategy(identifier: str) -> dict:
    match = next((item for item in STRATEGIES if item["id"] == identifier), None)
    if match is None:
        raise ResearchError("Choose a strategy from the research library.")
    if not match["implemented"]:
        raise ResearchError(
            "This strategy requires the point-in-time fundamentals milestone. It cannot be run with price-only inputs."
        )
    return match
