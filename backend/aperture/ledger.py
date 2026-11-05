"""A deterministic simulation ledger, independent from signal calculation."""

from datetime import date
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP

from .domain import Bar, CENT, ONE, SHARE, ZERO, Policy, Portfolio, ResearchError


def apply_actions(
    portfolio: Portfolio,
    day: date,
    bars: dict[str, Bar],
    dividend_model="pay_date",
    opening_income=None,
) -> None:
    """Apply splits and accrue only overnight holders' dividend entitlements."""
    for symbol, quantity in list(portfolio.positions.items()):
        if quantity <= ZERO:
            continue
        if symbol not in bars:
            raise ResearchError(
                f"Missing {symbol} price on {day}. A held stock cannot be silently removed or exited at an assumed price."
            )
        bar = bars[symbol]
        quantity *= bar.split
        portfolio.positions[symbol] = quantity
        if dividend_model == "ex_date":
            amount = (bar.research_dividend or bar.dividend) + bar.research_distribution
            if amount:
                portfolio.research_income.append((symbol, quantity * amount))
                # Value entitlements at the execution-time opening mark, never
                # the child's future closing price; income is not spendable.
                portfolio.research_income_value += quantity * (
                    (bar.research_dividend or bar.dividend)
                    + (opening_income or {}).get(symbol, ZERO)
                )
        elif bar.dividend:
            portfolio.receivables.append((bar.pay_date, quantity * bar.dividend))
    paid = sum(
        (amount for pay_day, amount in portfolio.receivables if pay_day <= day), ZERO
    )
    portfolio.cash += paid
    portfolio.receivables = [
        (pay_day, amount) for pay_day, amount in portfolio.receivables if pay_day > day
    ]


def reinvest_research_income(portfolio, day, bars):
    """Closing-price research convention, never cash available at that day's open."""
    for symbol, amount in portfolio.research_income:
        if portfolio.positions.get(symbol, ZERO) > ZERO and symbol in bars:
            shares = (amount / bars[symbol].close).quantize(SHARE, rounding=ROUND_DOWN)
            portfolio.positions[symbol] += shares
            portfolio.cash += amount - shares * bars[symbol].close
        else:
            portfolio.cash += amount
    portfolio.research_income.clear()
    portfolio.research_income_value = ZERO


def fee(notional: Decimal, policy: Policy) -> Decimal:
    return (notional * policy.fee_bps / 10000).quantize(CENT, rounding=ROUND_HALF_UP)


def buy(
    portfolio: Portfolio,
    symbol: str,
    opening: Decimal,
    budget: Decimal,
    policy: Policy,
    day: date,
) -> dict | None:
    budget = min(budget, portfolio.cash)
    if budget < ONE:
        return None
    price = opening * (ONE + policy.slippage_bps / 10000)
    quantity = ((budget - CENT) / (price * (ONE + policy.fee_bps / 10000))).quantize(
        SHARE, rounding=ROUND_DOWN
    )
    if quantity <= ZERO:
        return None
    notional = quantity * price
    commission = fee(notional, policy)
    if notional + commission > budget:
        raise ResearchError(
            "The simulated buy exceeds its reserved cash. No result was saved."
        )
    portfolio.cash -= notional + commission
    portfolio.positions[symbol] = portfolio.positions.get(symbol, ZERO) + quantity
    return {
        "session": str(day),
        "symbol": symbol,
        "side": "Buy",
        "quantity": str(quantity),
        "price": str(price),
        "notional": str(notional),
        "fee": str(commission),
    }


def sell(
    portfolio: Portfolio,
    symbol: str,
    opening: Decimal,
    quantity: Decimal,
    policy: Policy,
    day: date,
) -> dict | None:
    held = portfolio.positions.get(symbol, ZERO)
    quantity = min(quantity, held)
    if quantity <= ZERO:
        return None
    # A full exit preserves any corporate-action fraction instead of stranding dust.
    if quantity < held:
        quantity = quantity.quantize(SHARE, rounding=ROUND_DOWN)
    if quantity <= ZERO:
        return None
    price = opening * (ONE - policy.slippage_bps / 10000)
    notional = quantity * price
    commission = fee(notional, policy)
    portfolio.cash += notional - commission
    remaining = held - quantity
    if remaining:
        portfolio.positions[symbol] = remaining
    else:
        portfolio.positions.pop(symbol, None)
    return {
        "session": str(day),
        "symbol": symbol,
        "side": "Sell",
        "quantity": str(quantity),
        "price": str(price),
        "notional": str(notional),
        "fee": str(commission),
    }


def rebalance(
    portfolio: Portfolio,
    targets: dict[str, Decimal],
    bars: dict[str, Bar],
    policy: Policy,
    day: date,
) -> list[dict]:
    """Execute yesterday's target weights using this session's opening prices.

    This is a next-open simulation, not a guarantee of opening-auction fills.
    No signal receives these opening prices. The fill stage checks actual cash.
    """
    openings = {symbol: bar.open for symbol, bar in bars.items()}
    missing = set(targets) - openings.keys()
    if missing:
        raise ResearchError(
            f"Missing execution prices on {day}: {', '.join(sorted(missing))}."
        )
    equity = portfolio.value(openings)
    # Bound a full sell-and-buy cycle's modeled costs and fee rounding. Hard caps
    # are not relaxed just because costs reduce the equity denominator.
    buffer = equity * 2 * (policy.fee_bps + policy.slippage_bps) / 10000 + CENT * (
        len(targets) + len(portfolio.positions)
    )
    sizing_value = max(ZERO, equity - buffer)
    trades: list[dict] = []
    for symbol, quantity in sorted(list(portfolio.positions.items())):
        price = openings[symbol]
        desired = targets.get(symbol, ZERO) * sizing_value
        excess = quantity * price - desired
        if excess > ZERO:
            record = sell(
                portfolio,
                symbol,
                price,
                quantity if desired == ZERO else excess / price,
                policy,
                day,
            )
            if record:
                trades.append(record)
    for symbol, weight in sorted(targets.items()):
        difference = (
            weight * sizing_value
            - portfolio.positions.get(symbol, ZERO) * openings[symbol]
        )
        usable = max(ZERO, portfolio.cash - equity * policy.cash_reserve)
        record = buy(
            portfolio, symbol, openings[symbol], min(difference, usable), policy, day
        )
        if record:
            trades.append(record)
    if portfolio.cash < ZERO or any(
        quantity < ZERO for quantity in portfolio.positions.values()
    ):
        raise ResearchError(
            "The simulated portfolio violated its no-borrowing constraint."
        )
    return trades
