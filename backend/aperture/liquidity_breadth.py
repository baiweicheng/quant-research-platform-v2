"""Weekly stock selection and sizing from prices, volume and participation."""

from decimal import Decimal

import numpy as np

from . import calendar, lifecycles
from .domain import RankedStock, ResearchError
from .earnings_tracker import _select, ordinal_percentiles
from .membership import eligible
from .portfolio import target_weights
from .research_data import blocked_inputs, indexed_issues
from .sectors import sectors_on

STRATEGY_ID = "liquidity_breadth"
HISTORY = 253
COHORT = 48


def _percentiles(values):
    ranks = ordinal_percentiles(dict(enumerate(values)))
    return np.array([ranks[i] for i in range(len(values))])


def _trend_gap(returns):
    """Last total-return close relative to its 200-session average."""
    to_close = np.cumsum(returns[-199:][::-1], axis=0)
    return 200 / (1 + np.exp(-to_close).sum(axis=0)) - 1


def _weakness(breadth, threshold):
    return float(np.clip((threshold - breadth) / 0.35, 0, 1))


class LiquidityBreadth:
    def __init__(self, dataset):
        self.dataset = lifecycles.prepared(dataset)
        self.issues = indexed_issues(self.dataset)
        self.symbols = sorted(self.dataset.bars)
        self.index = {symbol: j for j, symbol in enumerate(self.symbols)}
        if not self.dataset.bars.get("SPY"):
            raise ResearchError("Liquidity and Breadth needs historical SPY bars.")
        populated = [rows for rows in self.dataset.bars.values() if rows]
        self.days = calendar.sessions(
            min(rows[0].session for rows in populated),
            max(rows[-1].session for rows in populated),
        )
        self.dates = {day: i for i, day in enumerate(self.days)}
        shape = len(self.days), len(self.symbols)
        self.returns = np.full(shape, np.nan)
        self.available = np.full(shape, np.inf)
        self.dollar_volume = np.full(shape, np.nan)
        for symbol, col in self.index.items():
            previous = None
            for bar in self.dataset.bars[symbol]:
                i = self.dates.get(bar.session)
                if i is None:
                    continue
                self.available[i, col] = (
                    bar.available_at.timestamp() if bar.available_at else 0
                )
                if bar.volume > 0:
                    self.dollar_volume[i, col] = float(bar.close) * bar.volume
                if i and previous and previous.session == self.days[i - 1]:
                    dividend = (
                        bar.research_dividend or bar.dividend
                    ) + bar.research_distribution
                    self.returns[i, col] = np.log(
                        float(bar.split)
                        * (float(bar.close) + float(dividend))
                        / float(previous.close)
                    )
                previous = bar

    def weekly_review(self, latest, policy):
        decisions = calendar.weekly_review_sessions(self.days, latest, HISTORY)
        if not decisions:
            raise ResearchError(
                "A weekly review needs 253 complete sessions and a completed exchange week."
            )
        prior = {}
        for day in decisions[:-1]:
            _, _, prior, _, _ = self.decision(day, policy, prior)
        return decisions[-1], self.decision(decisions[-1], policy, prior)

    def decision(self, day, policy, incumbents=()):
        i = self.dates[day]
        spy = self.index["SPY"]
        members = (
            eligible(self.dataset, day)
            - set(self.dataset.metadata.get("research_exclusions", ()))
        ) - {"SPY"}
        if members - self.index.keys():
            raise ResearchError("A universe member has no saved price series.")
        blocked = blocked_inputs(
            self.dataset,
            members | {"SPY"},
            self.days[max(0, i - HISTORY + 1)],
            day,
            "signals",
            issue_index=self.issues,
        )
        if blocked:
            raise ResearchError(
                "Unverified price or corporate-action inputs for "
                + ", ".join(sorted(blocked)[:12])
                + "."
            )
        cutoff = calendar.available_time(day).timestamp()
        complete = np.all(
            self.available[max(0, i - HISTORY + 1) : i + 1] <= cutoff, axis=0
        )
        if i < HISTORY - 1 or not complete[spy]:
            raise ResearchError(
                "Liquidity and Breadth needs 253 complete SPY sessions by the decision close."
            )
        returns = self.returns[i - HISTORY + 2 : i + 1]
        complete &= np.isfinite(returns).all(axis=0)
        if not complete[spy]:
            raise ResearchError(
                "SPY price and corporate-action inputs do not produce finite total returns."
            )
        volume = self.dollar_volume[i - 125 : i + 1]
        liquid = np.isfinite(volume[-20:]).sum(axis=0) >= 10
        excluded = []
        candidates = []
        for symbol in sorted(members):
            j = self.index[symbol]
            if complete[j] and liquid[j]:
                candidates.append(j)
            else:
                reason = (
                    "Needs 253 available daily bars with valid returns."
                    if not complete[j]
                    else "Needs traded volume on 10 of the last 20 sessions."
                )
                excluded.append({"symbol": symbol, "reason": reason})
        if not candidates:
            return [], excluded, {}, [], {}
        candidates = np.array(candidates)
        pool_volume = np.nanmedian(volume[:, candidates], axis=0)
        order = np.argsort(-pool_volume, kind="stable")[:COHORT]
        pool = candidates[order]
        pool_volume = pool_volume[order]
        candidate_returns = returns[:, candidates]
        spy_returns = returns[:, spy]
        relative = candidate_returns - spy_returns[:, None]
        gaps = _trend_gap(candidate_returns)
        breadth = float(np.mean(gaps > 0))
        trend_gap = float(_trend_gap(spy_returns))
        sizes = sectors_on(self.dataset, day)
        sectors = np.array([sizes.get(self.symbols[j], "Unknown") for j in candidates])
        sector_breadth = {
            sector: float(np.mean(gaps[sectors == sector] > 0))
            for sector in np.unique(sectors)
        }
        breadth_by_stock = np.array([sector_breadth[sector] for sector in sectors])
        trend = candidate_returns[-63:-5].sum(axis=0)
        compression = relative[-21:].std(axis=0) / np.maximum(
            relative[-126:].std(axis=0), 0.0001
        )
        quiet_trend = 0.55 * _percentiles(trend) + 0.45 * _percentiles(-compression)
        base = 0.75 * _percentiles(pool_volume) + 0.25 * quiet_trend[order]
        participation = (
            0.30 * _weakness(breadth, 0.55) * float(np.clip(-trend_gap / 0.075, 0, 1))
        )
        score = (1 - participation) * base + participation * _percentiles(
            breadth_by_stock
        )[order]
        market = spy_returns[-126:] - spy_returns[-126:].mean()
        variance = market @ market
        if variance > 0:
            beta = (market @ candidate_returns[-126:]) / variance
            beta_rank = _percentiles(-beta)
        else:
            beta = np.zeros(len(candidates))
            beta_rank = np.full(len(candidates), 0.5)
        sizing_strength = 2 * _weakness(breadth, 0.60)
        scales = np.exp(sizing_strength * (beta_rank[order] - 0.5))
        symbols = np.array([self.symbols[j] for j in pool])
        pool_sectors = sectors[order]
        selected = _select(
            candidate_returns[-63:, order] - spy_returns[-63:, None] / 0.98,
            0.1 * (score - 0.5),
            pool_sectors,
            symbols,
            np.isin(symbols, list(incumbents)),
            policy.positions,
            risk_aversion=2,
            incumbent_advantage=0.022,
        )
        ranked = [
            RankedStock(
                symbols[k],
                float(score[k]),
                pool_sectors[k],
                {
                    "median_dollar_volume_126": str(float(pool_volume[k])),
                    "intermediate_log_return": float(trend[order[k]]),
                    "relative_volatility_ratio": float(compression[order[k]]),
                    "sector_breadth": float(breadth_by_stock[order[k]]),
                    "market_breadth": breadth,
                    "spy_trend_gap": trend_gap,
                    "sector_breadth_weight": participation,
                    "beta_to_spy": float(beta[order[k]]),
                    "beta_sizing_strength": sizing_strength,
                    "incumbent": bool(symbols[k] in incumbents),
                },
            )
            for k in selected
        ]
        targets, notes = target_weights(
            ranked,
            policy,
            weight_scales={symbols[k]: Decimal(str(scales[k])) for k in selected},
        )
        excluded.extend(
            {
                "symbol": self.symbols[j],
                "reason": "Outside the liquidity and breadth portfolio selection.",
            }
            for j in candidates
            if self.symbols[j] not in targets
        )
        return ranked, excluded, targets, notes, {}
