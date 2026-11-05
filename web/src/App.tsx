import { useEffect, useState } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  Check,
  ChevronRight,
  Database,
  Download,
  Leaf,
  LoaderCircle,
  ShieldCheck,
  Sparkles,
  Upload,
} from "lucide-react";
import { api, download, money, percent, shortDate } from "./api";
import {
  Badge,
  Empty,
  MetricStrip,
  Notice,
  Step,
  TextLink,
} from "./components";
import { ImportDialog, StrategyDialog, TaskDialog } from "./dialogs";
import Research from "./Research";
import MarketData from "./MarketData";
import DatasetUpdates from "./DatasetUpdates";
import {
  snapshotGroups,
  snapshotName,
  aliasActionGaps,
  mergerActionGaps,
} from "./snapshots";
import PaperWorkspace, { PaperPerformance, PaperWeekly } from "./Paper";
import {
  FundamentalsPanel,
  FundamentalDetails,
  SignalAudit,
} from "./Fundamentals";
import type { Review, State, Strategy } from "./types";

const tabs = [
  ["/", "Overview"],
  ["/research", "Research"],
  ["/portfolio", "Portfolio"],
  ["/activity", "Activity"],
  ["/data", "Data"],
];

export default function App() {
  const navigate = useNavigate();
  const location = useLocation();
  const client = useQueryClient();
  const [dialog, setDialog] = useState<"import" | "backtest" | "review" | null>(
    null,
  );
  const [strategy, setStrategy] = useState<string>();
  const [info, setInfo] = useState<Strategy | null>(null);
  const [toast, setToast] = useState("");
  const query = useQuery({
    queryKey: ["state"],
    queryFn: () => api<State>("/state"),
    refetchInterval: (q) =>
      q.state.data?.jobs.some(
        (j) => j.state === "queued" || j.state === "running",
      )
        ? 1000
        : 10000,
  });
  const state = query.data;
  const practice = useMutation({
    mutationFn: () => api("/practice", {}),
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ["state"] });
      setToast(
        "Practice dataset queued. You can continue browsing while it is prepared.",
      );
    },
    onError: (error) => setToast(error.message),
  });
  const route = tabs.some(([path]) => path === location.pathname)
    ? location.pathname
    : "/";
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [location.pathname]);
  function start(kind: "review" | "backtest", id?: string) {
    if (!state?.datasets.length) {
      navigate("/data");
      setToast("Add a dataset or create the practice universe to begin.");
      return;
    }
    setStrategy(id);
    setDialog(kind);
  }
  return (
    <div className="app">
      <a
        className="skip-link"
        href="#main"
        onClick={(e) => {
          e.preventDefault();
          document.getElementById("main")?.focus();
        }}
      >
        Skip to content
      </a>
      <header className="topbar">
        <div className="topbar-inner">
          <NavLink to="/" className="brand" aria-label="Aperture home">
            <span className="brand-mark">A</span>
            <span>
              aperture<span className="brand-dot">.</span>
            </span>
          </NavLink>
          <nav aria-label="Main navigation">
            {tabs.map(([path, title]) => (
              <NavLink end={path === "/"} to={path} key={path}>
                {title}
              </NavLink>
            ))}
          </nav>
          <div className="environment">
            <span className="status-dot" />
            Local <span className="environment-divider" />
            <Badge>{state?.account.connected ? "Paper" : "Research"}</Badge>
          </div>
        </div>
      </header>
      <main id="main" tabIndex={-1}>
        {toast && (
          <div className="toast" role="status">
            <span>{toast}</span>
            <button
              onClick={() => setToast("")}
              aria-label="Dismiss notification"
            >
              ×
            </button>
          </div>
        )}
        {!state ? (
          query.isError ? (
            <Notice error>
              Couldn’t reach the local service. Start Aperture and try again.{" "}
              <button className="text-link" onClick={() => query.refetch()}>
                Retry connection
              </button>
            </Notice>
          ) : (
            <div className="loading full" role="status">
              <LoaderCircle size={22} className="spin" />
              Opening your workspace…
            </div>
          )
        ) : (
          <>
            {query.isError && (
              <Notice error>
                The connection was interrupted. Showing the last saved
                workspace; actions may need a retry.
              </Notice>
            )}
            {state.jobs.some(
              (j) => j.state === "running" || j.state === "queued",
            ) && (
              <div className="job-banner" role="status">
                <LoaderCircle className="spin" size={16} />
                <span>
                  Working in the background. Your workspace remains available.
                </span>
                <button
                  className="text-link"
                  onClick={() => navigate("/activity")}
                >
                  View progress <ArrowRight size={14} />
                </button>
              </div>
            )}
            {route === "/" && (
              <Overview
                state={state}
                onPrepare={() => start("review")}
                onResearch={() => navigate("/research")}
                onData={() => navigate("/data")}
                onPortfolio={() => navigate("/portfolio")}
              />
            )}
            {route === "/research" && (
              <Research
                state={state}
                onRun={(id) => start("backtest", id)}
                onInfo={setInfo}
                onData={() => navigate("/data")}
              />
            )}
            {route === "/portfolio" && (
              <Portfolio state={state} onPrepare={() => start("review")} />
            )}
            {route === "/activity" && (
              <ActivityPage
                state={state}
                onResearch={(id) => navigate(`/research?run=${id}`)}
                onReview={(id) => navigate(`/portfolio?review=${id}`)}
                onData={() => navigate("/data")}
              />
            )}
            {route === "/data" && (
              <DataPage
                state={state}
                onImport={() => setDialog("import")}
                onPractice={() => practice.mutate()}
                busy={
                  practice.isPending ||
                  state.jobs.some(
                    (j) =>
                      j.kind === "practice" &&
                      ["queued", "running"].includes(j.state),
                  )
                }
              />
            )}
            {dialog === "import" && (
              <ImportDialog
                onClose={() => setDialog(null)}
                onImported={() =>
                  setToast(
                    "Dataset imported. It is now available in Research. Repeated identical imports do not create duplicates.",
                  )
                }
              />
            )}
            {(dialog === "backtest" || dialog === "review") && (
              <TaskDialog
                key={`${dialog}-${strategy}`}
                kind={dialog}
                state={state}
                initial={strategy}
                onClose={() => setDialog(null)}
                onQueued={() => {
                  setToast(
                    "Task submitted. Activity shows its current status; saved results stay available.",
                  );
                  navigate("/activity");
                }}
              />
            )}
            {info && (
              <StrategyDialog strategy={info} onClose={() => setInfo(null)} />
            )}
          </>
        )}
      </main>
      <footer>
        <span>
          Aperture <span> / </span> A little more clarity, every week.
        </span>
        <span>Local research workspace · v{state?.version ?? "0.1.0"}</span>
      </footer>
    </div>
  );
}

function Overview({
  state,
  onPrepare,
  onResearch,
  onData,
  onPortfolio,
}: {
  state: State;
  onPrepare: () => void;
  onResearch: () => void;
  onData: () => void;
  onPortfolio: () => void;
}) {
  const latest = state.reviews[0];
  return (
    <>
      <div className="hero">
        <div>
          <span className="eyebrow">
            <span className="tiny-line" /> THE WEEKLY VIEW
          </span>
          <h1>
            Your week, in focus<span>.</span>
          </h1>
          <p>A calm place to turn research into considered decisions.</p>
        </div>
        <div className="portfolio-value">
          <span>
            {state.account.connected
              ? "Paper portfolio value"
              : "Planning capital"}{" "}
            <Badge>USD</Badge>
          </span>
          <strong>
            {money(
              state.account.snapshot?.equity ?? state.account.planning_capital,
            )}
          </strong>
          <small>
            {state.account.connected
              ? `Paper · ${state.account.snapshot?.source ?? "Alpaca"} · last synced ${new Date(state.account.snapshot!.checked_at).toLocaleString()}`
              : "Research only · No brokerage account connected"}
          </small>
        </div>
      </div>
      {state.account.connected ? (
        <PaperPerformance />
      ) : (
        <section className="card overview-performance">
          <MetricStrip account />
          <div className="performance-empty">
            <span className="empty-chart-icon">
              <Activity size={25} />
            </span>
            <div>
              <h3>A clear view of performance, when it begins.</h3>
              <p>
                Account returns will appear here after paper trading is
                connected. Explore strategy performance in Research today.
              </p>
            </div>
            <button className="button small secondary" onClick={onResearch}>
              Explore research <ArrowUpRight size={14} />
            </button>
          </div>
        </section>
      )}
      <div className="overview-grid">
        {state.account.connected ? (
          <PaperWeekly onPortfolio={onPortfolio} />
        ) : (
          <section className="weekly-card">
            <div className="weekly-overline">
              <span className="eyebrow">YOUR NEXT STEP</span>
              <Badge tone="light">
                {latest ? "Review prepared" : "Start with a clear plan"}
              </Badge>
            </div>
            <div className="weekly-title">
              <span className="weekly-icon">
                <Leaf size={24} />
              </span>
              <h2>
                {latest
                  ? "Your allocation, ready to explore."
                  : "Make room for a good decision."}
              </h2>
            </div>
            <p>
              {latest
                ? `Your ${latest.strategy.name} review is saved. Inspect the targets, cash allocation and exclusions before taking the next step.`
                : "Bring your data and a research idea together. One preparation task validates the inputs, calculates signals, and builds a target allocation."}
            </p>
            <div className="weekly-steps">
              <span>
                <Check size={13} />
                Validate data
              </span>
              <ChevronRight size={13} />
              <span>Calculate signals</span>
              <ChevronRight size={13} />
              <span>Build targets</span>
            </div>
            <div className="weekly-bottom">
              <button
                className="button light"
                onClick={latest ? onPortfolio : onPrepare}
              >
                {latest ? "View allocation review" : "Prepare weekly review"}
                <ArrowRight size={16} />
              </button>
              <span>Read-only · No orders submitted</span>
            </div>
          </section>
        )}
        <section className="card readiness">
          <div className="card-header">
            <div>
              <span className="eyebrow">A SOLID FOUNDATION</span>
              <h2>Your workspace</h2>
            </div>
            <ShieldCheck size={21} />
          </div>
          <div className="card-body">
            <Step
              complete={state.datasets.length > 0}
              title="Add a research dataset"
              detail={
                state.datasets.length
                  ? `${state.datasets.length} saved · imported or synthetic`
                  : "Import prices or explore the practice universe"
              }
            />
            <Step
              complete={state.runs.length > 0}
              title="Test an existing strategy"
              detail={
                state.runs.length
                  ? `${state.runs.length} reproducible experiments saved`
                  : "Five strategies, with clear input requirements"
              }
            />
            <Step
              complete={state.reviews.length > 0}
              title="Review a target allocation"
              detail="A plan is separate from permission to trade"
            />
            <TextLink onClick={onData}>Manage your data</TextLink>
          </div>
        </section>
      </div>
      <div className="section-heading">
        <div>
          <span className="eyebrow">ROOM TO EXPLORE</span>
          <h2>Build conviction, one idea at a time.</h2>
        </div>
        <TextLink onClick={onResearch}>Open research</TextLink>
      </div>
      <div className="explore-grid">
        <button className="card explore-card" onClick={onResearch}>
          <span className="soft-icon">
            <BookOpen size={22} />
          </span>
          <h3>Understand the strategy.</h3>
          <p>
            Five research families. Clear inputs, honest limitations, and no
            unexplained black boxes.
          </p>
          <span className="text-link">
            Strategy library <ArrowRight size={15} />
          </span>
        </button>
        <button className="card explore-card" onClick={onResearch}>
          <span className="soft-icon">
            <Sparkles size={22} />
          </span>
          <h3>Test the evidence.</h3>
          <p>
            Compare saved backtests with SPY, modeled costs and the same
            portfolio constraints.
          </p>
          <span className="text-link">
            Your experiments <ArrowRight size={15} />
          </span>
        </button>
        <div className="card explore-card muted-card">
          <span className="soft-icon">
            <ShieldCheck size={22} />
          </span>
          <h3>Move forward deliberately.</h3>
          <p>
            Paper trading includes strategy-version approval, manual or
            automatic rebalancing, order reconciliation and cash safeguards.
          </p>
          <button className="text-link" onClick={onPortfolio}>
            Open paper workspace <ArrowRight size={15} />
          </button>
        </div>
      </div>
    </>
  );
}

function DataPage({
  state,
  onImport,
  onPractice,
  busy,
}: {
  state: State;
  onImport: () => void;
  onPractice: () => void;
  busy: boolean;
}) {
  const [showOlder, setShowOlder] = useState(false);
  const snapshots = snapshotGroups(state.datasets);
  const visible = showOlder
    ? [...snapshots.latest, ...snapshots.older]
    : snapshots.latest;
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">THE INPUTS MATTER</span>
          <h1>Good research starts here.</h1>
          <p>Know where your data comes from, and what it can support.</p>
        </div>
        <button className="button" onClick={onImport}>
          <Upload size={16} />
          Import CSV
        </button>
      </div>
      <MarketData />
      <DatasetUpdates datasets={state.datasets} />
      <FundamentalsPanel datasets={state.datasets} />
      <div className="data-start card">
        <span className="soft-icon">
          <Database size={23} />
        </span>
        <div>
          <h2>Try the workflow before adding market data.</h2>
          <p>
            The practice universe has 32 fictional stocks and a synthetic SPY
            series. Use it to learn the app, with no API keys or account
            required.
          </p>
        </div>
        <button
          className="button secondary"
          onClick={onPractice}
          disabled={busy}
        >
          {busy ? (
            <LoaderCircle size={16} className="spin" />
          ) : (
            <Sparkles size={16} />
          )}
          {busy ? "Preparing…" : "Create practice data"}
        </button>
      </div>
      <div className="section-heading">
        <div>
          <h2>Your latest snapshots</h2>
          <p>
            Market data and SEC filings together. Older snapshots remain
            available to reproduce saved research.
          </p>
        </div>
        <Badge>{snapshots.latest.length} latest</Badge>
      </div>
      {!state.datasets.length ? (
        <div className="card">
          <Empty
            title="A fresh start, with clear inputs"
            action={
              <button className="button secondary" onClick={onImport}>
                Import your first dataset <ArrowRight size={15} />
              </button>
            }
          >
            Nothing has been imported. Download the S&P 500 with enough warm-up
            history, or create practice data above.
          </Empty>
        </div>
      ) : (
        <div className="dataset-list">
          {visible.map((dataset) => (
            <article className="card dataset-card" key={dataset.id}>
              <div className="card-header">
                <div>
                  <div className="inline">
                    <h2>{snapshotName(dataset)}</h2>
                    {snapshots.older.some((old) => old.id === dataset.id) && (
                      <Badge>Older snapshot</Badge>
                    )}
                    <Badge
                      tone={dataset.kind === "synthetic" ? "amber" : "green"}
                    >
                      {dataset.kind === "synthetic"
                        ? "Synthetic practice"
                        : dataset.metadata?.provider === "alpaca"
                          ? "Downloaded · Alpaca SIP"
                          : "Imported · as-traded declared"}
                    </Badge>
                  </div>
                  <p>
                    {dataset.symbol_count} symbols ·{" "}
                    {dataset.row_count.toLocaleString()} rows ·{" "}
                    {shortDate(dataset.start)} – {shortDate(dataset.end)}
                  </p>
                </div>
                <button
                  className="icon-button"
                  aria-label={`Export ${dataset.name} metadata`}
                  onClick={() =>
                    window.location.assign(
                      `/api/datasets/${dataset.id}/metadata`,
                    )
                  }
                >
                  <Download size={18} />
                </button>
              </div>
              <div className="card-body">
                <p className="data-source">
                  <strong>Source</strong> {dataset.source}
                </p>
                {!!Object.keys(dataset.metadata?.unavailable_symbols ?? {})
                  .length && (
                  <Notice>
                    {
                      Object.keys(dataset.metadata?.unavailable_symbols ?? {})
                        .length
                    }{" "}
                    securities have dated input limitations, including
                    historical payment dates. Total-return and cash-flow modes
                    have different requirements. Coverage-limited research
                    records every exclusion; strict full-index calculations
                    require complete inputs. See coverage below for reasons.
                  </Notice>
                )}
                {!!aliasActionGaps(dataset).length && (
                  <Notice>
                    Historical ticker transitions still need corporate-action
                    reconciliation: {aliasActionGaps(dataset).join(", ")}. Their
                    affected periods are excluded in coverage-limited research.
                  </Notice>
                )}
                {!!mergerActionGaps(dataset).length && (
                  <Notice>
                    Merger consideration still needs verified recipient, ratio
                    or valuation terms: {mergerActionGaps(dataset).join(", ")}.
                    These affected dates cannot be simulated at an assumed zero
                    recovery.
                  </Notice>
                )}
                {dataset.metadata?.validation_issues?.map((reason) => (
                  <Notice error key={reason}>
                    {reason}
                  </Notice>
                ))}
                {dataset.metadata?.fundamentals && (
                  <FundamentalDetails data={dataset.metadata.fundamentals} />
                )}
                <details className="details">
                  <summary>Coverage, symbols & limitations</summary>
                  <p>{dataset.symbols.join(" · ")}</p>
                  {dataset.metadata?.coverage && (
                    <div className="table-scroll">
                      <table>
                        <thead>
                          <tr>
                            <th>Stock</th>
                            <th>Bars</th>
                            <th>Missing sessions</th>
                            <th>Coverage</th>
                          </tr>
                        </thead>
                        <tbody>
                          {dataset.metadata.coverage.map((row) => (
                            <tr key={row.symbol}>
                              <td>{row.symbol}</td>
                              <td>
                                {row.rows} / {row.expected}
                              </td>
                              <td>{row.missing_count}</td>
                              <td>
                                {row.rows
                                  ? `${row.start} – ${row.end}`
                                  : "No prices returned"}
                                {row.reason && <small>{row.reason}</small>}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                  {dataset.warnings.map((w) => (
                    <p key={w}>{w}</p>
                  ))}
                  <p className="digest">Source fingerprint: {dataset.digest}</p>
                </details>
              </div>
            </article>
          ))}
        </div>
      )}
      {!!snapshots.older.length && (
        <button
          className="button secondary snapshot-archive-toggle"
          onClick={() => setShowOlder(!showOlder)}
          aria-expanded={showOlder}
        >
          {showOlder
            ? "Hide older snapshots"
            : `Show older snapshots (${snapshots.older.length})`}
        </button>
      )}
      <div className="two-columns">
        <div className="card education">
          <h3>Which stocks should I start with?</h3>
          <p>
            Start with the full S&P 500. Additional symbols supplement the
            index; SPY is reserved for comparisons. One download includes
            current and recorded historical members; backtests apply dated
            membership automatically within supported coverage. Public
            historical rosters and delisted-security coverage still need
            independent verification.
          </p>
        </div>
        <div className="card education">
          <h3>What about automatic downloads?</h3>
          <p>
            Weekly paper preparation refreshes S&P membership, backfills new
            members and updates prices and required SEC filings. Ordinary weekly
            use needs no separate Data download. Membership changes pause for
            your review and new approval. Keep Aperture open through preparation
            and confirmed order acceptance; Alpaca then holds the orders while
            your Mac is off.
          </p>
        </div>
      </div>
    </>
  );
}

function Portfolio({
  state,
  onPrepare,
}: {
  state: State;
  onPrepare: () => void;
}) {
  const location = useLocation();
  const [tab, setTab] = useState(
    new URLSearchParams(location.search).has("review") ? "research" : "paper",
  );
  return (
    <>
      <div className="subnav" role="tablist" aria-label="Portfolio sections">
        <button
          role="tab"
          aria-selected={tab === "paper"}
          onClick={() => setTab("paper")}
        >
          Paper portfolio
        </button>
        <button
          role="tab"
          aria-selected={tab === "research"}
          onClick={() => setTab("research")}
        >
          Research allocations
        </button>
      </div>
      {tab === "paper" ? (
        <PaperWorkspace state={state} />
      ) : (
        <ResearchAllocations state={state} onPrepare={onPrepare} />
      )}
    </>
  );
}

function ResearchAllocations({
  state,
  onPrepare,
}: {
  state: State;
  onPrepare: () => void;
}) {
  const location = useLocation();
  const [selected, setSelected] = useState(
    new URLSearchParams(location.search).get("review") ?? "",
  );
  const id = selected || state.reviews[0]?.id;
  const review = useQuery({
    queryKey: ["review", id],
    queryFn: () => api<Review>(`/results/${id}`),
    enabled: !!id,
  });
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">FROM IDEAS TO ALLOCATIONS</span>
          <h1>A considered portfolio.</h1>
          <p>
            Explore target allocations before a strategy is approved to trade.
          </p>
        </div>
        <button className="button" onClick={onPrepare}>
          Prepare weekly review <ArrowRight size={16} />
        </button>
      </div>
      <div className="card portfolio-summary">
        <div>
          <span className="eyebrow">PLANNING CAPITAL</span>
          <strong>{money(state.account.planning_capital)}</strong>
        </div>
        <div>
          <Badge>Research only</Badge>
          <p>
            Research targets use planning capital. Actual account holdings and
            orders appear in Paper portfolio.
          </p>
        </div>
      </div>
      {!id ? (
        <div className="card">
          <Empty
            title="Your first allocation is ahead"
            action={
              <button className="button secondary" onClick={onPrepare}>
                Prepare a review <ArrowRight size={15} />
              </button>
            }
          >
            Use current saved data and an existing strategy to see an allocation
            under the default risk policy.
          </Empty>
        </div>
      ) : (
        <>
          <label className="review-select">
            Saved allocation review
            <select value={id} onChange={(e) => setSelected(e.target.value)}>
              {state.reviews.map((r, i) => (
                <option key={r.id} value={r.id}>
                  {r.strategy.name} · {r.decision_session} · Review{" "}
                  {state.reviews.length - i}
                </option>
              ))}
            </select>
          </label>
          {review.isPending ? (
            <div className="card loading">Loading review…</div>
          ) : review.error ? (
            <Notice error>{review.error.message}</Notice>
          ) : (
            review.data && <ReviewDetail review={review.data} />
          )}
        </>
      )}
      <Notice>
        These are read-only research allocations. Use Paper portfolio for
        account reconciliation, explicit approvals and actual paper orders.
        Preparing a research review grants no trading approval.
      </Notice>
    </>
  );
}

function ReviewDetail({ review }: { review: Review }) {
  return (
    <section className="card">
      <div className="card-header">
        <div>
          <span className="eyebrow">READ-ONLY ALLOCATION REVIEW</span>
          <h2>{review.strategy.name}</h2>
          <p>
            Signals as of {shortDate(review.decision_session)} · Intended
            following session: {shortDate(review.execute_session)}
          </p>
        </div>
        <button
          className="button secondary small"
          onClick={() => download(`aperture-review-${review.id}.json`, review)}
        >
          <Download size={15} />
          Export
        </button>
      </div>
      <div className="card-body">
        {review.dataset_kind === "synthetic" && (
          <Notice>
            Synthetic practice allocation. The symbols and their returns are
            fictional.
          </Notice>
        )}
        <div className="review-stats">
          <div>
            <strong>{review.targets.length}</strong>
            <span>Target stocks</span>
          </div>
          <div>
            <strong>{percent(Number(review.cash_weight))}</strong>
            <span>Target cash</span>
          </div>
          <div>
            <strong>{review.eligible}</strong>
            <span>Eligible stocks</span>
          </div>
        </div>
        {review.notes.map((note) => (
          <p key={note} className="field-hint">
            {note}
          </p>
        ))}
      </div>
      {review.targets.length > 0 && (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Stock</th>
                <th>Sector</th>
                <th>Target weight</th>
                <th>Indicative allocation</th>
              </tr>
            </thead>
            <tbody>
              {review.targets.map((t) => (
                <tr key={t.symbol}>
                  <td>
                    <strong>{t.symbol}</strong>
                  </td>
                  <td>{t.sector}</td>
                  <td>{percent(Number(t.weight))}</td>
                  <td>{money(Number(t.weight) * Number(review.capital))}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="card-body">
        <p className="field-hint">
          Dollar values use planning capital and are illustrative allocations,
          not order sizes. Actual orders require current account state, prices
          and cash checks.
        </p>
        <SignalAudit
          fundamental={["quality", "quality_value", "value_momentum"].includes(
            review.strategy.id,
          )}
          decisions={[
            {
              session: review.decision_session,
              execute_session: review.execute_session,
              eligible: review.eligible,
              signals: review.signals || [],
              exclusions: review.excluded,
            },
          ]}
        />
        <details className="details">
          <summary>Excluded stocks ({review.excluded.length})</summary>
          {review.excluded.length ? (
            review.excluded.map((stock) => (
              <p key={stock.symbol}>
                <strong>{stock.symbol}</strong> — {stock.reason}
              </p>
            ))
          ) : (
            <p>
              Every stock in this dataset has the required input history and
              qualifies under this signal.
            </p>
          )}
        </details>
      </div>
    </section>
  );
}

function ActivityPage({
  state,
  onResearch,
  onReview,
  onData,
}: {
  state: State;
  onResearch: (id: string) => void;
  onReview: (id: string) => void;
  onData: () => void;
}) {
  const navigate = useNavigate();
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">NOTHING LOST BETWEEN VISITS</span>
          <h1>Your work, kept in view.</h1>
          <p>
            Background tasks save their progress and completed results locally.
          </p>
        </div>
        <Badge>{state.jobs.length} recent tasks</Badge>
      </div>
      <div className="card">
        {!state.jobs.length ? (
          <Empty
            title="A quiet workspace"
            action={
              <button
                className="button secondary"
                onClick={() => onResearch("")}
              >
                Explore strategies <ArrowRight size={15} />
              </button>
            }
          >
            Data preparation, backtests and allocation reviews will appear here
            when you run them.
          </Empty>
        ) : (
          <div className="activity-list">
            {state.jobs.map((job) => (
              <article className="activity-item" key={job.id}>
                <span className={`activity-icon ${job.state}`}>
                  {job.state === "running" || job.state === "queued" ? (
                    <LoaderCircle className="spin" size={19} />
                  ) : job.state === "complete" ? (
                    <Check size={19} />
                  ) : (
                    <Activity size={19} />
                  )}
                </span>
                <div className="activity-content">
                  <div className="inline">
                    <h3>
                      {{
                        practice: "Prepare practice data",
                        download: "Download research data",
                        dataset_update: "Update saved dataset",
                        connection: "Check paper/data access",
                        membership: "Refresh S&P 500 membership",
                        fundamentals: "Complete SEC download",
                        backtest: "Run backtest",
                        review: "Prepare allocation review",
                        validation: "Evaluate frozen research protocol",
                        paper_sync: "Reconcile paper account",
                        paper_prepare: "Prepare weekly paper review",
                        paper_cancel: "Cancel Aperture paper orders",
                      }[job.kind] ?? job.kind}
                    </h3>
                    <Badge
                      tone={
                        job.state === "failed"
                          ? "amber"
                          : job.state === "complete"
                            ? "green"
                            : ""
                      }
                    >
                      {job.state === "complete"
                        ? "Complete"
                        : job.state === "failed"
                          ? "Needs attention"
                          : job.state === "queued"
                            ? "Queued"
                            : "In progress"}
                    </Badge>
                  </div>
                  <p>{job.message}</p>
                  <small>{new Date(job.created_at).toLocaleString()}</small>
                  {job.state === "running" && (
                    <progress
                      value={job.progress}
                      max="100"
                      aria-label="Task progress"
                    />
                  )}
                  {job.state === "queued" && (
                    <p className="field-hint">
                      If this stays queued, make sure Aperture’s local worker is
                      running.
                    </p>
                  )}
                </div>
                {job.state === "complete" && job.kind !== "practice" && (
                  <button
                    className="button small secondary"
                    onClick={() =>
                      job.kind.startsWith("paper_")
                        ? navigate("/portfolio")
                        : job.kind === "validation"
                          ? navigate("/research?section=validation")
                          : job.kind === "backtest"
                            ? onResearch(job.result_id ?? "")
                            : job.kind === "review"
                              ? onReview(job.result_id ?? "")
                              : onData()
                    }
                  >
                    Open{" "}
                    {job.kind.startsWith("paper_")
                      ? "paper portfolio"
                      : job.kind === "validation"
                        ? "validation"
                        : job.kind === "backtest"
                          ? "research"
                          : job.kind === "review"
                            ? "review"
                            : "data"}
                    <ArrowRight size={14} />
                  </button>
                )}
              </article>
            ))}
          </div>
        )}
      </div>
      <p className="page-note">
        Tasks run while Aperture is open. If the worker stops midway, the task
        is marked for attention on restart and can be run again. Completed
        results are preserved.
      </p>
    </>
  );
}
