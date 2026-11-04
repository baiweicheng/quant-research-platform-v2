"""A daily accounting loop with after-close decisions and next-session fills."""

from datetime import date
from decimal import Decimal
from typing import Callable

from . import __version__, calendar
from .domain import Dataset, ONE, ZERO, Policy, Portfolio, ResearchError, strategy
from .ledger import apply_actions, buy, rebalance
from .metrics import windows
from .membership import validate_coverage, HISTORY_NOTE
from .portfolio import target_weights
from .signals import rank


def run(
    dataset: Dataset,
    identifier: str,
    start: date,
    end: date,
    capital: Decimal,
    policy: Policy,
    frequency: str = "weekly",
    progress: Callable[[int, str], None] | None = None,
) -> dict:
    recipe = strategy(identifier)
    if not capital.is_finite() or capital < Decimal("100"):
        raise ResearchError("Starting capital must be at least $100.")
    if frequency not in ("weekly", "monthly", "daily"):
        raise ResearchError("Choose weekly, monthly, or daily rebalancing.")
    if start >= end:
        raise ResearchError("Choose an end date after the start date.")
    days = calendar.sessions(start, end)
    if len(days) < 2:
        raise ResearchError("Choose a period containing at least two trading sessions.")
    all_by_day = {
        symbol: {bar.session: bar for bar in bars}
        for symbol, bars in dataset.bars.items()
    }
    investible = {
        symbol: rows for symbol, rows in all_by_day.items() if symbol != "SPY"
    }
    if not investible:
        raise ResearchError(
            "Import at least one stock in addition to the optional SPY benchmark."
        )
    last_available = max(day for rows in investible.values() for day in rows)
    first_available = min(day for rows in investible.values() for day in rows)
    if days[-1] > last_available or days[0] < first_available:
        raise ResearchError(
            f"Choose dates within the stock data coverage: {first_available} to {last_available}."
        )
    validate_coverage(dataset, days[0], days[-1])
    portfolio = Portfolio(capital)
    benchmark = Portfolio(capital)
    benchmark_ready = (
        "SPY" not in dataset.metadata.get("unavailable_symbols", {})
        and "SPY" in all_by_day
        and all(day in all_by_day["SPY"] for day in days)
    )
    reference_policy = Policy(
        positions=1,
        max_weight=ONE,
        sector_cap=ONE,
        cash_reserve=ZERO,
        fee_bps=policy.fee_bps,
        slippage_bps=policy.slippage_bps,
    )
    decisions = calendar.decision_sessions(days, frequency)
    pending: tuple[date, dict[str, Decimal]] | None = None
    curve, trades, decision_log = [], [], []
    cash_targets = []
    notes = {
        HISTORY_NOTE
        if dataset.metadata.get("membership")
        else "Exploratory fixed-list research: historical membership, delisted-stock coverage, and sector classifications have not been independently verified. Results must not be described as survivorship-safe."
    }
    if dataset.kind == "synthetic":
        notes.add(
            "Synthetic practice data. These returns are not evidence of strategy effectiveness."
        )
    if not benchmark_ready:
        notes.add(
            "SPY is missing complete coverage for this period. Benchmark metrics are unavailable."
        )
    first_fill_day = days[1]
    for index, day in enumerate(days):
        today = {
            symbol: rows[day] for symbol, rows in investible.items() if day in rows
        }
        apply_actions(portfolio, day, today)
        if pending and pending[0] == day:
            trades.extend(rebalance(portfolio, pending[1], today, policy, day))
            pending = None
        if benchmark_ready:
            spy = all_by_day["SPY"][day]
            apply_actions(benchmark, day, {"SPY": spy})
            if day >= first_fill_day:
                buy(benchmark, "SPY", spy.open, benchmark.cash, reference_policy, day)
        closes = {symbol: bar.close for symbol, bar in today.items()}
        value = portfolio.value(closes)
        reference = (
            benchmark.value({"SPY": all_by_day["SPY"][day].close})
            if benchmark_ready
            else None
        )
        curve.append(
            {
                "session": str(day),
                "equity": str(value),
                "cash": str(portfolio.cash),
                "receivable": str(
                    sum((amount for _, amount in portfolio.receivables), ZERO)
                ),
                "benchmark": None if reference is None else str(reference),
            }
        )
        if day in decisions and day != days[-1]:
            ranked, excluded = rank(dataset, identifier, day)
            targets, allocation_notes = target_weights(ranked, policy)
            notes.update(
                note for note in allocation_notes if "stays in cash because" not in note
            )
            cash_targets.append(ONE - sum(targets.values(), ZERO))
            pending = (calendar.next_session(day), targets)
            decision_log.append(
                {
                    "session": str(day),
                    "execute_session": str(pending[0]),
                    "eligible": len(ranked),
                    "excluded": len(excluded),
                    "targets": {
                        symbol: str(weight) for symbol, weight in targets.items()
                    },
                    "signals": [
                        {
                            "symbol": stock.symbol,
                            "score": stock.score,
                            "components": stock.components,
                        }
                        for stock in ranked
                    ],
                    "exclusions": excluded,
                }
            )
        if progress and (index % 10 == 0 or index == len(days) - 1):
            progress(
                10 + round(index / len(days) * 85),
                f"Simulating {day}; {len(trades)} fills recorded",
            )
    if not trades:
        notes.add(
            "No trades occurred. Check the warm-up history, missing sessions, and eligible-stock count."
        )
    if cash_targets and max(cash_targets) > policy.cash_reserve + Decimal("0.00001"):
        notes.add(
            f"Target cash ranged from {min(cash_targets):.1%} to {max(cash_targets):.1%} as eligible stocks and allocation limits changed. Limits were never relaxed."
        )
    final_prices = {
        symbol: rows[days[-1]].close
        for symbol, rows in investible.items()
        if days[-1] in rows
    }
    holdings = [
        {
            "symbol": symbol,
            "quantity": str(quantity),
            "price": str(final_prices[symbol]),
            "value": str(quantity * final_prices[symbol]),
            "weight": float(
                quantity * final_prices[symbol] / Decimal(curve[-1]["equity"])
            ),
        }
        for symbol, quantity in sorted(portfolio.positions.items())
    ]
    return {
        "engine_version": __version__,
        "input_contract": "as-traded-v1",
        "strategy": recipe,
        "dataset_id": dataset.id,
        "dataset_name": dataset.name,
        "dataset_kind": dataset.kind,
        "dataset_revision": dataset.revision,
        "source_digest": dataset.digest,
        "input_audit": dataset.metadata,
        "start": str(days[0]),
        "end": str(days[-1]),
        "capital": str(capital),
        "frequency": frequency,
        "policy": {
            key: str(value) if isinstance(value, Decimal) else value
            for key, value in vars(policy).items()
        },
        "curve": curve,
        "windows": windows(curve),
        "trades": trades,
        "trade_count": len(trades),
        "holdings": holdings,
        "decisions": decision_log,
        "notes": sorted(notes),
        "benchmark_model": "SPY buy-and-hold from the same next-session open, with the same costs and dividend reinvestment when cash is paid.",
        "execution_model": "Targets decided after close; simulated fills at the next actual session open with explicit slippage, fees, fractional shares and cash checks. No opening-auction execution guarantee.",
    }
