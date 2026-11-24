import { lazy, Suspense, useState, useEffect } from "react";
import { useQueries, useQuery } from "@tanstack/react-query";
import { useLocation } from "react-router-dom";
import {
  ArrowRight,
  Download,
  FlaskConical,
  Info,
  Layers,
  Play,
} from "lucide-react";
import { api, download, money, percent, points, shortDate } from "./api";
import {
  Badge,
  DisclosureCard,
  Empty,
  MetricStrip,
  Notice,
  PeriodPicker,
} from "./components";
import type { Period, Run, State, Strategy } from "./types";
import Validation from "./Validation";
import { SignalAudit, FactorAvailability } from "./Fundamentals";
import ResearchManager, { DeleteResearchButton } from "./ResearchManager";
const Chart = lazy(() => import("./Chart"));

function displayedExposure(run: Run, period: Period) {
  const rows = run.curve.slice(run.windows[period].start_index);
  if (!rows.length) return { cash: null, stocks: null };
  const cash =
    rows.reduce((sum, row) => sum + Number(row.cash) / Number(row.equity), 0) /
    rows.length;
  const stocks =
    rows.reduce(
      (sum, row) =>
        sum +
        (Number(row.equity) - Number(row.cash) - Number(row.receivable)) /
          Number(row.equity),
      0,
    ) / rows.length;
  return { cash, stocks };
}

export default function Research({
  state,
  onRun,
  onInfo,
  onData,
}: {
  state: State;
  onRun: (id: string) => void;
  onInfo: (s: Strategy) => void;
  onData: () => void;
}) {
  const families = state.strategies.filter((strategy) => !strategy.variant_of);
  const location = useLocation();
  const requestedRun = new URLSearchParams(location.search).get("run") ?? "";
  const [section, setSection] = useState<"library" | "results" | "validation">(
    new URLSearchParams(location.search).get("section") === "validation"
      ? "validation"
      : requestedRun
        ? "results"
        : "library",
  );
  const [selected, setSelected] = useState(requestedRun);
  const [compare, setCompare] = useState<string[]>([]);
  const [period, setPeriod] = useState<Period>("All");
  const identifier = state.runs.some((r) => r.id === selected)
    ? selected
    : state.runs[0]?.id;
  useEffect(() => {
    setCompare((ids) =>
      ids.filter((id) => state.runs.some((r) => r.id === id)),
    );
  }, [state.runs]);
  const result = useQuery({
    queryKey: ["result", identifier],
    queryFn: () => api<Run>(`/results/${identifier}?view=true`),
    enabled: !!identifier && section === "results",
  });
  const compared = useQueries({
    queries: compare.map((id) => ({
      queryKey: ["result", id],
      queryFn: () => api<Run>(`/results/${id}?view=true`),
    })),
  });
  const comparison = compared.flatMap((query) =>
    query.data ? [query.data] : [],
  );
  const toggleCompare = (id: string) =>
    setCompare((current) =>
      current.includes(id)
        ? current.filter((x) => x !== id)
        : current.length < 3
          ? [...current, id]
          : current,
    );
  return (
    <>
      <div className="page-heading">
        <h1>Research</h1>
        <div className="heading-actions">
          <ResearchManager category="Backtests" />
          <button
            className="button"
            onClick={() =>
              state.datasets.length ? onRun("momentum") : onData()
            }
          >
            <Play size={16} />
            New backtest
          </button>
        </div>
      </div>
      <div className="subnav" role="tablist" aria-label="Research sections">
        <button
          role="tab"
          aria-selected={section === "library"}
          onClick={() => setSection("library")}
        >
          Strategy library <span>{families.length}</span>
        </button>
        <button
          role="tab"
          aria-selected={section === "results"}
          onClick={() => setSection("results")}
        >
          Backtest results <span>{state.runs.length}</span>
        </button>
        <button
          role="tab"
          aria-selected={section === "validation"}
          onClick={() => setSection("validation")}
        >
          Validation
        </button>
      </div>
      {section === "validation" ? (
        <Validation state={state} />
      ) : section === "library" ? (
        <>
          <div className="strategy-grid">
            {families.map((s, i) => (
              <article
                className={`card strategy-card ${!s.implemented ? "planned" : ""}`}
                key={s.id}
              >
                <div className="card-top">
                  <span className="strategy-icon">
                    {i === 0 ? (
                      <ArrowRight size={22} />
                    ) : i === 1 ? (
                      <Layers size={22} />
                    ) : (
                      <FlaskConical size={22} />
                    )}
                  </span>
                  <Badge tone={s.implemented ? "green" : ""}>
                    {s.research_only
                      ? "Research only"
                      : s.implemented
                        ? "Ready to research"
                        : "Fundamentals milestone"}
                  </Badge>
                </div>
                <span className="eyebrow">{s.category}</span>
                <h3>{s.name}</h3>
                <p>
                  {s.description}
                  {s.frequency === "monthly" && " Rebalances at month-end."}
                </p>
                <div className="strategy-foot">
                  <button className="text-link" onClick={() => onInfo(s)}>
                    How it works <Info size={14} />
                  </button>
                  {s.implemented && (
                    <div className="inline">
                      {[
                        s,
                        ...state.strategies.filter(
                          (v) => v.variant_of === s.id,
                        ),
                      ].map((version) => (
                        <button
                          className="button small secondary"
                          key={version.id}
                          onClick={() =>
                            state.datasets.length ? onRun(version.id) : onData()
                          }
                        >
                          {version.variant_of ? "Backtest weekly" : "Backtest"}
                          <ArrowRight size={14} />
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </article>
            ))}
          </div>
          <DisclosureCard title="Backtesting notes">
            <div className="card-body">
              <p>
                Backtests test a hypothesis using historical data. Paper trading
                requires separate approval. Fundamental strategies need a
                snapshot with market data and SEC filings.
              </p>
            </div>
          </DisclosureCard>
        </>
      ) : !state.runs.length ? (
        <div className="card">
          <Empty
            title="Your first experiment starts here"
            action={
              <button
                className="button"
                onClick={() =>
                  state.datasets.length ? onRun("momentum") : onData()
                }
              >
                Set up a backtest <ArrowRight size={15} />
              </button>
            }
          >
            Add a dataset, choose an existing strategy, and save a reproducible
            result. Computation runs in the background.
          </Empty>
        </div>
      ) : (
        <>
          <DisclosureCard
            title="Saved backtests"
            summary={
              state.runs.length +
              " saved · Select a result or compare up to three"
            }
          >
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Compare</th>
                    <th>Experiment</th>
                    <th>Data / period</th>
                    <th>Return</th>
                    <th>Largest decline</th>
                    <th>Open</th>
                  </tr>
                </thead>
                <tbody>
                  {state.runs.map((run, i) => (
                    <tr
                      key={run.id}
                      className={identifier === run.id ? "selected-row" : ""}
                    >
                      <td>
                        <input
                          type="checkbox"
                          aria-label={`Compare ${run.strategy.name} experiment ${state.runs.length - i}`}
                          checked={compare.includes(run.id)}
                          disabled={
                            compare.length >= 3 && !compare.includes(run.id)
                          }
                          onChange={() => toggleCompare(run.id)}
                        />
                      </td>
                      <td>
                        <strong>{run.strategy.name}</strong>
                        <small>
                          v{run.strategy.version} ·{" "}
                          {run.trade_count.toLocaleString()} simulated fills
                        </small>
                      </td>
                      <td>
                        {run.dataset_name}
                        {run.coverage?.mode === "coverage_limited" && (
                          <small>
                            Coverage-limited · {run.coverage.excluded_count}{" "}
                            excluded
                          </small>
                        )}
                        {run.dataset_kind === "synthetic" && (
                          <Badge tone="amber">Synthetic</Badge>
                        )}
                        <small>
                          {shortDate(run.start)} – {shortDate(run.end)}
                        </small>
                        {run.sector_classification && (
                          <small>Current / last-known sector labels</small>
                        )}
                      </td>
                      <td>
                        {percent(run.metrics.return, true)}
                        {run.exposure && (
                          <small>
                            Avg {percent(run.exposure.mean_stock_weight)} stocks
                            / {percent(run.exposure.mean_cash_weight)} cash
                          </small>
                        )}
                      </td>
                      <td>{percent(run.metrics.drawdown)}</td>
                      <td>
                        <button
                          className="button small secondary"
                          onClick={() => {
                            setSelected(run.id);
                            setPeriod("All");
                          }}
                          aria-label={`View ${run.strategy.name} experiment ${state.runs.length - i}`}
                        >
                          View <ArrowRight size={14} />
                        </button>
                        <DeleteResearchButton
                          kind="result"
                          id={run.id}
                          name={`${run.strategy.name} experiment ${state.runs.length - i}`}
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </DisclosureCard>
          {compare.length > 0 && (
            <div className="card comparison">
              <div className="card-header">
                <div>
                  <h2>Compare experiments</h2>
                  <p>
                    Returns use each experiment’s displayed dates. Use identical
                    inputs for a fair comparison.
                  </p>
                </div>
                <button className="text-link" onClick={() => setCompare([])}>
                  Clear
                </button>
              </div>
              {compare.length < 2 ? (
                <p>Select one more experiment using the checkboxes above.</p>
              ) : comparison.length !== compare.length ? (
                <p>Loading comparison…</p>
              ) : (
                <>
                  <PeriodPicker value={period} onChange={setPeriod} />
                  {new Set(
                    comparison.map((r) =>
                      JSON.stringify([
                        r.dataset_id,
                        r.windows[period].start,
                        r.windows[period].end,
                        r.capital,
                        r.policy,
                        r.dividend_model,
                        r.coverage && { ...r.coverage, frequency: undefined },
                        r.engine_version,
                      ]),
                    ),
                  ).size > 1 && (
                    <Notice>
                      These experiments have different data, dates, capital,
                      engine versions or assumptions. Differences in returns
                      cannot be attributed only to the strategy.
                    </Notice>
                  )}
                  <div className="table-scroll">
                    <table>
                      <thead>
                        <tr>
                          <th>Strategy</th>
                          <th>Actual dates</th>
                          <th>Return</th>
                          <th>vs SPY</th>
                          <th>Largest decline</th>
                          <th>Avg stocks / cash</th>
                        </tr>
                      </thead>
                      <tbody>
                        {comparison.map((r) => (
                          <tr key={r.id}>
                            <td>
                              <strong>{r.strategy.name}</strong>
                              {r.coverage?.mode === "coverage_limited" && (
                                <small>
                                  Coverage-limited · {r.coverage.excluded_count}{" "}
                                  exclusions
                                </small>
                              )}
                              {r.dataset_kind === "synthetic" && (
                                <small>Synthetic practice</small>
                              )}
                            </td>
                            <td>
                              {shortDate(r.windows[period].start)} –{" "}
                              {shortDate(r.windows[period].end)}
                            </td>
                            <td>
                              {percent(r.windows[period].metrics.return, true)}
                            </td>
                            <td>
                              {points(r.windows[period].metrics.difference)}
                            </td>
                            <td>
                              {percent(r.windows[period].metrics.drawdown)}
                            </td>
                            <td>
                              {percent(displayedExposure(r, period).stocks)} /{" "}
                              {percent(displayedExposure(r, period).cash)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              )}
              {compared.some((q) => q.error) && (
                <Notice error>
                  Could not load a comparison. Clear the selection and try
                  again.
                </Notice>
              )}
            </div>
          )}
          {result.isPending ? (
            <div className="card loading" role="status">
              Loading saved result…
            </div>
          ) : result.error ? (
            <Notice error>
              {result.error.message}
              <button className="text-link" onClick={() => result.refetch()}>
                Try again
              </button>
            </Notice>
          ) : (
            result.data && (
              <RunDetail
                run={result.data}
                period={period}
                setPeriod={setPeriod}
              />
            )
          )}
        </>
      )}
    </>
  );
}

export function RunDetail({
  run,
  period,
  setPeriod,
}: {
  run: Run;
  period: Period;
  setPeriod: (p: Period) => void;
}) {
  const window = run.windows[period];
  const attribution = window.return_attribution;
  const exposure = displayedExposure(run, period);
  const coverage = run.coverage;
  const decisionExclusions = coverage?.decision_exclusions ?? [];
  const decisionStocks = new Set(decisionExclusions.map((row) => row.symbol));
  return (
    <>
      {run.coverage?.mode === "coverage_limited" && (
        <section className="card">
          <div className="card-body">
            <Notice>
              {run.coverage.warning ||
                "Coverage-limited research; exclusions can introduce bias."}
            </Notice>
            <details className="details">
              <summary>
                Coverage audit · {run.coverage.excluded_count} stocks excluded
              </summary>
              <p>
                {run.coverage.universe_count} stocks occurred in the requested
                universe. The availability policy was frozen before simulation.
                {run.coverage.price_window_policy &&
                  ` ${run.coverage.price_window_policy}`}
              </p>
              <div className="table-scroll">
                <table className="coverage-table">
                  <thead>
                    <tr>
                      <th>Stock</th>
                      <th>Excluded because</th>
                    </tr>
                  </thead>
                  <tbody>
                    {run.coverage.excluded?.map((row) => (
                      <tr key={row.symbol}>
                        <td>{row.symbol}</td>
                        <td>{row.reasons.join(" · ")}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
          </div>
        </section>
      )}
      <section className="card result-card">
        <div className="card-header">
          <div>
            <span className="eyebrow">BACKTEST · {run.dataset_name}</span>
            <h2>{run.strategy.name}</h2>
            <p>
              {shortDate(window.start)} – {shortDate(window.end)} ·{" "}
              {run.frequency} · {money(run.capital)} initial capital
            </p>
          </div>
          <button
            className="button secondary small"
            onClick={() => {
              if (run.audit_path)
                document.location.assign(`/api${run.audit_path}?download=true`);
              else download(`aperture-${run.id}.json`, run);
            }}
          >
            <Download size={15} />
            Export result
          </button>
        </div>
        {run.dataset_kind === "synthetic" && (
          <div className="synthetic-ribbon">
            Synthetic practice data · These returns have no investment meaning.
          </div>
        )}
        <MetricStrip metrics={window.metrics} />
        <p className="range-note allocation-summary">
          Average allocation: {percent(exposure.stocks)} stocks /{" "}
          {percent(exposure.cash)} cash.
        </p>
        <div className="chart-toolbar">
          <div className="legend">
            <span>
              <i />
              {run.strategy.name}
            </span>
            {window.metrics.benchmark_return !== null && (
              <span>
                <i className="spy" />
                SPY
              </span>
            )}
          </div>
          <PeriodPicker value={period} onChange={setPeriod} />
        </div>
        {window.limited && (
          <p className="range-note">
            The requested period exceeds this experiment’s history. Showing all
            available dates, {shortDate(window.start)} – {shortDate(window.end)}
            .
          </p>
        )}
        <Suspense
          fallback={<div className="chart loading">Loading chart…</div>}
        >
          <Chart run={run} period={period} />
        </Suspense>
        <div className="chart-foot">
          <span>Return rebased to 0% at the displayed start</span>
          <span>After modeled fees & slippage</span>
        </div>
      </section>
      {attribution && (
        <section className="card" aria-labelledby="return-attribution-title">
          <div className="card-header">
            <div>
              <h2 id="return-attribution-title">What drove the return</h2>
              <p>
                {shortDate(window.start)} – {shortDate(window.end)}
              </p>
            </div>
          </div>
          <div className="card-body">
            <dl className="facts">
              <div>
                <dt>Stock gain/loss before costs</dt>
                <dd>
                  {money(attribution.stock_gain)} ·{" "}
                  {percent(attribution.stock_return, true)}
                </dd>
              </div>
              <div>
                <dt>Trading costs · fees and slippage</dt>
                <dd>
                  {money(attribution.trading_cost_impact)} ·{" "}
                  {points(attribution.trading_cost_contribution)}
                </dd>
              </div>
              <div>
                <dt>
                  <strong>Net portfolio change</strong>
                </dt>
                <dd>
                  <strong>
                    {money(attribution.net_change)} ·{" "}
                    {percent(attribution.net_return, true)}
                  </strong>
                </dd>
              </div>
              {attribution.benchmark_gross_return != null && (
                <div>
                  <dt>SPY return before costs</dt>
                  <dd>{percent(attribution.benchmark_gross_return, true)}</dd>
                </div>
              )}
            </dl>
            <p className="field-hint">
              Stock gain/loss includes dividends and uses the holdings from this
              backtest. Position sizes and cash exposure still reflect the
              original cost assumptions.
            </p>
          </div>
        </section>
      )}
      {!!run.calendar_year_returns?.length && (
        <DisclosureCard
          title="Calendar-year returns"
          summary="Strategy vs SPY, after modeled costs"
        >
          <p className="card-body">
            Holdings carry across years. The dates show the valuations used,
            including partial years.
          </p>
          <div className="table-scroll">
            <table className="fundamental-table">
              <thead>
                <tr>
                  <th>Year</th>
                  <th>Valuation dates</th>
                  <th>Strategy</th>
                  <th>SPY</th>
                  <th>Difference</th>
                </tr>
              </thead>
              <tbody>
                {run.calendar_year_returns.map((year) => (
                  <tr key={year.year}>
                    <th scope="row">{year.year}</th>
                    <td>
                      {shortDate(year.start)} – {shortDate(year.end)}
                    </td>
                    <td>{percent(year.return, true)}</td>
                    <td>{percent(year.benchmark_return, true)}</td>
                    <td>{points(year.difference)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </DisclosureCard>
      )}
      <DisclosureCard title="Assumptions, costs & exposures">
        <div className="card-body">
          <dl className="facts">
            <div>
              <dt>Stock limit</dt>
              <dd>
                {percent(Number(run.policy.max_weight ?? 0.05))} per position
              </dd>
            </div>
            <div>
              <dt>Sector limit</dt>
              <dd>
                {percent(Number(run.policy.sector_cap ?? 0.25))} per sector
              </dd>
            </div>
            <div>
              <dt>Cash reserve</dt>
              <dd>
                At least {percent(Number(run.policy.cash_reserve ?? 0.02))}
              </dd>
            </div>
            <div>
              <dt>Modeled costs</dt>
              <dd>
                {run.policy.slippage_bps ?? 5} bps{" "}
                {run.trading_costs ? "base slippage" : "slippage"} +{" "}
                {run.policy.fee_bps ?? 1} bp{" "}
                {run.trading_costs ? "fee allowance + size adjustment" : "fee"},
                each side
              </dd>
            </div>
            {run.trading_costs && (
              <div>
                <dt>Full-run trading costs</dt>
                <dd>
                  {money(run.trading_costs.strategy.total)}
                  {run.trading_costs.strategy.average_bps != null &&
                    ` · ${run.trading_costs.strategy.average_bps.toFixed(1)} bps per dollar traded`}
                </dd>
              </div>
            )}
            <div>
              <dt>Cash return</dt>
              <dd>0% · no borrowing</dd>
            </div>
            <div>
              <dt>Annualized volatility</dt>
              <dd>{percent(window.metrics.volatility)}</dd>
            </div>
            <div>
              <dt>CAGR</dt>
              <dd>{percent(window.metrics.cagr)}</dd>
            </div>
          </dl>
          <p className="field-hint">
            Volatility needs 20 returns; CAGR needs one calendar year. A dash
            means insufficient history.
          </p>
          <p className="field-hint">
            Cash earns 0%. SPY is a fully invested buy-and-hold comparison.
            Average allocation includes the starting valuation of the displayed
            period.
          </p>
          <FactorAvailability
            decisions={run.decisions || []}
            start={window.start}
            end={window.end}
            expected={["quality", "quality_value", "value_momentum"].includes(
              run.strategy.id,
            )}
          />
          {run.sector_classification?.warning && (
            <p className="field-hint">{run.sector_classification.warning}</p>
          )}
          {!run.sector_classification && (
            <p className="field-hint">
              This saved result predates sector coverage auditing. Its original
              classifications and returns are preserved; refresh sectors in Data
              and select the new snapshot for another backtest.
            </p>
          )}
          <details className="details">
            <summary>Execution, dividends & benchmark</summary>
            <p>{run.execution_model}</p>
            {run.trading_costs && (
              <p>
                Strategy costs include {money(run.trading_costs.strategy.fees)}{" "}
                in fees and {money(run.trading_costs.strategy.slippage)} in
                slippage across the full run. SPY modeled costs were{" "}
                {money(run.trading_costs.benchmark.total)}.{" "}
                {run.trading_costs.strategy.without_liquidity_data > 0 &&
                  `${run.trading_costs.strategy.without_liquidity_data.toLocaleString()} fills used the missing-volume allowance.`}
              </p>
            )}
            <p>
              {run.dividend_model === "ex_date"
                ? "Total-return research: overnight holders’ distributions are reinvested at the ex-date close when still held, otherwise retained as cash. This is a research assumption, not payment-date cash availability."
                : "Splits adjust held shares. Dividends accrue to overnight holders on ex-date and become spendable on verified pay dates. Receivables are included in portfolio value."}
            </p>
            <p>{run.benchmark_model}</p>
            {run.engine_version && (
              <p>
                Research engine {run.engine_version}. Saved results retain the
                engine and inputs used when they were created.
              </p>
            )}
            <p className="digest">Input fingerprint: {run.source_digest}</p>
          </details>
        </div>
      </DisclosureCard>
      <DisclosureCard
        title="Research limitations"
        summary={
          decisionStocks.size > 0
            ? `${decisionStocks.size} ${coverage?.decision_scope === "supplemental" ? "supplemental" : "fixed-list"} ${decisionStocks.size === 1 ? "stock skipped" : "stocks skipped"} on one or more decision dates`
            : undefined
        }
      >
        <div className="card-body notes-list">
          {coverage?.decision_scope && <p>{coverage.warning}</p>}
          {decisionExclusions.length > 0 && (
            <details className="details">
              <summary>Decision exclusions</summary>
              <div className="table-scroll">
                <table className="coverage-table">
                  <thead>
                    <tr>
                      <th>Stock</th>
                      <th>Reason</th>
                      <th>Decisions</th>
                      <th>First</th>
                      <th>Last</th>
                    </tr>
                  </thead>
                  <tbody>
                    {decisionExclusions.map((row) => (
                      <tr key={`${row.symbol}:${row.reason}`}>
                        <td>{row.symbol}</td>
                        <td>{row.reason}</td>
                        <td>{row.decisions}</td>
                        <td>{row.first}</td>
                        <td>{row.last}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
          )}
          {run.notes.map((note) => (
            <p key={note}>{note}</p>
          ))}
        </div>
      </DisclosureCard>
      <SignalAudit
        collapsed
        decisions={run.decisions || []}
        auditPath={run.audit_path}
        strategyId={run.strategy.variant_of ?? run.strategy.id}
        fundamental={["quality", "quality_value", "value_momentum"].includes(
          run.strategy.id,
        )}
      />
      <DisclosureCard
        title="Simulated fills"
        summary={
          run.trade_count.toLocaleString() + " total · Full ledger in export"
        }
      >
        {run.trades.length ? (
          <>
            <p className="card-body">Showing up to the 50 most recent fills.</p>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Session</th>
                    <th>Stock</th>
                    <th>Side</th>
                    <th>Shares</th>
                    <th>Fill price</th>
                    <th>Fee</th>
                  </tr>
                </thead>
                <tbody>
                  {run.trades
                    .slice(-50)
                    .reverse()
                    .map((trade, i) => (
                      <tr key={`${trade.session}-${trade.symbol}-${i}`}>
                        <td>{shortDate(trade.session)}</td>
                        <td>
                          <strong>{trade.symbol}</strong>
                        </td>
                        <td>{trade.side}</td>
                        <td>
                          {Number(trade.quantity).toLocaleString("en-US", {
                            maximumFractionDigits: 6,
                          })}
                        </td>
                        <td>{money(trade.price)}</td>
                        <td>{money(trade.fee)}</td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </>
        ) : (
          <div className="card-body">
            <p>
              No simulated fills. Review the warm-up history and research
              limitations above.
            </p>
          </div>
        )}
      </DisclosureCard>
    </>
  );
}
