"""Weekly earnings strategy that distinguishes weak and strong market sessions."""

from decimal import Decimal

import numpy as np

from .domain import RankedStock
from .earnings_tracker import (
    EarningsTracker,
    WeeklyIncomeResearch,
    _select,
    filing_components,
    ordinal_percentiles,
)
from .portfolio import target_weights
from .pullback_rotation import (
    STRATEGY_ID as PULLBACK_ROTATION,
    EarningsPullbackRotation,
)
from .sectors import sectors_on
from .signals import median_dollar_volume

STRATEGY_ID = "earnings_market_capture"
CAPTURE_SESSIONS = 126


def market_capture(market, stocks):
    """Mean daily active log return in both tails of the market's return distribution."""
    weak, strong = np.quantile(market, (0.25, 0.75))
    relative = stocks - market[:, None]
    return relative[market <= weak].mean(axis=0), relative[market >= strong].mean(
        axis=0
    )


class EarningsMarketCapture(WeeklyIncomeResearch):
    def __init__(self, dataset):
        super().__init__(dataset)
        self.bars = {
            symbol: {bar.session: bar for bar in bars}
            for symbol, bars in self.dataset.bars.items()
        }

    def decision(self, day, policy, incumbents=()):
        candidates, excluded, audit = self._candidates(day)
        if not candidates:
            return [], excluded, {}, [], audit

        symbols = list(candidates)
        index = self.dates[day]
        recent = self.days[index - 19 : index + 1]
        volume = {
            s: median_dollar_volume(self.bars[s][d] for d in recent) for s in symbols
        }
        history = self.returns[index - CAPTURE_SESSIONS + 1 : index + 1]
        benchmark = history[:, self.index["SPY"]]
        prices = history[:, [self.index[s] for s in symbols]]
        weak, strong = market_capture(benchmark, prices)
        weak_returns = dict(zip(symbols, map(float, weak)))
        strong_returns = dict(zip(symbols, map(float, strong)))
        weak_rank = ordinal_percentiles(weak_returns)
        strong_rank = ordinal_percentiles(strong_returns)
        scale_rank = ordinal_percentiles(
            {s: report.scale for s, (_, report) in candidates.items()}
        )
        growth_rank = ordinal_percentiles(
            {s: report.growth for s, (_, report) in candidates.items()}
        )
        volume_rank = ordinal_percentiles(volume)

        # Screen on business scale and liquidity. The price tilt rewards
        # participation in rallies alongside resilience on weak days.
        pool = sorted(
            symbols, key=lambda s: -(0.60 * scale_rank[s] + 0.40 * volume_rank[s])
        )[:50]
        forecast = np.array(
            [
                0.10
                * (
                    0.60 * (0.65 * weak_rank[s] + 0.35 * strong_rank[s])
                    + 0.20 * scale_rank[s]
                    + 0.20 * growth_rank[s]
                    - 0.50
                )
                for s in pool
            ]
        )
        sectors = sectors_on(self.dataset, day)
        labels = np.array([sectors.get(s, "Unknown") for s in pool])
        issuers = np.array([candidates[s][0] for s in pool])
        existing = np.isin(pool, list(incumbents))
        residual = history[:, [self.index[s] for s in pool]] - benchmark[
            :, None
        ] / float(1 - policy.cash_reserve)
        selected = _select(
            residual,
            forecast,
            labels,
            issuers,
            existing,
            policy.positions,
            risk_aversion=4,
            incumbent_advantage=0.02,
        )
        ranked = []
        for i in selected:
            symbol = pool[i]
            cik, report = candidates[symbol]
            ranked.append(
                RankedStock(
                    symbol,
                    float(forecast[i]),
                    str(labels[i]),
                    {
                        **filing_components(cik, report),
                        "median_dollar_volume": str(volume[symbol]),
                        "weak_market_relative_return": weak_returns[symbol],
                        "strong_market_relative_return": strong_returns[symbol],
                        "incumbent": bool(existing[i]),
                    },
                )
            )
        targets, notes = target_weights(
            ranked, policy, weight_by_liquidity=True, liquidity_power=Decimal("0.75")
        )
        excluded.extend(
            {
                "symbol": s,
                "reason": "Outside the earnings, liquidity or capture selection.",
            }
            for s in symbols
            if s not in targets
        )
        return ranked, excluded, targets, notes, audit


def weekly_income_model(dataset, identifier):
    model = {
        STRATEGY_ID: EarningsMarketCapture,
        PULLBACK_ROTATION: EarningsPullbackRotation,
    }.get(identifier, EarningsTracker)
    return model(dataset)
