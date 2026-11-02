"""One target-construction policy shared by backtests and weekly reviews."""

from collections import Counter, defaultdict
from decimal import Decimal, ROUND_DOWN

from .domain import ONE, ZERO, Policy, RankedStock


def target_weights(
    ranked: list[RankedStock], policy: Policy
) -> tuple[dict[str, Decimal], list[str]]:
    selected = ranked[: policy.positions]
    weights = {stock.symbol: ZERO for stock in selected}
    sectors = {stock.symbol: stock.sector or "Unknown" for stock in selected}
    remaining = ONE - policy.cash_reserve
    active = set(weights)
    epsilon = Decimal("0.000000000001")
    while active and remaining > epsilon:
        sector_weights: dict[str, Decimal] = defaultdict(lambda: ZERO)
        for symbol, weight in weights.items():
            sector_weights[sectors[symbol]] += weight
        counts = Counter(sectors[symbol] for symbol in active)
        increment = min(
            remaining / len(active),
            *(policy.max_weight - weights[symbol] for symbol in active),
            *(
                (policy.sector_cap - sector_weights[sector]) / count
                for sector, count in counts.items()
            ),
        )
        if increment <= epsilon:
            break
        for symbol in sorted(active):
            weights[symbol] += increment
        remaining -= increment * len(active)
        active = {
            symbol
            for symbol in active
            if policy.max_weight - weights[symbol] > epsilon
            and policy.sector_cap
            - sector_weights[sectors[symbol]]
            - increment * counts[sectors[symbol]]
            > epsilon
        }
    weights = {
        symbol: value.quantize(Decimal("0.000000001"), rounding=ROUND_DOWN)
        for symbol, value in sorted(weights.items())
        if value > epsilon
    }
    notes = []
    cash = ONE - sum(weights.values(), ZERO)
    if cash > policy.cash_reserve + Decimal("0.00001"):
        notes.append(
            f"{cash:.1%} stays in cash because eligible stocks and position/sector limits constrain allocation. Limits were not relaxed."
        )
    if any(stock.sector == "Unknown" for stock in selected):
        notes.append(
            "Stocks without a sector share one Unknown bucket, subject to the same sector cap."
        )
    return weights, notes
