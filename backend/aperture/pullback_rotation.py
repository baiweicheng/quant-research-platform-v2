"""Weekly relative-strength and pullback portfolios using dated earnings."""

from collections import Counter
from decimal import Decimal
from math import log

import numpy as np

from .domain import RankedStock
from .earnings_tracker import (
    WeeklyIncomeResearch,
    filing_components,
    ordinal_percentiles,
)
from .portfolio import target_weights
from .sectors import sectors_on
from .signals import median_dollar_volume

STRATEGY_ID = "earnings_pullback_rotation"
MARKET_SESSIONS = 126
PULLBACK_THRESHOLD = log(0.95)


def select_stocks(pool, scores, incumbents, bonus, filings, sectors, positions):
    ordered = sorted(pool, key=lambda s: -(scores[s] + bonus * (s in incumbents)))
    picks, issuers = [], set()
    sector_count = Counter()
    for symbol in ordered:
        issuer, _ = filings[symbol]
        sector = sectors[symbol]
        if issuer in issuers or sector_count[sector] >= 6:
            continue
        issuers.add(issuer)
        sector_count[sector] += 1
        picks.append(symbol)
        if len(picks) == positions:
            break
    return picks


class EarningsPullbackRotation(WeeklyIncomeResearch):
    def __init__(self, dataset):
        super().__init__(dataset)
        self.volume_bars = {
            s: {bar.session: bar for bar in bars}
            for s, bars in self.dataset.bars.items()
        }

    def decision(self, day, policy, incumbents=()):
        filings, excluded, audit = self._candidates(day)
        if not filings:
            return [], excluded, {}, [], audit

        symbols = list(filings)
        sectors_as_of = sectors_on(self.dataset, day)
        sectors = {s: sectors_as_of.get(s, "Unknown") for s in symbols}
        end = self.dates[day] + 1
        window = self.returns[end - MARKET_SESSIONS : end]
        stocks = window[:, [self.index[s] for s in symbols]]
        market = window[:, self.index["SPY"]]
        variance = market.var()
        centered_market = market - market.mean()
        beta = np.mean(
            (stocks - stocks.mean(axis=0)) * centered_market[:, None], axis=0
        )
        if variance > 0:
            beta /= variance

        market_return = float(market.sum())
        pullback_market = market_return < PULLBACK_THRESHOLD
        audit["market_log_return_126"] = market_return
        audit["sleeve"] = "pullback" if pullback_market else "relative"
        residual_63 = stocks[-63:].sum(axis=0) - beta * market[-63:].sum()
        residual_126 = stocks.sum(axis=0) - beta * market_return
        tracking_vol = (stocks[-63:] - market[-63:, None]).std(axis=0)
        pullback = -stocks[-5:].sum(axis=0) / np.maximum(tracking_vol, 0.001)
        recent = self.days[end - 20 : end]
        volumes = {
            s: median_dollar_volume(self.volume_bars[s][d] for d in recent)
            for s in symbols
        }
        income_growth = ordinal_percentiles(
            {s: report.growth for s, (_, report) in filings.items()}
        )
        pool = sorted(symbols, key=lambda s: -volumes[s])[:100]
        if pullback_market:
            ranks_beta = ordinal_percentiles(dict(zip(symbols, beta)))
            ranks_pullback = ordinal_percentiles(dict(zip(symbols, pullback)))
            ranks_volume = ordinal_percentiles(volumes)
            scores = {
                s: 0.35 * ranks_beta[s]
                + 0.30 * ranks_pullback[s]
                + 0.20 * ranks_volume[s]
                + 0.15 * income_growth[s]
                for s in pool
            }
        else:
            ranks_63 = ordinal_percentiles(dict(zip(symbols, residual_63)))
            ranks_126 = ordinal_percentiles(dict(zip(symbols, residual_126)))
            scores = {
                s: 0.40 * ranks_63[s] + 0.40 * ranks_126[s] + 0.20 * income_growth[s]
                for s in pool
            }
        chosen = select_stocks(
            pool,
            scores,
            set(incumbents),
            0.12 if pullback_market else 0.05,
            filings,
            sectors,
            policy.positions,
        )
        ranked = []
        scales = {}
        candidate_index = {s: j for j, s in enumerate(symbols)}
        for symbol in chosen:
            j = candidate_index[symbol]
            cik, report = filings[symbol]
            ranked.append(
                RankedStock(
                    symbol,
                    scores[symbol],
                    sectors[symbol],
                    {
                        **filing_components(cik, report),
                        "beta_126": float(beta[j]),
                        "pullback_score": float(pullback[j]),
                        "residual_63": float(residual_63[j]),
                        "residual_126": float(residual_126[j]),
                        "median_dollar_volume": str(volumes[symbol]),
                    },
                )
            )
            scales[symbol] = volumes[symbol].sqrt()
            if not pullback_market:
                scales[symbol] *= Decimal(str(np.clip(beta[j], 0.45, 1.8)))
        weights, notes = target_weights(ranked, policy, weight_scales=scales)
        excluded.extend(
            {"symbol": s, "reason": "Outside the liquidity or portfolio selection."}
            for s in symbols
            if s not in weights
        )
        return ranked, excluded, weights, notes, audit
