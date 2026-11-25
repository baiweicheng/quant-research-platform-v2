"""Weekly liquidity and volatility selection with a market rebound rule."""

from decimal import Decimal

import numpy as np

from .domain import RankedStock
from .earnings_tracker import (
    WeeklyIncomeResearch,
    filing_components,
    ordinal_percentiles,
)
from .portfolio import target_weights
from .pullback_rotation import select_stocks
from .sectors import sectors_on
from .signals import median_dollar_volume

STRATEGY_ID = "liquidity_volatility_rotation"
REBOUND_GAP = -0.065


def _trend_gap(returns):
    """Decision total-return level divided by its 252-close average, minus one."""
    prior = np.cumsum(returns[-251:][::-1])
    return float(252 / (1 + np.exp(-prior).sum()) - 1)


def _stock_signals(stocks, market, volume, rebound):
    centered = market[-126:] - market[-126:].mean()
    variance = centered @ centered
    beta = centered @ stocks[-126:] / variance if variance else np.zeros(len(volume))
    volatility = stocks[-63:].std(axis=0)
    volatility_adjusted_liquidity = np.log(volume) - 0.5 * np.log(
        np.maximum(stocks[-20:].std(axis=0), 1e-12)
    )
    risk_adjusted_trend = stocks[-126:].sum(axis=0) / np.maximum(volatility, 0.001)
    tracking_volatility = (stocks[-63:] - market[-63:, None]).std(axis=0)
    pullback = -stocks[-5:].sum(axis=0) / np.maximum(tracking_volatility, 0.001)

    if rebound:
        scoring = ((0.40, beta), (0.30, pullback), (0.30, volume))
        scales = (volume / 1e9) ** 0.50
    else:
        scoring = ((0.90, volatility_adjusted_liquidity), (0.10, risk_adjusted_trend))
        scales = (
            (volume / 1e9) ** 0.30
            * np.sqrt(np.clip(beta, 0.45, 1.80))
            / np.maximum(volatility, 0.004)
        )
    return (
        scoring,
        scales,
        beta,
        volatility_adjusted_liquidity,
        risk_adjusted_trend,
        pullback,
    )


class LiquidityVolatilityRotation(WeeklyIncomeResearch):
    def __init__(self, dataset):
        super().__init__(dataset)
        self.volume_bars = {
            symbol: {bar.session: bar for bar in bars}
            for symbol, bars in self.dataset.bars.items()
        }

    def decision(self, day, policy, incumbents=()):
        filings, excluded, audit = self._candidates(day)
        if not filings:
            return [], excluded, {}, [], audit

        symbols = list(filings)
        end = self.dates[day] + 1
        market = self.returns[end - 252 : end, self.index["SPY"]]
        gap = _trend_gap(market)
        rebound = gap < REBOUND_GAP
        audit["market_trend_gap_252"] = gap
        audit["sleeve"] = "rebound" if rebound else "liquidity"

        recent = self.days[end - 20 : end]
        volumes = {
            symbol: median_dollar_volume(self.volume_bars[symbol][d] for d in recent)
            for symbol in symbols
        }
        stocks = self.returns[end - 126 : end, [self.index[s] for s in symbols]]
        scoring, scales, beta, liquid, trend, pullback = _stock_signals(
            stocks, market, np.array([float(volumes[s]) for s in symbols]), rebound
        )
        rank_components = [
            (weight, ordinal_percentiles(dict(zip(symbols, values))))
            for weight, values in scoring
        ]
        pool = sorted(symbols, key=lambda s: -volumes[s])[: 100 if rebound else 110]
        scores = {
            s: round(sum(weight * ranks[s] for weight, ranks in rank_components), 12)
            for s in pool
        }
        sectors_as_of = sectors_on(self.dataset, day)
        sectors = {s: sectors_as_of.get(s, "Unknown") for s in symbols}
        candidates = select_stocks(
            sorted(pool),
            scores,
            set(incumbents),
            0.12 if rebound else 0.14,
            filings,
            sectors,
            min(policy.positions, 25 if rebound else 22),
        )
        indices = {symbol: j for j, symbol in enumerate(symbols)}
        ranked = []
        weights = {}
        for symbol in candidates:
            j = indices[symbol]
            cik, report = filings[symbol]
            ranked.append(
                RankedStock(
                    symbol,
                    scores[symbol],
                    sectors[symbol],
                    {
                        **filing_components(cik, report),
                        "median_dollar_volume": str(volumes[symbol]),
                        "volatility_adjusted_liquidity": float(liquid[j]),
                        "risk_adjusted_trend": float(trend[j]),
                        "pullback_score": float(pullback[j]),
                        "beta_126": float(beta[j]),
                        "incumbent": symbol in incumbents,
                    },
                )
            )
            weights[symbol] = Decimal(str(float(scales[j])))
        targets, notes = target_weights(ranked, policy, weight_scales=weights)
        excluded.extend(
            {"symbol": s, "reason": "Outside the liquidity or portfolio selection."}
            for s in symbols
            if s not in targets
        )
        return ranked, excluded, targets, notes, audit
