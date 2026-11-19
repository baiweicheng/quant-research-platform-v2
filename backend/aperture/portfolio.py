"""One target-construction policy shared by backtests and weekly reviews."""

from collections import defaultdict
from decimal import Decimal, ROUND_DOWN

from .domain import ONE, ZERO, Policy, RankedStock


def uses_liquidity_weights(recipe: dict, ranked: list[RankedStock]) -> bool:
    return recipe.get("weight_by_liquidity", False) and (
        not ranked or ranked[0].components.get("market_state") != "weak"
    )


def target_weights(
    ranked: list[RankedStock], policy: Policy, *, weight_by_liquidity: bool = False
) -> tuple[dict[str, Decimal], list[str]]:
    selected = ranked[: policy.positions]
    weights = {stock.symbol: ZERO for stock in selected}
    sectors = {stock.symbol: stock.sector or "Unknown" for stock in selected}
    remaining = ONE - policy.cash_reserve
    active = set(weights)
    scales = {symbol: ONE for symbol in weights}
    if weight_by_liquidity and selected:
        liquidity = {
            stock.symbol: Decimal(stock.components["median_dollar_volume"]).sqrt()
            for stock in selected
        }
        largest = max(liquidity.values())
        scales = {symbol: value / largest for symbol, value in liquidity.items()}
    epsilon = Decimal("0.000000000001")
    while active and remaining > epsilon:
        sector_weights: dict[str, Decimal] = defaultdict(lambda: ZERO)
        for symbol, weight in weights.items():
            sector_weights[sectors[symbol]] += weight
        ordered_active = sorted(active)
        sector_scales: dict[str, Decimal] = defaultdict(lambda: ZERO)
        for symbol in ordered_active:
            sector_scales[sectors[symbol]] += scales[symbol]
        total_scale = sum(sector_scales.values(), ZERO)
        # Allocate proportionally until a cap binds, then redistribute across
        # the remaining names without changing the original ranking.
        increment = min(
            remaining / total_scale,
            *(
                (policy.max_weight - weights[symbol]) / scales[symbol]
                for symbol in ordered_active
            ),
            *(
                (policy.sector_cap - sector_weights[sector]) / scale
                for sector, scale in sector_scales.items()
            ),
        )
        if increment <= epsilon:
            break
        for symbol in ordered_active:
            weights[symbol] += increment * scales[symbol]
        remaining -= increment * total_scale
        active = {
            symbol
            for symbol in active
            if policy.max_weight - weights[symbol] > epsilon
            and policy.sector_cap
            - sector_weights[sectors[symbol]]
            - increment * sector_scales[sectors[symbol]]
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
