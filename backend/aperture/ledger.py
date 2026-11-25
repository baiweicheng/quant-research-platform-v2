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
    fresh=None,
) -> Decimal:
    """Apply actions and return the value of cash dividends earned this session.

    Shares issued as merger consideration at today's effective time were not
    held at the prior close. They neither split again nor receive the
    recipient's same-day ex-date dividends or spin-off distributions.
    """
    dividends = ZERO
    for symbol, held in list(portfolio.positions.items()):
        if held <= ZERO:
            continue
        if symbol not in bars:
            raise ResearchError(
                f"Missing {symbol} price on {day}. A held stock cannot be silently removed or exited at an assumed price."
            )
        bar = bars[symbol]
        issued = min(held, (fresh or {}).get(symbol, ZERO))
        quantity = (held - issued) * bar.split
        portfolio.positions[symbol] = quantity + issued
        if dividend_model == "ex_date":
            cash_dividend = bar.research_dividend or bar.dividend
            dividends += quantity * cash_dividend
            amount = cash_dividend + bar.research_distribution
            if amount:
                portfolio.research_income.append((symbol, quantity * amount))
                # Value entitlements at the execution-time opening mark, never
                # the child's future closing price; income is not spendable.
                portfolio.research_income_value += quantity * (
                    cash_dividend + (opening_income or {}).get(symbol, ZERO)
                )
        elif bar.dividend:
            entitlement = quantity * bar.dividend
            dividends += entitlement
            portfolio.receivables.append((bar.pay_date, entitlement))
    paid = sum(
        (amount for pay_day, amount in portfolio.receivables if pay_day <= day), ZERO
    )
    portfolio.cash += paid
    portfolio.receivables = [
        (pay_day, amount) for pay_day, amount in portfolio.receivables if pay_day > day
    ]
    return dividends


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


def slippage_bps(policy, order_value, dollar_volume):
    if policy.cost_model == "fixed":
        return policy.slippage_bps
    if not dollar_volume:
        return policy.slippage_bps + 10
    # A scenario with 1% daily volatility and unit impact coefficient. Limit
    # the modeled rate at one full day's volume and flag large orders in results.
    rate = min(ONE, order_value / dollar_volume).sqrt() * 100
    return policy.slippage_bps + rate.quantize(Decimal("0.0001"))


def trade_record(
    day,
    symbol,
    side,
    quantity,
    price,
    commission,
    policy,
    opening,
    volume,
    rate,
    order_value,
):
    record = {
        "session": str(day),
        "symbol": symbol,
        "side": side,
        "quantity": str(quantity),
        "price": str(price),
        "notional": str(quantity * price),
        "fee": str(commission),
    }
    if policy.cost_model == "liquidity-v1":
        record.update(
            reference_open=str(opening),
            slippage_bps=str(rate),
            slippage_cost=str(quantity * abs(price - opening)),
            trailing_dollar_volume=str(volume) if volume else None,
            modeled_order_value=str(order_value),
        )
    return record


def buy(
    portfolio: Portfolio,
    symbol: str,
    opening: Decimal,
    budget: Decimal,
    policy: Policy,
    day: date,
    dollar_volume: Decimal | None = None,
) -> dict | None:
    budget = min(budget, portfolio.cash)
    if budget < ONE:
        return None
    rate = slippage_bps(policy, budget, dollar_volume)
    price = opening * (ONE + rate / 10000)
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
    return trade_record(
        day,
        symbol,
        "Buy",
        quantity,
        price,
        commission,
        policy,
        opening,
        dollar_volume,
        rate,
        budget,
    )


def sell(
    portfolio: Portfolio,
    symbol: str,
    opening: Decimal,
    quantity: Decimal,
    policy: Policy,
    day: date,
    dollar_volume: Decimal | None = None,
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
    rate = slippage_bps(policy, quantity * opening, dollar_volume)
    price = opening * (ONE - rate / 10000)
    notional = quantity * price
    commission = fee(notional, policy)
    portfolio.cash += notional - commission
    remaining = held - quantity
    if remaining:
        portfolio.positions[symbol] = remaining
    else:
        portfolio.positions.pop(symbol, None)
    return trade_record(
        day,
        symbol,
        "Sell",
        quantity,
        price,
        commission,
        policy,
        opening,
        dollar_volume,
        rate,
        quantity * opening,
    )


def rebalance(
    portfolio: Portfolio,
    targets: dict[str, Decimal],
    bars: dict[str, Bar],
    policy: Policy,
    day: date,
    dollar_volumes: dict[str, Decimal | None] | None = None,
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
    volumes = dollar_volumes or {}
    worst_slippage = max(
        (
            slippage_bps(
                policy,
                max(
                    portfolio.positions.get(symbol, ZERO) * openings[symbol],
                    targets.get(symbol, ZERO) * equity,
                ),
                volumes.get(symbol),
            )
            for symbol in targets.keys() | portfolio.positions.keys()
        ),
        default=policy.slippage_bps,
    )
    buffer = equity * 2 * (policy.fee_bps + worst_slippage) / 10000 + CENT * (
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
                volumes.get(symbol),
            )
            if record:
                trades.append(record)
    # Entitlements count in NAV, but cannot fund purchases. Reserve the whole
    # buy basket together so a cash shortfall never favors earlier tickers.
    needs = {
        symbol: max(
            ZERO,
            weight * sizing_value
            - portfolio.positions.get(symbol, ZERO) * openings[symbol],
        )
        for symbol, weight in targets.items()
    }
    usable = max(ZERO, portfolio.cash - equity * policy.cash_reserve)
    total = sum(needs.values(), ZERO)
    scale = min(ONE, usable / total) if total else ZERO
    for symbol, difference in sorted(needs.items()):
        record = buy(
            portfolio,
            symbol,
            openings[symbol],
            difference * scale,
            policy,
            day,
            volumes.get(symbol),
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
