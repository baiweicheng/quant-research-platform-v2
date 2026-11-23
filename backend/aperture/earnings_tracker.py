"""Weekly earnings and filing-reaction portfolio with a SPY tracking objective."""

from bisect import bisect_left, bisect_right
from collections import Counter
from datetime import date, timedelta
from decimal import ROUND_DOWN, Decimal

import numpy as np

from . import annual_income, calendar, lifecycles, periodic_income
from .domain import RankedStock, ResearchError
from .membership import eligible
from .portfolio import target_weights
from .research_data import blocked_inputs, indexed_issues
from .sectors import sectors_on
from .signals import percentile_ranks


def _select(
    residual,
    forecast,
    sectors,
    issuers,
    incumbents,
    count,
    *,
    risk_aversion=10,
    incumbent_advantage=0.0132,
):
    allowed = np.ones(len(forecast), dtype=bool)
    total = np.zeros((len(residual), 1))
    selected = []
    counts = Counter()
    benefit = forecast + incumbent_advantage * incumbents
    for size in range(1, count + 1):
        if not np.any(allowed):
            break
        loss = np.mean((total + residual) ** 2, axis=0)
        utility = benefit - risk_aversion * 252 / (2 * size) * loss
        best = int(np.argmax(np.where(allowed, utility, -np.inf)))
        selected.append(best)
        total += residual[:, best, None]
        allowed &= issuers != issuers[best]
        counts[sectors[best]] += 1
        if counts[sectors[best]] >= 6:
            allowed &= sectors != sectors[best]
    return selected


def _weights(ranked, residual, forecast, policy):
    base, notes = target_weights(ranked, policy)
    weights = np.array([float(base.get(s.symbol, 0)) for s in ranked])
    labels = np.unique([s.sector for s in ranked], return_inverse=True)[1]
    risk = np.atleast_2d(np.cov(residual.T, ddof=0)) * 252
    marginal_risk = risk @ weights
    variance = np.diag(risk)
    curvature = 10 * np.maximum(1e-12, variance[None, :] + variance[:, None] - 2 * risk)
    same_sector = labels[:, None] == labels[None, :]
    # Each feasible pair transfer preserves total exposure. Choose the greatest
    # improvement in forecast return minus tracking variance, then update the gradient.
    for _ in range(65):
        utility = forecast - 10 * marginal_risk
        improvement = utility[None, :] - utility[:, None]
        sector_room = (
            float(policy.sector_cap) - np.bincount(labels, weights=weights)[labels]
        )
        room = np.minimum(weights[:, None], float(policy.max_weight) - weights[None, :])
        room = np.minimum(room, np.where(same_sector, 1.0, sector_room[None, :]))
        step = np.clip(improvement / curvature, 0, np.maximum(room, 0))
        gain = improvement * step - 0.5 * curvature * step**2
        source, dest = np.unravel_index(np.argmax(gain), gain.shape)
        if gain[source, dest] < 1e-10:
            break
        amount = step[source, dest]
        weights[source] -= amount
        weights[dest] += amount
        marginal_risk += amount * (risk[:, dest] - risk[:, source])
    return {
        s.symbol: Decimal(str(float(w))).quantize(
            Decimal("0.000000001"), rounding=ROUND_DOWN
        )
        for s, w in zip(ranked, weights)
        if w >= 1e-9
    }, notes


def ordinal_percentiles(values):
    size = len(values)
    return {
        symbol: (percentile * (size - 1) + 1) / size
        for symbol, percentile in percentile_ranks(values).items()
    }


def filing_components(cik, report):
    return {
        "cik": cik,
        "accession": report.accession,
        "form": report.form,
        "filed": str(report.filed),
        "period_end": str(report.end),
        "period_start": str(report.start),
        "comparative_start": str(report.prior_start),
        "comparative_end": str(report.prior_end),
        "concept": report.concept,
        **({"source_url": report.source_url} if report.source_url else {}),
        "income": str(report.income),
        "prior_income": str(report.previous),
        "annualized_income": report.scale,
        "earnings_growth": report.growth,
    }


class WeeklyIncomeResearch:
    def __init__(self, dataset):
        if (
            not dataset.periodic_income
            or "SPY" not in dataset.bars
            or not dataset.bars["SPY"]
        ):
            raise ResearchError(periodic_income.MISSING + " SPY bars are required.")
        self.dataset = lifecycles.prepared(dataset)
        self.issues = indexed_issues(dataset)
        self.succession = periodic_income.succession_histories(dataset)
        self.reports = {
            cik: ([r.filed for r in rows], rows)
            for cik, rows in dataset.periodic_income.items()
        }
        self.symbols = sorted(dataset.bars)
        self.index = {s: i for i, s in enumerate(self.symbols)}
        start = min(rows[0].session for rows in dataset.bars.values() if rows)
        end = max(rows[-1].session for rows in dataset.bars.values() if rows)
        self.days = calendar.sessions(start, end)
        self.dates = {d: i for i, d in enumerate(self.days)}
        shape = len(self.days), len(self.symbols)
        self.returns = np.full(shape, np.nan)
        self.available = np.full(shape, np.inf)
        self.traded = np.zeros(shape, dtype=bool)
        for j, symbol in enumerate(self.symbols):
            previous = None
            for bar in dataset.bars[symbol]:
                i = self.dates.get(bar.session)
                if i is None:
                    continue
                self.available[i, j] = (
                    bar.available_at.timestamp() if bar.available_at else 0
                )
                self.traded[i, j] = bar.volume > 0
                if previous and i and previous.session == self.days[i - 1]:
                    dividend = (
                        bar.research_dividend or bar.dividend
                    ) + bar.research_distribution
                    gross = (
                        float(bar.split)
                        * (float(bar.close) + float(dividend))
                        / float(previous.close)
                    )
                    self.returns[i, j] = np.log(gross)
                previous = bar

    def weekly_review(self, latest, policy):
        last = self.dates[latest]
        while (
            last >= 0
            and self.days[last].isocalendar()[:2]
            == calendar.next_session(self.days[last]).isocalendar()[:2]
        ):
            last -= 1
        first = self.days[0]
        default_start = (
            date(first.year + 1, 1, 1)
            if (first.month, first.day) <= (1, 7)
            else first + timedelta(days=370)
        )
        start = max(252, bisect_left(self.days, default_start))
        if last < start:
            raise ResearchError(
                "A weekly review needs 253 complete sessions and a completed exchange week."
            )
        decisions = sorted(
            calendar.decision_sessions(self.days[start : last + 1], "weekly")
        )
        prior = {}
        for day in decisions[:-1]:
            _, _, prior, _, _ = self.decision(day, policy, prior)
        return decisions[-1], self.decision(decisions[-1], policy, prior)

    def _report(self, symbol, day, cutoff):
        if symbol in self.succession:
            dates, history = self.succession[symbol]
            index = bisect_left(dates, day) - 1
            if index >= 0:
                cik, report, expires = history[index]
                if day < expires:
                    return cik, report
            return "", None
        identity = annual_income.as_of(
            self.dataset.annual_income.get(symbol, ()), day, cutoff
        )
        cik = identity["cik"] if identity else ""
        dates, reports = self.reports.get(cik, ((), ()))
        index = bisect_left(dates, day) - 1
        return cik, reports[index] if index >= 0 else None

    def _candidates(self, day):
        ds = self.dataset
        t = self.dates[day]
        cutoff = calendar.available_time(day)
        members = eligible(ds, day) - set(ds.metadata.get("research_exclusions", ()))
        if members - self.index.keys():
            raise ResearchError("A member has no saved price series.")
        blocked = blocked_inputs(
            ds,
            members | {"SPY"},
            self.days[max(0, t - 252)],
            day,
            "signals",
            issue_index=self.issues,
        )
        if blocked:
            raise ResearchError(
                "Unverified weekly income strategy price inputs for "
                + ", ".join(sorted(blocked)[:12])
                + "."
            )
        market = self.index["SPY"]
        available = np.all(
            self.available[max(0, t - 252) : t + 1] <= cutoff.timestamp(), axis=0
        )
        if t < 252 or not available[market]:
            raise ResearchError(
                "Choose a dataset with 253 complete SPY sessions before the first weekly income decision, including the decision close."
            )
        volume = self.traded[t - 19 : t + 1].sum(axis=0) >= 10
        candidates = {}
        excluded = []
        stats = {"positive": 0, "nonpositive": 0, "unavailable": 0}
        assessed = 0
        for symbol in sorted(members):
            j = self.index[symbol]
            if not available[j] or not volume[j]:
                excluded.append(
                    {
                        "symbol": symbol,
                        "reason": "Needs 253 timely sessions and ten positive-volume days in the latest 20.",
                    }
                )
                continue
            assessed += 1
            cik, report = self._report(symbol, day, cutoff)
            if (
                not report
                or report.income is None
                or day - report.filed > timedelta(days=150)
            ):
                stats["unavailable"] += 1
                excluded.append(
                    {
                        "symbol": symbol,
                        "reason": "No timely comparable 10-Q/10-K income pair.",
                    }
                )
                continue
            if report.income <= 0:
                stats["nonpositive"] += 1
                excluded.append(
                    {"symbol": symbol, "reason": "Reported income is nonpositive."}
                )
                continue
            stats["positive"] += 1
            candidates[symbol] = (cik, report)
        audit = {
            "members": len(members),
            "assessed": assessed,
            "factors": {"periodic_net_income": stats},
        }
        return candidates, excluded, audit


class EarningsTracker(WeeklyIncomeResearch):
    def decision(self, day, policy, incumbents=()):
        candidates, excluded, audit = self._candidates(day)
        if not candidates or policy.cash_reserve == 1:
            return [], excluded, {}, [], audit
        t = self.dates[day]
        market = self.index["SPY"]
        labels = sectors_on(self.dataset, day)
        growth = {s: report.growth for s, (_, report) in candidates.items()}
        news = {}
        for symbol, (_, report) in candidates.items():
            event = bisect_right(self.days, report.filed)
            # The three returns end at the first full session after filing.
            interval = self.returns[event - 2 : event + 1]
            news[symbol] = float(
                (interval[:, self.index[symbol]] - interval[:, market]).sum()
            )
        growth_rank = ordinal_percentiles(growth)
        news_rank = ordinal_percentiles(news)
        pool = sorted(candidates, key=lambda s: -candidates[s][1].scale)[:50]
        js = [self.index[s] for s in pool]
        sectors = np.array([labels.get(s, "Unknown") for s in pool])
        issuers = np.array([candidates[s][0] for s in pool])
        held = np.isin(pool, list(incumbents))
        forecast = np.array(
            [0.08 * ((growth_rank[s] + news_rank[s]) / 2 - 0.5) for s in pool]
        )
        history = self.returns[t - 251 : t + 1]
        residual = history[:, js] - history[:, market, None] / float(
            1 - policy.cash_reserve
        )
        choice = _select(
            residual[-126:], forecast, sectors, issuers, held, policy.positions
        )
        ranked = []
        for k in choice:
            symbol = pool[k]
            cik, report = candidates[symbol]
            ranked.append(
                RankedStock(
                    symbol,
                    float(forecast[k]),
                    str(sectors[k]),
                    {
                        **filing_components(cik, report),
                        "filing_relative_return": news[symbol],
                        "incumbent": bool(held[k]),
                    },
                )
            )
        chosen = {s.symbol for s in ranked}
        excluded.extend(
            {"symbol": s, "reason": "Outside the earnings or tracking selection."}
            for s in candidates
            if s not in chosen
        )
        weights, notes = _weights(ranked, residual[:, choice], forecast[choice], policy)
        excluded.extend(
            {
                "symbol": stock.symbol,
                "reason": "The risk allocation assigned zero weight.",
            }
            for stock in ranked
            if stock.symbol not in weights
        )
        return (
            [stock for stock in ranked if stock.symbol in weights],
            excluded,
            weights,
            notes,
            audit,
        )
