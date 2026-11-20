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
    research_dividend: Decimal = ZERO
    research_distribution: Decimal = ZERO

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
        if any(
            not v.is_finite() or v < ZERO
            for v in (self.research_dividend, self.research_distribution)
        ):
            raise ResearchError(
                "Research distributions must be finite and nonnegative."
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
class AnnualStatement:
    symbol: str
    cik: str
    start: date
    end: date
    filed: date
    available_at: datetime
    accession: str
    form: str
    assets: Decimal | None
    gross_profit: Decimal | None
    eps: Decimal | None
    eps_compatible: bool
    sources: dict[str, str] = field(default_factory=dict)
    issues: tuple[str, ...] = ()


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
    fundamentals: dict[str, tuple[AnnualStatement, ...]] = field(default_factory=dict)
    annual_income: dict[str, list[dict]] = field(default_factory=dict)


@dataclass(frozen=True)
class Policy:
    positions: int = 25
    max_weight: Decimal = Decimal("0.05")
    sector_cap: Decimal = Decimal("0.25")
    cash_reserve: Decimal = Decimal("0.02")
    slippage_bps: Decimal = Decimal("5")
    fee_bps: Decimal = Decimal("1")
    cost_model: Literal["fixed", "liquidity-v1"] = "fixed"

    def __post_init__(self):
        if self.cost_model not in ("fixed", "liquidity-v1"):
            raise ResearchError("Unknown trading cost model.")
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


def backtest_policy(profile: Literal["standard", "higher"] = "standard") -> Policy:
    return Policy(
        slippage_bps=Decimal("15") if profile == "higher" else Decimal("5"),
        cost_model="liquidity-v1",
    )


@dataclass(frozen=True)
class RankedStock:
    symbol: str
    score: float
    sector: str
    components: dict = field(default_factory=dict)


@dataclass
class Portfolio:
    cash: Decimal
    positions: dict[str, Decimal] = field(default_factory=dict)
    receivables: list[tuple[date, Decimal]] = field(default_factory=list)
    research_income: list[tuple[str, Decimal]] = field(default_factory=list)
    research_income_value: Decimal = ZERO

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
            + self.research_income_value
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
        "version": "1.0.0",
        "name": "Profitability / Quality",
        "category": "Fundamental",
        "description": "Favor businesses that turn their resources into profits.",
        "risk": "Strong businesses can be expensive; accounting differs by industry.",
        "inputs": "SEC annual gross profit / year-end assets, positive only; 20 complete price sessions. US-GAAP 10-K filings, available conservatively after filing.",
        "definition": "Rank positive annual gross profit divided by fiscal year-end assets, highest first. Revenue minus cost of revenue is used only when matched to the same filing and annual period. This is a profitability signal, not the full academic Quality Minus Junk portfolio.",
        "implemented": True,
    },
    {
        "id": "quality_value",
        "version": "1.0.0",
        "name": "Quality Value",
        "category": "Fundamental",
        "description": "Combine inexpensive valuation with business profitability.",
        "risk": "Cheap companies can stay cheap or deteriorate further.",
        "inputs": "SEC annual gross profit / assets and split-aware diluted EPS / decision close; 20 complete price sessions. Both factors must be positive.",
        "definition": "Equal blend of cross-sectional profitability and earnings-yield percentile ranks among stocks that qualify for both. Earnings yield is reported annual diluted EPS, adjusted for subsequent known splits, divided by the decision-session raw close. Missing factors never fall back to a single-factor strategy.",
        "implemented": True,
    },
    {
        "id": "value_momentum",
        "version": "1.0.1",
        "name": "Value + Momentum",
        "category": "Technical + fundamental",
        "description": "Combine what a business costs with how its stock is behaving.",
        "risk": "Value underperformance and momentum reversals can coincide.",
        "inputs": "SEC annual diluted EPS / decision close and 12–1 total-return momentum; 253 complete price sessions. Both factors must be positive.",
        "definition": "Equal blend of cross-sectional earnings-yield and 12–1 momentum percentile ranks among stocks that qualify for both. Uses annual reported diluted EPS with explicit split adjustments, not current vendor ratios. Missing or nonpositive components exclude a stock; no single-factor fallback.",
        "implemented": True,
    },
    {
        "id": "liquidity_weighted_momentum",
        "version": "1.0.0",
        "name": "Liquidity-Weighted Momentum",
        "category": "Technical",
        "description": "Favor liquid stocks with strong six- and twelve-month trends relative to their daily volatility.",
        "risk": "Momentum can reverse quickly. The liquidity screen can concentrate exposure in heavily traded stocks.",
        "inputs": "253 complete daily closes, split and cash distribution events, and recent daily share volume.",
        "definition": "Screen for the 100 stocks with highest median dollar volume over the latest 20 sessions, using at least 10 positive-volume sessions. Rank by the average of six- and twelve-month total returns divided by their respective annualized daily volatilities. Both windows end 21 sessions before the decision. Select the top 25 positive scores and size each position in proportion to the square root of median dollar volume, subject to the usual stock, sector and cash limits.",
        "implemented": True,
        "weight_by_liquidity": True,
    },
    {
        "id": "profitable_liquidity_leaders",
        "version": "1.0.0",
        "name": "Profitable Liquidity Leaders",
        "category": "Technical + fundamental",
        "description": "Own actively traded stocks that have positive annual net income and are in an uptrend.",
        "risk": "An established uptrend can reverse between month-end rebalances. Reported net income can include one-time gains.",
        "inputs": "Comparable annual SEC net income, 253 complete daily bars, volume and corporate actions.",
        "definition": "At month end, require positive net income in the latest comparable annual report and a total-return level above its 200-session average. Rank eligible stocks by median dollar volume over 20 sessions. Use the most liquid eligible share class per issuer. Weight up to 25 names by the square root of median dollar volume, subject to the stock, sector and cash limits.",
        "implemented": True,
        "weight_by_liquidity": True,
        "requires_annual_income": True,
        "frequency": "monthly",
    },
    {
        "id": "session_strength_liquidity",
        "version": "1.0.0",
        "name": "Session Strength and Liquidity",
        "category": "Technical + fundamental",
        "description": "Combine filed earnings, liquidity, regular-session strength and overnight follow-through.",
        "risk": "The rule was selected on the historical study period. Forward performance is untested.",
        "inputs": "Comparable annual SEC net income, 253 complete daily bars for stocks and SPY, volume and corporate actions.",
        "definition": "Start with the 100 most liquid stocks and require positive filed annual net income. Score median dollar volume (55%), 84-session regular-session strength versus SPY (35%), and 63-session overnight follow-through (10%). Follow-through counts days when both relative returns were positive. Select one listing per issuer and up to five stocks per sector. Rebalance at the next open after month end using square-root dollar-volume weights and the shared portfolio limits.",
        "implemented": True,
        "requires_annual_income": True,
        "weight_by_liquidity": True,
        "frequency": "monthly",
        "calendar_year_comparison": True,
    },
    {
        "id": "earnings_market_regime",
        "version": "1.0.0",
        "name": "Earnings and Market Regime Rotation",
        "category": "Technical + fundamental",
        "description": "Switch stock-selection rules as SPY’s short and medium trends change.",
        "risk": "The rule was selected on the historical study period. Its yearly record is sensitive to the short market lookback. Forward performance is untested.",
        "inputs": "Comparable annual SEC net income and prior-year net income, 253 complete daily bars for stocks and SPY, volume and corporate actions.",
        "definition": "Test whether SPY is above its 100-session average and whether its 21-session return is positive. With neither condition, rank earnings improvement relative to beginning assets among 100 liquid stocks and weight equally. With one condition, blend liquidity and 63-session strength for stocks above their 200-session average. With both, blend liquidity and 252-session strength for profitable stocks. The mixed and strong rules use square-root dollar-volume weights. Rebalance at the next open after month end.",
        "implemented": True,
        "requires_annual_income": True,
        "weight_by_liquidity": True,
        "frequency": "monthly",
        "calendar_year_comparison": True,
    },
]

STRATEGIES.extend(
    {
        **recipe,
        "id": f"{recipe['id']}_weekly",
        "name": f"{recipe['name']} · Weekly",
        "version": "1.0.0",
        "variant_of": recipe["id"],
        "frequency": "weekly",
        "risk": recipe["risk"].replace("month-end rebalances", "weekly rebalances"),
        "definition": recipe["definition"]
        .replace("At month end", "After the final trading session of the week")
        .replace("after month end", "after the final trading session of the week"),
    }
    for recipe in tuple(STRATEGIES)
    if recipe["id"]
    in {
        "profitable_liquidity_leaders",
        "session_strength_liquidity",
        "earnings_market_regime",
    }
)


ARCHIVED_STRATEGIES = frozenset({"quality", "quality_value"})


def strategy(identifier: str) -> dict:
    match = next((item for item in STRATEGIES if item["id"] == identifier), None)
    if match is None:
        raise ResearchError("Choose a strategy from the research library.")
    if not match["implemented"]:
        raise ResearchError(
            "This strategy requires the point-in-time fundamentals milestone. It cannot be run with price-only inputs."
        )
    return match


def runnable_strategy(identifier: str) -> dict:
    recipe = strategy(identifier)
    if identifier in ARCHIVED_STRATEGIES:
        raise ResearchError(
            f"{recipe['name']} is archived. Choose an available strategy for new research or paper trading."
        )
    return recipe


def paper_strategy(identifier: str) -> dict:
    recipe = runnable_strategy(identifier)
    if recipe.get("research_only"):
        raise ResearchError(f"{recipe['name']} is available for research only.")
    return recipe
