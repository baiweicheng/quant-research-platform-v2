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
import { Badge, Empty, MetricStrip, Notice, PeriodPicker } from "./components";
import type { Period, Run, State, Strategy } from "./types";
import Validation from "./Validation";
import { SignalAudit } from "./Fundamentals";
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
        <div>
          <span className="eyebrow">YOUR IDEAS, TESTED</span>
          <h1>Research with a clear view.</h1>
          <p>Understand the evidence before putting an idea to work.</p>
        </div>
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
          Strategy library <span>{state.strategies.length}</span>
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
          <div className="section-intro">
            <h2>A thoughtful starting point.</h2>
            <p>
              Established research families, with explicit definitions and
              limitations. Nothing here is approved for trading.
            </p>
          </div>
          <div className="strategy-grid">
            {state.strategies.map((s, i) => (
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
                    {s.implemented
                      ? "Ready to research"
                      : "Fundamentals milestone"}
                  </Badge>
                </div>
                <span className="eyebrow">{s.category}</span>
                <h3>{s.name}</h3>
                <p>{s.description}</p>
                <div className="strategy-foot">
                  <button className="text-link" onClick={() => onInfo(s)}>
                    How it works <Info size={14} />
                  </button>
                  {s.implemented && (
                    <button
                      className="button small secondary"
                      onClick={() =>
                        state.datasets.length ? onRun(s.id) : onData()
                      }
                    >
                      Backtest <ArrowRight size={14} />
                    </button>
                  )}
                </div>
              </article>
            ))}
          </div>
          <Notice>
            Backtesting explores a hypothesis. It does not approve a strategy or
            establish that it will work in the future. Fundamental strategies
            need a combined price + SEC dataset. AI-assisted discovery comes in
            a later milestone.
          </Notice>
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
          <div className="card runs-card">
            <div className="card-header">
              <div>
                <h2>Saved experiments</h2>
                <p>Select a result to explore, or compare up to three.</p>
              </div>
              <Badge>{state.runs.length} saved</Badge>
            </div>
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
          </div>
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
                    comparison.map(
                      (r) =>
                        `${r.dataset_id}/${r.windows[period].start}/${r.windows[period].end}/${r.capital}/${JSON.stringify(r.policy)}/${r.dividend_model}/${JSON.stringify(r.coverage)}/${r.engine_version}`,
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
  const exposure = displayedExposure(run, period);
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
                universe. The full-period availability policy was frozen before
                simulation.
              </p>
              <div className="table-scroll">
                <table>
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
        <div className="card-body exposure-disclosure">
          <Notice>
            <strong>
              Average allocation: {percent(exposure.stocks)} stocks /{" "}
              {percent(exposure.cash)} cash.
            </strong>{" "}
            Cash earns 0% in this simulation. SPY is a fully invested
            buy-and-hold comparison; the exposure can differ substantially. This
            average uses the displayed period, including its starting valuation.
          </Notice>
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
        </div>
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
      <div className="two-columns">
        <section className="card">
          <div className="card-header">
            <div>
              <h2>Know the assumptions</h2>
              <p>Every result carries its calculation context.</p>
            </div>
          </div>
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
                  {run.policy.slippage_bps ?? 5} bps slippage +{" "}
                  {run.policy.fee_bps ?? 1} bp fee, each side
                </dd>
              </div>
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
            <details className="details">
              <summary>Execution, dividends & benchmark</summary>
              <p>{run.execution_model}</p>
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
        </section>
        <section className="card">
          <div className="card-header">
            <div>
              <h2>Research limitations</h2>
              <p>Read these before interpreting performance.</p>
            </div>
          </div>
          <div className="card-body notes-list">
            {run.notes.map((note) => (
              <p key={note}>{note}</p>
            ))}
          </div>
        </section>
      </div>
      <SignalAudit
        decisions={run.decisions || []}
        auditPath={run.audit_path}
        fundamental={["quality", "quality_value", "value_momentum"].includes(
          run.strategy.id,
        )}
      />
      <section className="card">
        <div className="card-header">
          <div>
            <h2>Simulated fills</h2>
            <p>
              {run.trade_count.toLocaleString()} total · Most recent 50 shown ·
              Full ledger included in export
            </p>
          </div>
          <Badge>Simulation</Badge>
        </div>
        {run.trades.length ? (
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
        ) : (
          <div className="card-body">
            <p>
              No simulated fills. Review the warm-up history and research
              limitations above.
            </p>
          </div>
        )}
      </section>
    </>
  );
}
