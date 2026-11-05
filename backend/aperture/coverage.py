"""Explicit exploratory coverage policy; complete-input mode stays strict."""

from collections import defaultdict
from datetime import timedelta

from . import calendar, membership
from .domain import ResearchError

MODES = ("strict", "coverage_limited")
WARNING = "Coverage-limited exploratory research: stocks with missing or unverified inputs are excluded using availability over the whole test window, including dates after a decision. This can introduce survivorship and selection bias. These results do not represent a complete S&P 500 backtest or establish trading readiness."


def plan(dataset, start, end, identifier, dividend_model, mode):
    if mode not in MODES:
        raise ResearchError("Choose strict full-index or coverage-limited research.")
    days = calendar.sessions(start, end)
    required = 20 if identifier in ("quality", "quality_value") else 253
    warmup = calendar.sessions(days[0] - timedelta(days=740), days[0])[-required:]
    first = warmup[0] if warmup else days[0]
    first_needed = {}
    for day in days:
        for name in membership.eligible(dataset, day):
            first_needed.setdefault(name, day)
    reasons = defaultdict(list)
    if mode == "coverage_limited":
        from .research_data import input_issues

        for issue in input_issues(dataset):
            name = issue["symbol"]
            if (
                name in first_needed
                and issue["start"] <= str(end)
                and issue["end"] >= str(first)
                and not (
                    issue["kind"] == "cash_payment" and dividend_model != "pay_date"
                )
            ):
                reasons[name].append(f"{issue['start']}: {issue['reason']}")
        if "input_issues" not in dataset.metadata:
            for name, reason in dataset.metadata.get("unavailable_symbols", {}).items():
                if name in first_needed:
                    reasons[name].append(reason)
        for name, begin in first_needed.items():
            available = {b.session for b in dataset.bars.get(name, ())}
            # A departed name may still be held until the next execution. A
            # complete remaining price path avoids inventing a terminal value.
            missing = [d for d in days if d >= begin and d not in available]
            if missing:
                reasons[name].append(
                    f"Missing {len(missing)} sessions from first membership through test end; first missing {missing[0]}. No terminal price is assumed."
                )
    return {
        "mode": mode,
        "dividend_model": dividend_model,
        "start": str(days[0]),
        "end": str(days[-1]),
        "universe_count": len(first_needed),
        "excluded_count": len(reasons),
        "excluded": [
            {"symbol": s, "reasons": sorted(set(r))} for s, r in sorted(reasons.items())
        ],
        "warning": WARNING
        if mode == "coverage_limited"
        else "Strict: required historical members and inputs must be complete; gaps stop the calculation.",
    }
