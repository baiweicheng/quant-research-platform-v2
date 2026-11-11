"""Conservative, filing-versioned annual US-GAAP research inputs.

Do not turn a current companyfacts snapshot into a current-ratios history.
Every normalized value retains its accession, reporting dates, and availability.
"""

import hashlib
import json
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal

from . import calendar
from .domain import AnnualStatement, Dataset, ONE, ResearchError, ZERO, decimal
from .providers import Provider, ResourceMissing
from .store import Store, now
from .eps_policy import (
    assess,
    EPS_TAGS,
    WARNING as EPS_WARNING,
    VERSION as EPS_VERSION,
)
from .annual_refresh import companyfacts as read_companyfacts

VERSION = "annual-us-gaap-v6-gross-profit-and-service-costs"
AVAILABILITY = "After close + 15 minutes on the first exchange session strictly after the SEC filing date. No same-day publication assumption."
TAGS = {
    "assets": ("Assets",),
    "gross_profit": ("GrossProfit",),
    "revenue": (
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
    ),
    "cost": (
        "CostOfRevenue",
        "CostOfGoodsAndServicesSold",
        "CostOfGoodsSold",
        "CostOfServices",
    ),
    # The combined element is the filer's diluted EPS when basic and diluted
    # are reported as one amount; a separate diluted fact takes precedence,
    # then the continuing-operations elements (see ``EPS_TAGS``).
    "eps": EPS_TAGS,
}
REVENUE_COMPONENTS = ("SalesRevenueGoodsNet", "SalesRevenueServicesNet")
# Positive diluted EPS above the share price (a P/E below one) is not a
# plausible reported value for a listed common share; it indicates an XBRL
# scale error (for example 1,730,000 for $1.73).
IMPLAUSIBLE_EPS = "Reported positive EPS exceeds the decision share price, which indicates a filing scale error. EPS valuation is excluded for this filing."
FUNDAMENTAL_STRATEGIES = ("quality", "quality_value", "value_momentum")


def filing_available(filed: date):
    following = calendar.sessions(filed + timedelta(days=1), filed + timedelta(days=15))
    if not following:
        raise ResearchError(
            "The filing date is outside the supported exchange-calendar range."
        )
    return calendar.available_time(following[0])


def normalize(
    symbol: str,
    cik: str,
    company: dict,
    submissions: dict,
    class_evidence: dict | None = None,
) -> tuple[tuple[AnnualStatement, ...], list[str]]:
    """Normalize annual periods without quarter proration or unit substitution."""
    issues = []
    facts = company.get("facts", {}).get("us-gaap", {})
    if not facts:
        return (), [
            "No supported US-GAAP company facts. Foreign/IFRS and custom-taxonomy statements are not synthesized."
        ]
    if submissions.get("entityType") not in (None, "", "operating"):
        return (), [
            "Issuer is not classified as an operating company in the SEC submission metadata."
        ]
    class_evidence = class_evidence or {}
    groups: dict[tuple, dict[str, set[Decimal]]] = {}
    filed_dates, forms = {}, {}
    wanted = {tag for tags in TAGS.values() for tag in tags} | set(REVENUE_COMPONENTS)
    for tag in wanted:
        unit = "USD/shares" if tag in TAGS["eps"] else "USD"
        for item in facts.get(tag, {}).get("units", {}).get(unit, []):
            if item.get("form") not in ("10-K", "10-K/A"):
                continue
            try:
                end = date.fromisoformat(item["end"])
                filed = date.fromisoformat(item["filed"])
                start = date.fromisoformat(item["start"]) if item.get("start") else None
                accession = item["accn"]
                if not re.fullmatch(r"\d{10}-\d{2}-\d{6}", accession) or end > filed:
                    continue
                if start is not None and not 330 <= (end - start).days <= 400:
                    continue  # Not an annual flow; no arbitrary YTD-to-TTM conversion.
                if tag != "Assets" and start is None:
                    continue
                value = decimal(item["val"], "SEC fact")
            except (KeyError, TypeError, ValueError):
                issues.append(f"Invalid {tag} fact excluded.")
                continue
            key = (accession, start, end)
            groups.setdefault(key, {}).setdefault(tag, set()).add(value)
            if accession in filed_dates and filed_dates[accession] != filed:
                raise ResearchError(
                    f"Conflicting filing dates for SEC accession {accession}."
                )
            filed_dates[accession], forms[accession] = filed, item["form"]
    output = []
    for (accession, start, end), values in sorted(
        groups.items(), key=lambda pair: (pair[0][2], pair[0][0], str(pair[0][1]))
    ):
        if start is None:
            continue
        sources, row_issues, conflicted = {}, [], set()

        def value_for(name: str):
            pool = (
                groups.get((accession, None, end), {}) if name == "assets" else values
            )
            for tag in TAGS[name]:
                candidates = pool.get(tag, set())
                if len(candidates) > 1:
                    conflicted.add(name)
                    row_issues.append(
                        f"Conflicting {tag} values in the same filing/period; not selected."
                    )
                    return None
                if candidates:
                    sources[name] = tag
                    return next(iter(candidates))
            return None

        assets = value_for("assets")
        gross = value_for("gross_profit")
        if gross is None and "gross_profit" not in conflicted:
            # Only exactly matched flow durations, units and accession can be
            # subtracted. Revenue and cost from a different filing never mix.
            revenue = value_for("revenue")
            if revenue is None and "revenue" not in conflicted:
                goods_rev_cand = values.get("SalesRevenueGoodsNet", set())
                srv_rev_cand = values.get("SalesRevenueServicesNet", set())
                if len(goods_rev_cand) > 1 or len(srv_rev_cand) > 1:
                    conflicted.add("revenue")
                    row_issues.append(
                        "Conflicting component revenue values in the same filing/period; not selected."
                    )
                else:
                    goods_rev = next(iter(goods_rev_cand)) if goods_rev_cand else None
                    srv_rev = next(iter(srv_rev_cand)) if srv_rev_cand else None
                    if goods_rev is not None and srv_rev is not None:
                        revenue = goods_rev + srv_rev
                        sources["revenue"] = (
                            "SalesRevenueGoodsNet + SalesRevenueServicesNet"
                        )
                    elif goods_rev is not None:
                        revenue = goods_rev
                        sources["revenue"] = "SalesRevenueGoodsNet"
                    elif srv_rev is not None:
                        revenue = srv_rev
                        sources["revenue"] = "SalesRevenueServicesNet"

            # Determine economically complete cost of goods and services:
            # 1. Primary aggregate cost tags: CostOfRevenue, then CostOfGoodsAndServicesSold
            cost = None
            cost_source = None
            for tag in ("CostOfRevenue", "CostOfGoodsAndServicesSold"):
                candidates = values.get(tag, set())
                if len(candidates) > 1:
                    conflicted.add("cost")
                    row_issues.append(
                        f"Conflicting {tag} values in the same filing/period; not selected."
                    )
                    break
                if candidates:
                    cost = next(iter(candidates))
                    cost_source = tag
                    break

            # 2. Component cost tags if aggregate tag absent
            if cost is None and "cost" not in conflicted:
                cogs_cand = values.get("CostOfGoodsSold", set())
                cos_cand = values.get("CostOfServices", set())
                if len(cogs_cand) > 1 or len(cos_cand) > 1:
                    conflicted.add("cost")
                    row_issues.append(
                        "Conflicting component cost values in the same filing/period; not selected."
                    )
                else:
                    cogs = next(iter(cogs_cand)) if cogs_cand else None
                    cos = next(iter(cos_cand)) if cos_cand else None
                    if cogs is not None and cos is not None:
                        cost = cogs + cos
                        cost_source = "CostOfGoodsSold + CostOfServices"
                    elif cos is not None and cogs is None:
                        cost = cos
                        cost_source = "CostOfServices"
                    elif cogs is not None and cos is None:
                        # Detect partial-cost fallback: if filing reports service revenue but no service cost
                        srv_rev_cand = values.get("SalesRevenueServicesNet", set())
                        srv_rev = (
                            next(iter(srv_rev_cand))
                            if srv_rev_cand and len(srv_rev_cand) == 1
                            else ZERO
                        )
                        if srv_rev > ZERO:
                            row_issues.append(
                                "Partial-cost fallback rejected: filing reports service revenue without service cost."
                            )
                        else:
                            cost = cogs
                            cost_source = "CostOfGoodsSold"

            if (
                revenue is not None
                and cost is not None
                and "cost" not in conflicted
                and "revenue" not in conflicted
            ):
                gross = revenue - cost
                sources["cost"] = cost_source
                sources["gross_profit"] = sources["revenue"] + " - " + cost_source
        # Eligibility belongs to this accession, never today's ticker count.
        evidence = class_evidence.get(accession, {})
        eps_compatible = bool(
            evidence.get("compatible")
            and evidence.get("accession") == accession
            and evidence.get("filed") == str(filed_dates[accession])
            and evidence.get("cik") == cik
            and evidence.get("symbol") == symbol
        )
        eps = value_for("eps") if eps_compatible else None
        if evidence.get("url"):
            key = (
                "eps_evidence"
                if evidence.get("class_verified") is False
                else "share_class_evidence"
            )
            sources[key] = evidence["url"]
        if evidence.get("class_verified") is False:
            sources["eps_policy"] = EPS_VERSION
        if evidence.get("sha256"):
            sources["share_class_evidence_sha256"] = evidence["sha256"]
        if not eps_compatible:
            row_issues.append(
                evidence.get("reason")
                or "No dated filing-specific common-share mapping. EPS valuation is excluded; today's ticker list is not evidence of past share classes."
            )
        if assets is not None and assets <= ZERO:
            row_issues.append(
                "Nonpositive assets cannot be a profitability denominator."
            )
            assets = None
        if gross is None and eps is None:
            continue
        if gross is None or assets is None:
            row_issues.append("Matched annual gross profit/assets are unavailable.")
        if eps is None:
            row_issues.append("Compatible reported diluted EPS is unavailable.")
        filed = filed_dates[accession]
        output.append(
            AnnualStatement(
                symbol,
                cik,
                start,
                end,
                filed,
                filing_available(filed),
                accession,
                forms[accession],
                assets,
                gross,
                eps,
                eps_compatible,
                sources,
                tuple(row_issues),
            )
        )
    if not output:
        issues.append(
            "No supported complete annual periods were found. Quarterly/custom/other-currency facts were not substituted."
        )
    return tuple(
        sorted(output, key=lambda s: (s.end, s.available_at, s.accession, s.start))
    ), sorted(set(issues))


def as_of(
    statements: tuple[AnnualStatement, ...], decision: date
) -> AnnualStatement | None:
    cutoff = calendar.available_time(decision)
    eligible = [
        s
        for s in statements
        if s.available_at <= cutoff
        and s.end <= decision
        and (decision - s.end).days <= 550
        and decision < date.fromisoformat(s.sources.get("valid_before", "9999-12-31"))
    ]
    if not eligible:
        return None
    # First choose the latest fiscal end; revisions of that end take effect only
    # after their own filing-availability date, never retroactively.
    end = max(s.end for s in eligible)
    candidates = [s for s in eligible if s.end == end]
    latest = max(s.available_at for s in candidates)
    candidates = [s for s in candidates if s.available_at == latest]
    # A filing with multiple valid annual durations is ambiguous rather than an
    # invitation to choose a convenient length or manufacture TTM.
    financials = {(s.start, s.assets, s.gross_profit, s.eps) for s in candidates}
    if len(financials) > 1:
        return None
    return sorted(candidates, key=lambda s: s.accession)[-1]


def inputs(
    dataset: Dataset, symbol: str, decision: date, *, issue_index=None
) -> tuple[dict, str | None]:
    statement = as_of(dataset.fundamentals.get(symbol, ()), decision)
    if statement is None:
        return (
            {},
            "No unambiguous annual SEC filing available at this decision (or fiscal end older than 550 days).",
        )
    cutoff = calendar.available_time(decision)
    bars = [
        b
        for b in dataset.bars[symbol]
        if statement.filed < b.session <= decision
        and (b.available_at is None or b.available_at <= cutoff)
    ]
    if not bars or bars[-1].session != decision:
        return {}, "A current decision-session price is required."
    values = {
        "filing": {
            "cik": statement.cik,
            "accession": statement.accession,
            "start": str(statement.start),
            "end": str(statement.end),
            "filed": str(statement.filed),
            "available_at": statement.available_at.isoformat(),
            "form": statement.form,
            "sources": statement.sources,
            "issues": statement.issues,
            "url": f"https://www.sec.gov/Archives/edgar/data/{int(statement.cik)}/{statement.accession.replace('-', '')}/",
        }
    }
    if statement.assets and statement.gross_profit is not None:
        values["profitability"] = statement.gross_profit / statement.assets
    elif statement.gross_profit is None:
        sector = dataset.sectors.get(symbol, "Unknown")
        if sector in ("Financials", "Utilities", "Real Estate"):
            values["profitability_issue"] = (
                f"Gross profit is not applicable for {sector} under US-GAAP."
            )
        else:
            values["profitability_issue"] = next(
                (
                    issue
                    for issue in statement.issues
                    if "partial-cost" in issue.lower()
                    or "gross profit" in issue.lower()
                    or "cost" in issue.lower()
                ),
                "Annual gross profit is unavailable in filing.",
            )
    elif not statement.assets or statement.assets <= ZERO:
        values["profitability_issue"] = "Filing reports nonpositive or missing assets."
    action_days = calendar.sessions(statement.filed + timedelta(days=1), decision)
    known_days = {bar.session for bar in bars}
    from .research_data import blocked_inputs

    split_history_complete = all(
        day in known_days for day in action_days
    ) and not blocked_inputs(
        dataset, {symbol}, statement.filed, decision, "signals", issue_index=issue_index
    )
    if (
        statement.eps is not None
        and statement.eps_compatible
        and split_history_complete
    ):
        factor = ONE
        # EPS is in the share basis reported by that filing. Apply only splits
        # after its filing date and through this decision, not all future splits.
        for bar in bars:
            if statement.filed < bar.session <= decision:
                factor *= bar.split
        eps_asof = statement.eps / factor
        # A loss can exceed the share price; a positive P/E below one cannot
        # be a plausible reported value and indicates an XBRL scale error.
        if eps_asof > bars[-1].close:
            values["valuation_issue"] = IMPLAUSIBLE_EPS
        else:
            values["eps_asof"] = eps_asof
            values["earnings_yield"] = eps_asof / bars[-1].close
    elif statement.eps is not None and not split_history_complete:
        values["valuation_issue"] = (
            "Price/action history after this filing is incomplete; intervening split units cannot be verified."
        )
    elif not statement.eps_compatible:
        values["valuation_issue"] = next(
            (
                issue
                for issue in statement.issues
                if "class" in issue.lower() or "ticker" in issue.lower()
            ),
            "Dated filing-specific EPS share units are unavailable.",
        )
    return values, None


def attach(
    store: Store,
    dataset_id: str,
    progress,
    provider: Provider | None = None,
    *,
    refresh=False,
    allow_empty=False,
    force_facts=False,
) -> dict:
    requested = next((row for row in store.datasets() if row["id"] == dataset_id), None)
    if requested is None:
        raise ResearchError("That dataset was not found. Choose one from Data.")
    if requested["kind"] == "synthetic":
        raise ResearchError(
            "SEC fundamentals cannot be attached to fictional practice symbols. Choose an actual market dataset."
        )
    base = store.dataset(
        requested.get("metadata", {}).get("price_dataset_id", dataset_id)
    )
    api = provider or Provider(store)
    try:
        progress(3, "Loading the SEC issuer/ticker directory")
        directory = api.get(
            "sec",
            "https://www.sec.gov/files/company_tickers_exchange.json",
            ttl=0 if refresh else 86400,
        )
        rows = [dict(zip(directory["fields"], row)) for row in directory["data"]]
        mapping = {}
        for row in rows:
            mapping.setdefault(str(row["ticker"]).upper().replace(".", "-"), set()).add(
                str(row["cik"]).zfill(10)
            )
        statements, coverage, source_hashes = {}, [], {}
        symbols = [
            s
            for s in base.bars
            if s != "SPY" and s not in base.metadata.get("dependency_symbols", [])
        ]
        last_session = max(bar.session for bars in base.bars.values() for bar in bars)
        first_session = min(bar.session for bars in base.bars.values() for bar in bars)
        from .research_data import indexed_issues

        issue_index = indexed_issues(base)
        # Two issuer pipelines share the provider request gate. Ordinary
        # acquisition uses structured facts, without historical report bodies.
        parallel = hasattr(api, "fork") and len(symbols) > 1
        progress_lock = threading.Lock()
        completed = 0
        readers = {}

        def cache_stats():
            if not parallel:
                return getattr(api, "annual_cache_stats", {})
            return {
                key: sum(
                    getattr(reader, "annual_cache_stats", {}).get(key, 0)
                    for reader in readers.values()
                )
                for key in ("reused", "downloaded")
            }

        def report(symbol, filing=None, total=None):
            with progress_lock:
                stats = cache_stats()
                detail = f", filing {filing}/{total}" if filing is not None else ""
                progress(
                    5 + round(completed / max(len(symbols), 1) * 85),
                    f"Preparing SEC financials: {symbol} ({completed}/{len(symbols)} companies complete{detail}; "
                    f"{stats.get('reused', 0):,} histories reused, {stats.get('downloaded', 0):,} refreshed)",
                )

        def read_symbol(symbol):
            reader = api.fork() if parallel else api
            with progress_lock:
                readers[symbol] = reader
            issuer_statements, issuer_coverage, issuer_hashes = {}, [], {}
            report(symbol)
            ciks = mapping.get(symbol.replace(".", "-"), set())
            from .historical_issuers import mapping_evidence

            historical_issuer = mapping_evidence(base.metadata, symbol)
            if historical_issuer and historical_issuer["cik"] is None:
                issuer_coverage.append(
                    {
                        "symbol": symbol,
                        "records": 0,
                        "historical_issuer_evidence": historical_issuer,
                        "reason": "The reviewed issuer filed with a bank regulator, not the SEC; no SEC annual financials exist for it.",
                        "quality_ready": False,
                        "value_ready": False,
                    }
                )
                return (
                    issuer_statements,
                    issuer_coverage,
                    issuer_hashes,
                    reader.observations if parallel else [],
                )
            if historical_issuer:
                ciks = {historical_issuer["cik"]}
            if len(ciks) != 1:
                issuer_coverage.append(
                    {
                        "symbol": symbol,
                        "records": 0,
                        "reason": "No unique current SEC issuer mapping. Historical ticker reuse is not inferred.",
                        "quality_ready": False,
                        "value_ready": False,
                    }
                )
                return (
                    issuer_statements,
                    issuer_coverage,
                    issuer_hashes,
                    reader.observations if parallel else [],
                )
            cik = next(iter(ciks))
            try:
                submissions = reader.get(
                    "sec",
                    f"https://data.sec.gov/submissions/CIK{cik}.json",
                    ttl=0 if refresh else 3600,
                )
                company = read_companyfacts(reader, cik, submissions, force=force_facts)
            except ResourceMissing:
                issuer_coverage.append(
                    {
                        "symbol": symbol,
                        "cik": cik,
                        "records": 0,
                        "reason": "SEC has no published submissions/companyfacts resource for this issuer (HTTP 404). No statements are synthesized.",
                        "quality_ready": False,
                        "value_ready": False,
                    }
                )
                return (
                    issuer_statements,
                    issuer_coverage,
                    issuer_hashes,
                    reader.observations if parallel else [],
                )
            if (
                str(company.get("cik", "")).zfill(10) != cik
                or str(submissions.get("cik", "")).zfill(10) != cik
            ):
                raise ResearchError(f"SEC issuer identity mismatch for {symbol}.")
            class_evidence = assess(
                symbol,
                cik,
                company,
                str(first_session - timedelta(days=550)),
                str(last_session),
            )
            normalized, issues = normalize(
                symbol, cik, company, submissions, class_evidence
            )
            # A reviewed Rule 12g-3 predecessor filed the listed shares'
            # annual reports before the successor registrant existed.
            from .historical_issuers import predecessors

            prior_sources, prior_coverage = [], []
            for proof in [] if historical_issuer else predecessors(symbol, cik, reader):
                prior = proof["cik"]
                prior_submissions = reader.get(
                    "sec",
                    f"https://data.sec.gov/submissions/CIK{prior}.json",
                    ttl=0 if refresh else 3600,
                )
                prior_company = read_companyfacts(
                    reader, prior, prior_submissions, force=force_facts
                )
                if (
                    str(prior_company.get("cik", "")).zfill(10) != prior
                    or str(prior_submissions.get("cik", "")).zfill(10) != prior
                ):
                    raise ResearchError(f"SEC issuer identity mismatch for {symbol}.")
                prior_classes = assess(
                    symbol,
                    prior,
                    prior_company,
                    str(first_session - timedelta(days=550)),
                    str(last_session),
                )
                prior_rows, _ = normalize(
                    symbol, prior, prior_company, prior_submissions, prior_classes
                )
                effective = date.fromisoformat(proof["effective"])
                marks = {"predecessor_issuer": proof["url"]}
                if proof.get("valid_before"):
                    marks["valid_before"] = proof["valid_before"]
                prior_rows = tuple(
                    replace(row, sources={**row.sources, **marks})
                    for row in prior_rows
                    if row.filed < effective
                )
                normalized = tuple(
                    sorted(
                        normalized + prior_rows,
                        key=lambda s: (s.end, s.available_at, s.accession, s.start),
                    )
                )
                class_evidence = {**class_evidence, **prior_classes}
                prior_sources.append(
                    {
                        "companyfacts": prior_company,
                        "submissions": prior_submissions,
                        "filed_share_classes": prior_classes,
                    }
                )
                prior_coverage.append(
                    {
                        "cik": prior,
                        "name": proof["name"],
                        "effective": proof["effective"],
                        "valid_before": proof.get("valid_before"),
                        "url": proof["url"],
                        "records": len(prior_rows),
                    }
                )
            if prior_coverage and normalized:
                issues = [i for i in issues if "No supported" not in i]
            issuer_statements[symbol] = normalized
            latest = as_of(normalized, last_session)
            latest_inputs, latest_issue = inputs(
                replace(base, fundamentals={symbol: normalized}),
                symbol,
                last_session,
                issue_index=issue_index,
            )
            coverage_issues = issues + (
                list(latest.issues)
                if latest
                else [latest_issue or "No recent annual filing available."]
            )
            if latest_inputs.get("valuation_issue"):
                coverage_issues.append(latest_inputs["valuation_issue"])
            verified_classes = sum(
                bool(row.get("compatible")) for row in class_evidence.values()
            )
            if verified_classes < len(class_evidence):
                coverage_issues.append(
                    f"{len(class_evidence) - verified_classes} of {len(class_evidence)} EPS accessions are excluded by the lightweight share-basis policy."
                )
            issuer_hashes[symbol] = hashlib.sha256(
                json.dumps(
                    {
                        "companyfacts": company,
                        "submissions": submissions,
                        "filed_share_classes": class_evidence,
                        **({"predecessors": prior_sources} if prior_sources else {}),
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode()
            ).hexdigest()
            issuer_coverage.append(
                {
                    "symbol": symbol,
                    "cik": cik,
                    "records": len(normalized),
                    "historical_issuer_evidence": historical_issuer,
                    **(
                        {"predecessor_issuers": prior_coverage}
                        if prior_coverage
                        else {}
                    ),
                    "reason": "; ".join(dict.fromkeys(coverage_issues)),
                    "quality_ready": latest_inputs.get("profitability", ZERO) > ZERO,
                    "value_ready": latest_inputs.get("earnings_yield", ZERO) > ZERO,
                    "latest_period": str(latest.end) if latest else None,
                    "latest_filed": str(latest.filed) if latest else None,
                    "available_at": latest.available_at.isoformat() if latest else None,
                    "filed_share_classes_digest": store.capture_source(
                        json.dumps(
                            list(class_evidence.values()),
                            sort_keys=True,
                            separators=(",", ":"),
                        ).encode()
                    ),
                    "eps_checks": len(class_evidence),
                    "eps_accepted": verified_classes,
                }
            )
            return (
                issuer_statements,
                issuer_coverage,
                issuer_hashes,
                reader.observations if parallel else [],
            )

        def completed_symbol(symbol):
            nonlocal completed
            result = read_symbol(symbol)
            with progress_lock:
                completed += 1
            report(symbol)
            return result

        pool = ThreadPoolExecutor(max_workers=2) if parallel else None
        try:
            results = (
                pool.map(completed_symbol, symbols)
                if pool
                else map(completed_symbol, symbols)
            )
            for (
                issuer_statements,
                issuer_coverage,
                issuer_hashes,
                observations,
            ) in results:
                statements.update(issuer_statements)
                coverage.extend(issuer_coverage)
                source_hashes.update(issuer_hashes)
                api.observations.extend(observations)
        finally:
            if pool:
                pool.shutdown(wait=True, cancel_futures=True)
        if parallel:
            api.annual_cache_stats = cache_stats()
        count = sum(len(items) for items in statements.values())
        if not count and not allow_empty:
            raise ResearchError(
                "No supported annual SEC statements were available for this dataset. No combined snapshot was created."
            )
        policy = {
            "normalizer": VERSION,
            "availability": AVAILABILITY,
            "staleness_days": 550,
            "units": "USD; reported diluted EPS USD/shares (EarningsPerShareDiluted, else the combined EarningsPerShareBasicAndDiluted amount, else diluted EPS from continuing operations when the filing reports no whole-entity net element). Positive EPS above the decision share price is rejected as a likely scale error.",
            "periods": "Annual 330–400 days; 10-K and 10-K/A only",
            "share_class_evidence_storage": "shared-per-security-v1",
            "eps_policy": EPS_VERSION,
            "issuer_mapping": "Current SEC directory, reviewed filing evidence for the exact historical quote vintage, or reviewed Rule 12g-3 predecessor registrants of the same listed shares (their reports filed before the succession); never an inferred successor ticker.",
            "share_basis": EPS_WARNING,
            "refresh_policy": "Annual filing changes trigger financial-history refresh; otherwise captured histories can be reused for up to 30 days. Manual SEC refresh forces a new capture.",
        }
        raw = json.dumps(
            {"price_digest": base.digest, "policy": policy, "sources": source_hashes},
            sort_keys=True,
        ).encode()
        digest = hashlib.sha256(raw).hexdigest()
        meta = {
            **base.metadata,
            "bundle_role": "complete",
            "price_dataset_id": base.id,
            "price_digest": base.digest,
            "fundamentals": {
                **policy,
                "record_count": count,
                "coverage": coverage,
                "retrieved_at": now(),
                "observation_ids": api.observations,
                "source_hashes": source_hashes,
                "refresh_stats": getattr(api, "annual_cache_stats", {}),
            },
        }
        enriched = replace(
            base,
            id=digest[:24],
            name=base.name,
            digest=digest,
            metadata=meta,
            fundamentals=statements,
            source=base.source + " + SEC EDGAR annual filings",
        )
        original_summary = next(
            item for item in store.datasets() if item["id"] == base.id
        )
        warnings = list(original_summary["warnings"]) + [
            AVAILABILITY,
            "Annual US-GAAP support only; missing/custom/IFRS inputs are excluded. Annual metrics are not TTM estimates.",
            EPS_WARNING,
            "SEC filings are versioned by accession and filing date. Issuer mappings use the current SEC directory or explicit dated filing evidence; historical universe membership remains independently constrained.",
            "Earnings yield uses reported diluted EPS and explicit split adjustments; no current vendor valuation ratios or current share counts are backfilled.",
        ]
        progress(97, "Saving the filing-versioned combined dataset")
        return store.save_dataset(enriched, raw, warnings)
    finally:
        if provider is None:
            api.close()
