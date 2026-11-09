"""A daily accounting loop with after-close decisions and next-session fills."""

from dataclasses import replace
from datetime import date
from decimal import Decimal
from typing import Callable

from . import __version__, calendar
from .domain import (
    Dataset,
    ONE,
    ZERO,
    Policy,
    Portfolio,
    ResearchError,
    strategy,
    decimal,
)
from .ledger import apply_actions, buy, rebalance, reinvest_research_income
from .research_data import blocked_inputs, indexed_issues, security_events
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
    dividend_model: str | None = None,
    coverage_mode: str = "strict",
) -> dict:
    dividend_model = dividend_model or dataset.metadata.get(
        "default_dividend_model", "pay_date"
    )
    if dividend_model not in ("ex_date", "pay_date"):
        raise ResearchError(
            "Choose total-return research or payment-date cash simulation."
        )
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
    from .coverage import plan as coverage_plan
    from .lifecycles import prepared

    dataset = prepared(dataset)
    coverage_audit = coverage_plan(
        dataset, days[0], days[-1], identifier, dividend_model, coverage_mode, frequency
    )
    excluded_names = {row["symbol"] for row in coverage_audit["excluded"]}
    if excluded_names:
        dataset = replace(
            dataset,
            metadata={
                **dataset.metadata,
                "research_exclusions": sorted(excluded_names),
            },
        )
    if dividend_model == "pay_date" and "input_issues" in dataset.metadata:
        cash_blocked = {
            i["symbol"]
            for i in dataset.metadata["input_issues"]
            if i["kind"] == "cash_payment"
            and i["start"] <= str(days[-1])
            and i["end"] >= str(days[0])
            and i["symbol"] not in excluded_names
            and i["symbol"] != "SPY"
        }
        if cash_blocked:
            raise ResearchError(
                "Payment-date cash simulation requires verified settlement/share-delivery inputs for "
                + ", ".join(sorted(cash_blocked)[:12])
                + ". Choose total-return research or coverage-limited research, or supply the verified dates."
            )
    validate_coverage(dataset, days[0], days[-1], dividend_model, excluded_names)
    portfolio = Portfolio(capital)
    benchmark = Portfolio(capital)
    benchmark_ready = (
        not blocked_inputs(dataset, {"SPY"}, days[0], days[-1], dividend_model)
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
    from .lifecycles import event_session

    decisions = calendar.decision_sessions(days, frequency)
    pending: tuple[date, dict[str, Decimal]] | None = None
    curve, trades, decision_log = [], [], []
    cash_targets = []
    notes = {
        HISTORY_NOTE
        if dataset.metadata.get("membership")
        else "Exploratory fixed-list research: historical membership, delisted-stock coverage, and sector classifications have not been independently verified. Results must not be described as survivorship-safe."
    }
    if (
        identifier in {"quality_value", "value_momentum"}
        and dataset.metadata.get("fundamentals", {}).get("normalizer")
        == "annual-us-gaap-v1"
    ):
        notes.add(
            "Legacy snapshot: EPS eligibility uses the former current-ticker screen. In Data, refresh SEC financial data and select the new snapshot to use the current EPS policy. Saved historical inputs are not rewritten."
        )
    notes.add(coverage_audit["price_window_policy"])
    if identifier in {"quality_value", "value_momentum"}:
        eps_policy = dataset.metadata.get("fundamentals", {}).get("eps_policy")
        if eps_policy:
            notes.add(dataset.metadata["fundamentals"]["share_basis"])
    if coverage_mode == "coverage_limited":
        notes.add(coverage_audit["warning"])
        notes.add(
            f"Excluded {coverage_audit['excluded_count']} of {coverage_audit['universe_count']} in-period stocks. Every exclusion and reason is retained in the coverage audit."
        )
    sector_audit = dataset.metadata.get("sector_classification")
    if sector_audit:
        notes.add(sector_audit["warning"])
        if sector_audit["unresolved_count"]:
            notes.add(
                f"{sector_audit['unresolved_count']} symbols have unresolved sectors. Unknown stocks share one capped bucket; inspect sector coverage in Data."
            )
    if dataset.kind == "synthetic":
        notes.add(
            "Synthetic practice data. These returns are not evidence of strategy effectiveness."
        )
    if dividend_model == "ex_date":
        notes.add(
            "Total-return research: overnight holders' dividends and spin-off market value are reinvested at the ex-date close when the stock remains held, otherwise retained as cash. This is a research convention, not actual payment-date cash availability. Corporate merger consideration follows captured terms; absent cash-settlement dates use the effective date only in this research mode."
        )
    if not benchmark_ready:
        notes.add(
            "SPY is missing complete coverage for this period. Benchmark metrics are unavailable."
        )
    first_fill_day = days[1]
    issue_index = indexed_issues(dataset)
    for index, day in enumerate(days):
        today = {
            symbol: rows[day] for symbol, rows in investible.items() if day in rows
        }
        corporate = dataset.metadata.get("corporate_actions", [])
        current_mergers = [
            e
            for e in corporate
            if e["kind"] in ("cash_mergers", "stock_mergers", "stock_and_cash_mergers")
            and event_session(e) == day
        ]
        ceased = {e["source"] for e in current_mergers}
        incoming = {
            e["target"]
            for e in current_mergers
            if e.get("target") and portfolio.positions.get(e["source"], ZERO)
        }
        if pending and pending[0] == day:
            incoming.update(set(pending[1]) - ceased)
        blocked = blocked_inputs(
            dataset,
            set(portfolio.positions) | incoming,
            day,
            day,
            dividend_model,
            issue_index=issue_index,
        )
        if blocked:
            raise ResearchError(
                "Held or incoming research positions have unverified inputs: "
                + ", ".join(sorted(blocked)[:12])
                + f" on {day}."
            )
        security_events(portfolio, day, corporate, today, dividend_model)
        opening_income = {
            s: decimal(v)
            for s, v in dataset.metadata.get("research_open_income", {})
            .get(str(day), {})
            .items()
        }
        apply_actions(portfolio, day, today, dividend_model, opening_income)
        if pending and pending[0] == day:
            targets = {s: w for s, w in pending[1].items() if s not in ceased}
            if ceased & pending[1].keys():
                notes.add(
                    "A merger became effective between decision and execution; instructions to buy the ceased security were canceled."
                )
            trades.extend(rebalance(portfolio, targets, today, policy, day))
            pending = None
        if benchmark_ready:
            spy = all_by_day["SPY"][day]
            apply_actions(benchmark, day, {"SPY": spy}, dividend_model)
            if day >= first_fill_day:
                buy(benchmark, "SPY", spy.open, benchmark.cash, reference_policy, day)
        if dividend_model == "ex_date":
            reinvest_research_income(portfolio, day, today)
            if benchmark_ready:
                reinvest_research_income(
                    benchmark, day, {"SPY": all_by_day["SPY"][day]}
                )
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
                    "target_sectors": {
                        stock.symbol: stock.sector
                        for stock in ranked
                        if stock.symbol in targets
                    },
                    "signals": [
                        {
                            "symbol": stock.symbol,
                            "score": stock.score,
                            "sector": stock.sector,
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
    result = {
        "engine_version": __version__,
        "input_contract": "dated-research-v1"
        if dataset.metadata.get("normalizer_version")
        else "as-traded-v1",
        "strategy": recipe,
        "dataset_id": dataset.id,
        "dataset_name": dataset.name,
        "dataset_kind": dataset.kind,
        "dataset_revision": dataset.revision,
        "source_digest": dataset.digest,
        "input_audit": {
            k: v
            for k, v in dataset.metadata.items()
            if k != "_research_terminal_events"
        },
        "start": str(days[0]),
        "end": str(days[-1]),
        "capital": str(capital),
        "frequency": frequency,
        "dividend_model": dividend_model,
        "coverage": coverage_audit,
        "policy": {
            key: str(value) if isinstance(value, Decimal) else value
            for key, value in vars(policy).items()
        },
        "sector_classification": {
            k: sector_audit[k]
            for k in (
                "version",
                "policy",
                "warning",
                "classified_count",
                "unresolved_count",
                "classification_digest",
            )
        }
        if sector_audit
        else None,
        "curve": curve,
        "windows": windows(curve),
        "trades": trades,
        "trade_count": len(trades),
        "holdings": holdings,
        "decisions": decision_log,
        "notes": sorted(notes),
        "benchmark_model": "SPY buy-and-hold from the same next-session open, with the same costs and ex-date closing-price reinvestment."
        if dividend_model == "ex_date"
        else "SPY buy-and-hold from the same next-session open, with the same costs and dividend reinvestment when cash is paid.",
        "execution_model": "Targets decided after close; simulated fills at the next actual session open with explicit slippage, fees, fractional shares and cash checks. No opening-auction execution guarantee.",
    }
    from .exposure import summarize as summarize_exposure

    result["exposure"] = summarize_exposure(result)
    return result
