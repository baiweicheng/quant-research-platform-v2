import { lazy, Suspense, useState } from "react";
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
const Chart = lazy(() => import("./Chart"));

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
  const [section, setSection] = useState<"library" | "results">(
    requestedRun ? "results" : "library",
  );
  const [selected, setSelected] = useState(requestedRun);
  const [compare, setCompare] = useState<string[]>([]);
  const [period, setPeriod] = useState<Period>("All");
  const identifier = selected || state.runs[0]?.id;
  const result = useQuery({
    queryKey: ["result", identifier],
    queryFn: () => api<Run>(`/results/${identifier}`),
    enabled: !!identifier && section === "results",
  });
  const compared = useQueries({
    queries: compare.map((id) => ({
      queryKey: ["result", id],
      queryFn: () => api<Run>(`/results/${id}`),
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
        <button
          className="button"
          onClick={() => (state.datasets.length ? onRun("momentum") : onData())}
        >
          <Play size={16} />
          New backtest
        </button>
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
      </div>
      {section === "library" ? (
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
            establish that it will work in the future. AI-assisted discovery and
            point-in-time fundamentals come in later milestones.
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
                        {run.dataset_kind === "synthetic" && (
                          <Badge tone="amber">Synthetic</Badge>
                        )}
                        <small>
                          {shortDate(run.start)} – {shortDate(run.end)}
                        </small>
                      </td>
                      <td>{percent(run.metrics.return, true)}</td>
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
                        `${r.dataset_id}/${r.windows[period].start}/${r.windows[period].end}/${r.capital}/${JSON.stringify(r.policy)}`,
                    ),
                  ).size > 1 && (
                    <Notice>
                      These experiments have different data, dates, capital or
                      assumptions. Differences in returns cannot be attributed
                      only to the strategy.
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
                        </tr>
                      </thead>
                      <tbody>
                        {comparison.map((r) => (
                          <tr key={r.id}>
                            <td>
                              <strong>{r.strategy.name}</strong>
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

function RunDetail({
  run,
  period,
  setPeriod,
}: {
  run: Run;
  period: Period;
  setPeriod: (p: Period) => void;
}) {
  const window = run.windows[period];
  return (
    <>
      <section className="card result-card">
        <div className="card-header">
          <div>
            <span className="eyebrow">BACKTEST · {run.dataset_name}</span>
            <h2>{run.strategy.name}</h2>
            <p>
              {shortDate(window.start)} – {shortDate(window.end)} · Weekly ·{" "}
              {money(run.capital)} initial capital
            </p>
          </div>
          <button
            className="button secondary small"
            onClick={() => download(`aperture-${run.id}.json`, run)}
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
                <dd>5% per position</dd>
              </div>
              <div>
                <dt>Sector limit</dt>
                <dd>25% per sector</dd>
              </div>
              <div>
                <dt>Cash reserve</dt>
                <dd>At least 2%</dd>
              </div>
              <div>
                <dt>Modeled costs</dt>
                <dd>5 bps slippage + 1 bp fee, each side</dd>
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
                Splits adjust held shares. Dividends accrue to overnight holders
                on ex-date and become spendable on pay date. Receivables are
                included in portfolio value.
              </p>
              <p>{run.benchmark_model}</p>
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
