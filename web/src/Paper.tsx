import { lazy, Suspense, useEffect, useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Download, RefreshCw, ShieldCheck } from "lucide-react";
import { api, download, money, percent, shortDate } from "./api";
import { Badge, Empty, MetricStrip, Notice, PeriodPicker } from "./components";
import { SignalAudit } from "./Fundamentals";
import type { Decision, Period, Run, State } from "./types";
const Chart = lazy(() => import("./Chart"));
export type PaperSnapshot = {
  account_key: string;
  source?: string;
  checked_at: string;
  cash: string;
  equity: string;
  spendable_cash: string;
  buying_power?: string;
  margin_debit?: string;
  unsettled_sales: string;
  issues: string[];
  positions: {
    symbol: string;
    qty: string;
    market_value: string;
    current_price: string;
    unrealized_pl: string;
  }[];
  open_orders: {
    id: string;
    symbol: string;
    side: string;
    status: string;
    qty?: string | null;
    notional?: string | null;
    filled_qty: string;
    client_order_id: string;
  }[];
};
type Config = {
  hash: string;
  strategy_id: string;
  strategy_version: string;
  mode: "manual" | "automatic";
  paused: boolean;
  symbols: string[];
  data_start: string;
  max_drift: string;
  policy: Record<string, string>;
  execution_version?: string;
  universe?: "sp500" | "custom";
  supplements?: string[];
  exit_symbols?: string[];
  funding_policy?: "cash_only" | "paper_margin";
};
type Plan = {
  id: string;
  state: string;
  message: string;
  created_at: string;
  dataset_name: string;
  source_digest: string;
  decision_session: string;
  execute_session: string;
  last_execution_session: string;
  strategy: { id: string; name: string; version: string };
  cash_weight: string;
  account: PaperSnapshot;
  targets: { symbol: string; weight: string; sector: string }[];
  changes: {
    symbol: string;
    side: string;
    quantity: string;
    max_notional: string;
    before_weight: string;
    target_weight: string;
    sector: string;
    reference_price: string;
    reason: string;
  }[];
  notes: string[];
  signals: Decision["signals"];
  excluded: { symbol: string; reason: string }[];
  config?: Config;
  staged_orders?: {
    symbol: string;
    side: string;
    notional?: string;
    qty?: string;
  }[];
  deferred_buys?: { symbol: string; amount: string; reason: string }[];
  funding?: {
    reference_cash_after: string;
    debit_if_buys_fill_first: string;
    buy_budget: string;
  };
};
type Order = {
  client_id: string;
  plan_id: string;
  symbol: string;
  side: string;
  state: string;
  updated_at: string;
  request: {
    qty?: string;
    notional?: string;
    limit_price?: string;
    type?: string;
  };
  broker?: {
    id?: string;
    filled_qty?: string;
    filled_avg_price?: string;
    reason?: string;
  } | null;
};
type Performance = {
  available: boolean;
  curve: Run["curve"];
  windows: Run["windows"];
  start?: string;
  end?: string;
  notes: string[];
  benchmark_model?: string;
  checked_at?: string;
};
type PaperState = {
  config?: Config | null;
  snapshot?: PaperSnapshot | null;
  approval?: {
    id: string;
    created_at: string;
    allow_automatic: boolean;
    rationale: string;
  } | null;
  plans: Plan[];
  orders: Order[];
  events: { id: number; created_at: string; message: string }[];
  performance?: Performance | null;
  last_error?: string | null;
  worker_seen?: string | null;
  automatic_status: string;
  fill_check?: {
    status: string;
    checked_at: string | null;
    counts: Record<string, number>;
    issues: string[];
  } | null;
  membership_update?: {
    added: string[];
    removed: string[];
    backfill_dataset_id: string | null;
  } | null;
  quote_waits?: { plan_id: string; reasons: string[] } | null;
};
export function usePaper() {
  const query = useQuery({
    queryKey: ["paper"],
    queryFn: () => api<PaperState>("/paper"),
    refetchInterval: 2500,
  });
  const checked = query.data?.fill_check?.checked_at;
  const launchCheck = useQuery({
    queryKey: ["paper-launch-fill-check"],
    queryFn: () => api("/paper/actions/sync", {}),
    enabled:
      !!query.data?.orders.some((o) => o.state !== "planned") &&
      (!checked || Date.now() - new Date(checked).getTime() >= 60000),
    staleTime: Infinity,
    retry: false,
  });
  return { ...query, launchError: launchCheck.error };
}
function useAction() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ path, body = {} }: { path: string; body?: unknown }) =>
      api(`/paper${path}`, body),
    onSuccess: async () => {
      await Promise.all([
        client.invalidateQueries({ queryKey: ["paper"] }),
        client.invalidateQueries({ queryKey: ["state"] }),
      ]);
    },
  });
}

export function PaperPerformance() {
  const q = usePaper();
  const perf = q.data?.performance;
  const [period, setPeriod] = useState<Period>("All");
  const window = perf?.windows?.[period];
  const chartData =
    perf && window
      ? {
          curve: perf.curve,
          windows: perf.windows,
          strategy: { name: "Paper account" },
        }
      : null;
  return (
    <section className="card overview-performance">
      <div className="card-header">
        <div>
          <span className="eyebrow">PAPER ACCOUNT PERFORMANCE</span>
          <h2>Your actual paper history.</h2>
          <p>
            {window
              ? `${shortDate(window.start)} – ${shortDate(window.end)}`
              : "Completed daily sessions appear after account refresh."}
          </p>
        </div>
        <Badge>Broker valuations</Badge>
      </div>
      <MetricStrip account metrics={window?.metrics} />
      <p className="chart-notice">
        Alpaca paper does not credit dividends. SPY includes them; the gap
        includes this simulator difference.
      </p>
      {perf?.available && chartData && window ? (
        <>
          <div className="chart-toolbar">
            <span>Daily flow-adjusted estimate · regular-session history</span>
            <PeriodPicker value={period} onChange={setPeriod} />
          </div>
          {window.limited && (
            <p className="chart-notice">
              Showing available history: {window.start} – {window.end}.
            </p>
          )}
          <Suspense fallback={<p>Loading chart…</p>}>
            <Chart run={chartData} period={period} label="Paper account" />
          </Suspense>
        </>
      ) : (
        <div className="card-body">
          <p>
            No complete return history yet. Refresh the paper account after
            funded market sessions; no history is fabricated.
          </p>
        </div>
      )}
      {perf && (
        <details className="details paper-performance-notes">
          <summary>Sources, cash flows & comparison</summary>
          {perf.notes.map((n) => (
            <p key={n}>{n}</p>
          ))}
          <p>{perf.benchmark_model}</p>
          <p>
            Deposits/withdrawals are removed using an end-of-day convention.
            Intraday flows make this an estimate. SPY must cover every displayed
            session; missing comparison data is never filled forward. The
            requested history is the latest year supplied by the broker.
          </p>
          <button
            className="button small secondary"
            onClick={() => download("aperture-paper-performance.json", perf)}
          >
            Export account history
          </button>
        </details>
      )}
    </section>
  );
}

export function PaperWeekly({ onPortfolio }: { onPortfolio: () => void }) {
  const q = usePaper();
  const act = useAction();
  const data = q.data;
  const cfg = data?.config;
  const latest = data?.plans?.[0];
  const reviewExisting = data?.plans.some(
    (p) =>
      !["complete", "blocked", "stopped", "expired", "superseded"].includes(
        p.state,
      ),
  );
  return (
    <section className="weekly-card">
      <div className="weekly-overline">
        <span className="eyebrow">YOUR PAPER WEEK</span>
        <Badge tone="light">
          {cfg?.paused ? "Paused" : (cfg?.mode ?? "Set up")}
        </Badge>
      </div>
      <h2>Prepare once. Review with context.</h2>
      <p>
        Reconcile the account, update prices and filings, validate inputs and
        save an allocation with proposed paper orders.
      </p>
      <div className="weekly-steps">
        <span>Reconcile</span>
        <ArrowRight size={13} />
        <span>Update & calculate</span>
        <ArrowRight size={13} />
        <span>Review</span>
      </div>
      {latest && (
        <p>
          Latest plan: {latest.state.replaceAll("_", " ")} · {latest.message}
        </p>
      )}
      <div className="weekly-bottom">
        <button
          className="button light"
          disabled={act.isPending}
          onClick={() =>
            cfg && !reviewExisting
              ? act.mutate({ path: "/actions/prepare" })
              : onPortfolio()
          }
        >
          {reviewExisting
            ? "Review current paper plan"
            : cfg
              ? "Prepare weekly paper review"
              : "Set up paper trading"}
          <ArrowRight size={16} />
        </button>
        <button className="text-link" onClick={onPortfolio}>
          Open Portfolio
        </button>
      </div>
      {act.error && <Notice error>{act.error.message}</Notice>}
      {act.isSuccess && (
        <p role="status">
          Preparation queued. Open Portfolio for the saved review; no orders
          submitted by preparation.
        </p>
      )}
    </section>
  );
}

export default function PaperWorkspace({ state }: { state: State }) {
  const query = usePaper();
  const action = useAction();
  const data = query.data;
  const cfg = data?.config;
  const snap = data?.snapshot;
  const providers = useQuery({
    queryKey: ["providers"],
    queryFn: () =>
      api<{
        watchlist: { symbols: string[]; start: string };
        paper_default_symbols?: string[];
      }>("/providers"),
  });
  const [editing, setEditing] = useState(false);
  const [universe, setUniverse] = useState<"sp500" | "sp500_plus" | "custom">(
    "sp500",
  );
  useEffect(() => {
    setUniverse(
      cfg
        ? cfg.universe === "sp500"
          ? cfg.supplements?.length
            ? "sp500_plus"
            : "sp500"
          : "custom"
        : "sp500",
    );
  }, [cfg?.hash]);
  const [selected, setSelected] = useState("");
  const [ack, setAck] = useState(false);
  const p = data?.plans?.find((p) => p.id === selected) ?? data?.plans?.[0];
  const latest = data?.plans?.[0];
  const unfinished = data?.orders.filter(
    (o) =>
      o.plan_id === latest?.id &&
      ["canceled", "expired", "rejected", "replaced"].includes(o.state),
  );
  const canReviewRemaining =
    !!unfinished?.length &&
    !!latest &&
    ["blocked", "stopped", "expired", "complete"].includes(latest.state) &&
    data?.orders.every((o) =>
      ["filled", "canceled", "expired", "rejected", "replaced"].includes(
        o.state,
      ),
    );
  const references = new Map(
    data?.plans.flatMap((plan) =>
      plan.changes.map(
        (change) =>
          [
            `${plan.id}:${change.symbol}:${change.side}`,
            Number(change.reference_price),
          ] as const,
      ),
    ),
  );
  useEffect(() => {
    setAck(false);
  }, [p?.id, p?.state]);
  const workerFresh =
    !!data?.worker_seen &&
    Date.now() - new Date(data.worker_seen).getTime() < 20000;
  if (query.isPending)
    return (
      <div className="card loading" role="status">
        Loading paper workspace…
      </div>
    );
  function save(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    action.mutate({
      path: "/config",
      body: {
        strategy_id: f.get("strategy_id"),
        mode: f.get("mode"),
        execution: "broker_market",
        funding_policy: "paper_margin",
        universe: universe === "custom" ? "custom" : "sp500",
        symbols: (universe === "sp500" ? "" : String(f.get("symbols")))
          .split(/[\s,]+/)
          .filter(Boolean),
        data_start: f.get("data_start"),
        positions: Number(f.get("positions")),
        max_weight: String(Number(f.get("max_weight")) / 100),
        sector_cap: String(Number(f.get("sector_cap")) / 100),
        cash_reserve: String(Number(f.get("cash_reserve")) / 100),
        max_drift: cfg?.max_drift ?? "0.03",
      },
    });
  }
  return (
    <div className="paper-workspace">
      <div className="page-heading">
        <div>
          <span className="eyebrow">RESEARCH INTO PRACTICE</span>
          <h1>A considered paper portfolio.</h1>
          <p>
            Explicit approval, visible cash and a durable record of every order.
          </p>
        </div>
        <button
          className="button secondary"
          disabled={action.isPending}
          onClick={() => action.mutate({ path: "/actions/sync" })}
        >
          <RefreshCw size={16} />
          Refresh paper account
        </button>
      </div>
      <Notice>
        Paper environment only. No live-trading endpoint is available. Your
        intended starting balance is $100,000; account refresh shows the
        broker’s actual balance and never resets it.
      </Notice>
      {query.error && <Notice error>{query.error.message}</Notice>}
      {query.launchError && (
        <Notice error>
          Automatic broker fill check could not be queued:{" "}
          {query.launchError.message}. Refresh the paper account before
          preparing another rebalance.
        </Notice>
      )}
      {action.error && <Notice error>{action.error.message}</Notice>}
      {action.isSuccess && (
        <Notice>
          {action.variables?.path.endsWith("/approve") && p?.staged_orders
            ? "Alpaca acceptance confirmed. You may close Aperture; accepted orders remain active. Check actual fills next time you open the platform."
            : "Action saved or queued. Check the current status below and task progress in Activity."}
        </Notice>
      )}
      {data?.last_error && <Notice error>{data.last_error}</Notice>}
      {data?.fill_check && (
        <Notice error={data.fill_check.status === "attention"}>
          <strong>Broker fill check: {data.fill_check.status}</strong>{" "}
          {data.fill_check.checked_at
            ? `Checked ${new Date(data.fill_check.checked_at).toLocaleString()}. `
            : "Checking is required before another rebalance. "}
          {Object.entries(data.fill_check.counts)
            .map(([status, count]) => `${count} ${status}`)
            .join(" · ")}
          {data.fill_check.issues.join(" ")}
        </Notice>
      )}
      {data?.membership_update && (
        <Notice>
          <strong>S&P 500 membership changed.</strong> Added:{" "}
          {data.membership_update.added.join(", ") || "none"}. Removed:{" "}
          {data.membership_update.removed.join(", ") || "none"}.{" "}
          {data.membership_update.backfill_dataset_id
            ? "New-member history was captured in Data. "
            : "Inspect the backfill task in Activity. "}
          Trading settings stay frozen until you adopt the roster and obtain new
          matching approval.
          <button
            className="button secondary"
            disabled={
              action.isPending ||
              (!!data.membership_update.added.length &&
                !data.membership_update.backfill_dataset_id)
            }
            onClick={() => action.mutate({ path: "/membership/apply" })}
          >
            Use updated roster in settings
          </button>
        </Notice>
      )}
      {!!unfinished?.length && (
        <Notice>
          Some orders finished without filling completely. Confirmed fills are
          retained. Reconcile any open or uncertain orders first, then prepare a
          fresh next-session review using current prices and remaining holdings.
          Nothing is resent automatically.
          <button
            className="button secondary"
            disabled={
              !canReviewRemaining ||
              action.isPending ||
              data?.fill_check?.status === "checking"
            }
            onClick={() => action.mutate({ path: "/actions/prepare" })}
          >
            Review remaining trades
          </button>
        </Notice>
      )}
      <div className="paper-status">
        <Badge tone={workerFresh ? "green" : "amber"}>
          {workerFresh ? "Worker online" : "Worker unavailable or delayed"}
        </Badge>
        <span>
          {cfg?.paused
            ? "Execution paused"
            : cfg
              ? `${cfg.mode} mode`
              : "Paper setup needed"}
        </span>
        <span>
          {data?.approval
            ? "Strategy approved for paper"
            : "Strategy approval needed"}
        </span>
      </div>
      {snap ? (
        <>
          <div className="card portfolio-summary">
            <div>
              <span className="eyebrow">PAPER ACCOUNT VALUE</span>
              <strong>{money(snap.equity)}</strong>
            </div>
            <div>
              <Badge>USD · Paper</Badge>
              <p>{snap.source ?? "Alpaca paper broker"}</p>
              <p>
                Last checked {new Date(snap.checked_at).toLocaleString()}.
                Startup checks owned orders automatically. Refresh to reconcile
                subsequent broker changes.
              </p>
            </div>
          </div>
          <div className="paper-cash-grid">
            <div className="card education">
              <h3>Account cash</h3>
              <strong>{money(snap.cash)}</strong>
              <p>
                {cfg?.funding_policy === "paper_margin"
                  ? "Negative cash is a simulated margin debit, even if sales were intended to cover it."
                  : "Margin buying power is ignored by this saved cash-funded policy."}
              </p>
            </div>
            <div className="card education">
              <h3>
                {cfg?.funding_policy === "paper_margin"
                  ? "Paper buying power"
                  : "Conservative spendable cash"}
              </h3>
              <strong>
                {money(
                  cfg?.funding_policy === "paper_margin"
                    ? (snap.buying_power ?? "0")
                    : snap.spendable_cash,
                )}
              </strong>
              <p>
                {cfg?.funding_policy === "paper_margin"
                  ? "Broker-reported regular buying power; orders remain subject to Alpaca checks."
                  : "Before the policy cash reserve and order-level checks."}
              </p>
            </div>
            <div className="card education">
              <h3>Unsettled sale proceeds</h3>
              <strong>{money(snap.unsettled_sales)}</strong>
              <p>
                {cfg?.funding_policy === "paper_margin"
                  ? "Shown separately; paper margin can bridge funding before sales settle."
                  : "Reserved until the next exchange session."}
              </p>
            </div>
          </div>
          {snap.issues.map((n) => (
            <Notice error key={n}>
              {n}
            </Notice>
          ))}
        </>
      ) : (
        <div className="card">
          <Empty
            title="Connect your paper workspace"
            action={
              <button
                className="button"
                onClick={() => action.mutate({ path: "/actions/sync" })}
              >
                Check configured paper account
              </button>
            }
          >
            Your private paper keys are read locally. Begin with a read-only
            refresh, then choose a strategy and review its risk policy.
          </Empty>
        </div>
      )}
      <section className="card">
        <div className="card-header">
          <div>
            <h2>Strategy & operating policy</h2>
            <p>
              Changes require a new matching paper approval. Use a dedicated
              long-only stock account.
            </p>
          </div>
          {cfg && (
            <button
              className="button small secondary"
              onClick={() => setEditing(!editing)}
            >
              {editing ? "Close settings" : "Edit settings"}
            </button>
          )}
        </div>
        <div className="card-body">
          {!cfg || editing ? (
            <form className="form" onSubmit={save} key={cfg?.hash ?? "new"}>
              <label>
                Paper strategy
                <select
                  name="strategy_id"
                  defaultValue={cfg?.strategy_id ?? "momentum"}
                >
                  {state.strategies.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name} · v{s.version}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Rebalance mode
                <select name="mode" defaultValue={cfg?.mode ?? "manual"}>
                  <option value="manual">
                    Manual — approve each prepared rebalance
                  </option>
                  <option value="automatic">
                    Automatic — prepare and stage while Aperture is open
                  </option>
                </select>
              </label>
              <label>
                Stock universe
                <select
                  value={universe}
                  onChange={(e) =>
                    setUniverse(
                      e.target.value as "sp500" | "sp500_plus" | "custom",
                    )
                  }
                >
                  <option value="sp500">S&P 500 only</option>
                  <option value="sp500_plus">S&P 500 + custom list</option>
                  <option value="custom">Custom list only</option>
                </select>
              </label>
              {universe !== "sp500" && (
                <label>
                  {universe === "sp500_plus"
                    ? "Additional stock symbols"
                    : "US stock universe"}
                  <textarea
                    name="symbols"
                    key={universe}
                    required
                    defaultValue={(universe === "sp500_plus"
                      ? (cfg?.supplements ?? [])
                      : (cfg?.symbols ??
                        providers.data?.paper_default_symbols ??
                        providers.data?.watchlist.symbols ??
                        [])
                    ).join(" ")}
                    placeholder="AAPL MSFT … SPY"
                  />
                </label>
              )}
              <label>
                Backfill history starts
                <input
                  name="data_start"
                  type="date"
                  required
                  defaultValue={cfg?.data_start ?? "2016-01-04"}
                />
              </label>
              <div className="form-row">
                <label>
                  Maximum positions
                  <input
                    type="number"
                    name="positions"
                    min="1"
                    max="100"
                    required
                    defaultValue={cfg?.policy.positions ?? 25}
                  />
                </label>
                <label>
                  Stock cap (%)
                  <input
                    type="number"
                    name="max_weight"
                    min="0.1"
                    max="100"
                    step="0.1"
                    required
                    defaultValue={Number(cfg?.policy.max_weight ?? 0.05) * 100}
                  />
                </label>
                <label>
                  Sector cap (%)
                  <input
                    type="number"
                    name="sector_cap"
                    min="0.1"
                    max="100"
                    step="0.1"
                    required
                    defaultValue={Number(cfg?.policy.sector_cap ?? 0.25) * 100}
                  />
                </label>
                <label>
                  Cash reserve (%)
                  <input
                    type="number"
                    name="cash_reserve"
                    min="1"
                    max="50"
                    step="0.1"
                    required
                    defaultValue={
                      Number(cfg?.policy.cash_reserve ?? 0.05) * 100
                    }
                  />
                </label>
              </div>
              <p className="field-hint">
                Suggested initial policy: 25 names, 5% per stock, 25% per sector
                and 5% cash. Saving settings does not approve a strategy. Paper
                margin funding permits a simulated debit; no shorts or
                extended-hours orders. Target limits are not relaxed to force
                investment.
              </p>
              <Notice>
                Broker-staged Market DAY orders execute in the next regular
                session while your Mac may be off. There is no price cap: actual
                fill prices, shares and weights can differ from references. Buys
                use fixed dollar budgets and paper margin buying power so buys
                and sells can be staged together. A simulated debit can remain
                overnight if sales fail or fall short. Saving replaces a legacy
                limit or cash-funded policy and requires matching paper
                approval.
              </Notice>
              <button className="button" disabled={action.isPending}>
                Save paper settings
              </button>
            </form>
          ) : (
            <>
              <p>
                Funding:{" "}
                {cfg.funding_policy === "paper_margin"
                  ? "Paper margin — simultaneous buys and sells; an overnight simulated debit is possible."
                  : "Cash-funded — sale-dependent amounts are deferred."}
              </p>
              <p>
                <strong>
                  {state.strategies.find((s) => s.id === cfg.strategy_id)?.name}{" "}
                  · v{cfg.strategy_version}
                </strong>
              </p>
              <p>
                {cfg.symbols.length - 1} stocks · up to {cfg.policy.positions}{" "}
                positions · {percent(Number(cfg.policy.max_weight))} stock cap ·{" "}
                {percent(Number(cfg.policy.sector_cap))} sector cap ·{" "}
                {percent(Number(cfg.policy.cash_reserve))} cash floor ·{" "}
                {cfg.execution_version === "paper-broker-market-day-v1"
                  ? "Broker-staged Market DAY"
                  : `${percent(Number(cfg.max_drift))} legacy limit price band`}
              </p>
              <p>
                {cfg.execution_version === "paper-broker-market-day-v1"
                  ? "Prepare and approve outside market hours. Keep Aperture open until every instruction is confirmed accepted at Alpaca, then you may close the app. Closing does not cancel broker-held orders. The next launch checks actual fills before another rebalance."
                  : cfg.mode === "automatic"
                    ? "Automatic weekly preparation runs after the week’s final market close and submits in the next regular session, only under explicit automatic paper approval. Keep the worker running through execution and any settlement wait."
                    : "Manual mode: prepare after a completed close, inspect the plan and separately approve the following session’s paper orders. Keep Aperture running through fills and settlement."}
              </p>
              {!!cfg.exit_symbols?.length && (
                <p>
                  Exit-only holdings: {cfg.exit_symbols.join(", ")}. They can be
                  reduced, and are excluded from new-buy ranking.
                </p>
              )}
            </>
          )}
          {cfg && (
            <div className="paper-controls">
              <button
                className="button secondary"
                onClick={() =>
                  action.mutate({
                    path: cfg.paused ? "/actions/resume" : "/actions/stop",
                  })
                }
              >
                {cfg.paused
                  ? "Resume approved execution"
                  : "Stop future submissions"}
              </button>
              <button
                className="button secondary"
                onClick={() => action.mutate({ path: "/actions/cancel" })}
              >
                Stop & cancel Aperture orders
              </button>
              {data?.approval && (
                <button
                  className="text-link"
                  onClick={() => action.mutate({ path: "/revoke" })}
                >
                  Revoke strategy approval
                </button>
              )}
            </div>
          )}
          <p className="field-hint">
            Stopping does not undo fills. Cancellation is a request; an order
            may fill before cancellation. Only Aperture-owned orders are
            canceled.
          </p>
        </div>
      </section>
      {cfg && !data?.approval && (
        <Approval
          key={cfg.hash}
          cfg={cfg}
          connected={!!snap}
          onApprove={(body) => action.mutate({ path: "/approval", body })}
          busy={action.isPending}
        />
      )}
      {data?.approval && (
        <Notice>
          <ShieldCheck size={16} />
          Paper approval recorded{" "}
          {new Date(data.approval.created_at).toLocaleString()}. Automatic
          execution:{" "}
          {data.approval.allow_automatic ? "permitted" : "not permitted"}.{" "}
          {data.approval.rationale}
        </Notice>
      )}
      {cfg && (
        <section className="card">
          <div className="card-header">
            <div>
              <h2>Your weekly review</h2>
              <p>
                Preparation reconciles fills, refreshes membership and market
                inputs, and saves a review. Approval confirms broker acceptance
                before reporting success; Alpaca handles accepted orders while
                Aperture is closed.
              </p>
            </div>
            <button
              className="button"
              disabled={
                action.isPending || data?.fill_check?.status === "checking"
              }
              onClick={() => action.mutate({ path: "/actions/prepare" })}
            >
              Prepare weekly paper review
              <ArrowRight size={16} />
            </button>
          </div>
          <div className="card-body">
            <p>{data?.automatic_status}</p>
            {p &&
              data?.quote_waits?.plan_id === p.id &&
              data.quote_waits.reasons.length > 0 && (
                <Notice>
                  Waiting quotes for affected stocks; other approved targets can
                  proceed after each fill. {data.quote_waits.reasons.join(" ")}
                </Notice>
              )}
            {p && (
              <>
                <label>
                  Saved paper plan
                  <select
                    value={p.id}
                    onChange={(e) => {
                      setSelected(e.target.value);
                      setAck(false);
                    }}
                  >
                    {data?.plans?.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.strategy.name} · {p.decision_session} · {p.state}
                      </option>
                    ))}
                  </select>
                </label>
                <div className="inline">
                  <Badge tone={p.state === "blocked" ? "amber" : "green"}>
                    {p.state.replaceAll("_", " ")}
                  </Badge>
                  <p>{p.message}</p>
                </div>
                <p>
                  Signals after {p.decision_session} close · regular-session
                  execution {p.execute_session}. Target cash{" "}
                  {percent(Number(p.cash_weight))}.
                </p>
                <p>
                  Frozen account value {money(p.account.equity)} ·{" "}
                  {p.dataset_name}
                </p>
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>Stock</th>
                        <th>Action</th>
                        <th>Before</th>
                        <th>Target</th>
                        <th>
                          {p.staged_orders
                            ? "Reference shares"
                            : "Maximum shares"}
                        </th>
                        <th>Reference dollars</th>
                      </tr>
                    </thead>
                    <tbody>
                      {p.changes.map((c) => (
                        <tr key={`${c.symbol}-${c.side}`}>
                          <td>
                            {c.symbol}
                            <small>{c.sector}</small>
                          </td>
                          <td>{c.side}</td>
                          <td>{percent(Number(c.before_weight))}</td>
                          <td>{percent(Number(c.target_weight))}</td>
                          <td>{c.quantity}</td>
                          <td>{money(c.max_notional)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {!p.changes.length && (
                  <p>No orders are needed under this allocation.</p>
                )}
                {p.staged_orders && (
                  <Notice>
                    {p.staged_orders.length} instructions to stage:{" "}
                    {p.staged_orders
                      .map(
                        (o) =>
                          `${o.side} ${o.symbol} ${o.notional ? money(o.notional) : `${o.qty} shares`}`,
                      )
                      .join(" · ")}
                    .{" "}
                    {p.deferred_buys?.length
                      ? `Deferred buys: ${p.deferred_buys.map((o) => `${o.symbol} ${money(o.amount)}`).join(" · ")}. Prepare a fresh review when cash/capacity is available.`
                      : p.config?.funding_policy === "paper_margin"
                        ? "All reviewed dollar budgets are included; paper margin may bridge sale proceeds."
                        : "No sale-dependent buy amounts are included."}
                  </Notice>
                )}
                {p.funding && p.config?.funding_policy === "paper_margin" && (
                  <Notice>
                    Cash after all trades at reference prices:{" "}
                    {money(p.funding.reference_cash_after)}. Simulated debit if
                    all buys fill before sells:{" "}
                    {money(p.funding.debit_if_buys_fill_first)}. These are
                    estimates; failed sells or price gaps can leave an overnight
                    debit. No running app is required for accepted orders, and
                    no automatic liquidation is scheduled.
                  </Notice>
                )}
                {p.notes.map((n) => (
                  <p className="field-hint" key={n}>
                    {n}
                  </p>
                ))}
                <Notice>
                  Free-source inputs remain exploratory. Inspect excluded stocks
                  and filings.{" "}
                  {p.staged_orders
                    ? "Market buys use the displayed dollar budgets; actual shares and portfolio weights depend on fills. Closing Aperture does not cancel accepted orders. Deferred amounts require a fresh review."
                    : "Buy quantities may shrink within the reviewed dollar/target/cash bounds; material changes require a fresh review."}
                </Notice>
                {p.state === "prepared" && (
                  <div className="validation-actions">
                    <label className="check-label">
                      <input
                        type="checkbox"
                        checked={ack}
                        onChange={(e) => setAck(e.target.checked)}
                      />
                      {p.staged_orders
                        ? `I reviewed this plan and approve its Market DAY PAPER orders. I accept price gaps, fixed dollar buys and ${p.config?.funding_policy === "paper_margin" ? "paper margin use, including a possible overnight debit" : "the deferred amounts shown"}.`
                        : "I reviewed this plan and approve its following-session PAPER orders within the displayed policy and price bounds."}
                    </label>
                    <button
                      className="button"
                      disabled={
                        !ack ||
                        !data?.approval ||
                        !!cfg.paused ||
                        action.isPending
                      }
                      onClick={() =>
                        action.mutate({
                          path: `/plans/${p.id}/approve`,
                          body: { acknowledge: ack },
                        })
                      }
                    >
                      {action.isPending && p.staged_orders
                        ? "Confirming acceptance at Alpaca…"
                        : p.staged_orders
                          ? "Approve & stage at Alpaca"
                          : "Approve paper rebalance"}
                    </button>
                  </div>
                )}
                {p.state === "blocked" &&
                  p.message.toLowerCase().includes("quote") && (
                    <div className="validation-actions">
                      <label className="check-label">
                        <input
                          type="checkbox"
                          checked={ack}
                          onChange={(e) => setAck(e.target.checked)}
                        />
                        I rechecked this frozen plan. Retry its quote validation
                        under the same bounds, retaining confirmed fills.
                      </label>
                      <button
                        className="button"
                        disabled={
                          !ack ||
                          action.isPending ||
                          !data?.approval ||
                          !!cfg.paused
                        }
                        onClick={() =>
                          action.mutate({
                            path: `/plans/${p.id}/retry-quote`,
                            body: { acknowledge: ack },
                          })
                        }
                      >
                        Recheck quotes & resume this plan
                      </button>
                    </div>
                  )}
                <details className="details">
                  <summary>Signals, filings & excluded stocks</summary>
                  <SignalAudit
                    fundamental={[
                      "quality",
                      "quality_value",
                      "value_momentum",
                    ].includes(p.strategy.id)}
                    decisions={[
                      {
                        session: p.decision_session,
                        execute_session: p.execute_session,
                        eligible: p.signals?.length ?? 0,
                        signals: p.signals,
                        exclusions: p.excluded,
                      },
                    ]}
                  />
                </details>
                <button
                  className="button small secondary"
                  onClick={() => download(`paper-plan-${p.id}.json`, p)}
                >
                  <Download size={15} />
                  Export frozen paper plan
                </button>
                <p className="digest">Source fingerprint: {p.source_digest}</p>
              </>
            )}
          </div>
        </section>
      )}
      {snap && (
        <section className="card">
          <div className="card-header">
            <div>
              <h2>Actual positions & broker orders</h2>
              <p>
                Broker records are authoritative. Refresh after manual account
                changes.
              </p>
            </div>
            <Badge>{snap.positions.length} positions</Badge>
          </div>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Stock</th>
                  <th>Shares</th>
                  <th>Market value</th>
                  <th>Weight</th>
                  <th>Unrealized P/L</th>
                </tr>
              </thead>
              <tbody>
                {snap.positions.map((r) => (
                  <tr key={r.symbol}>
                    <td>{r.symbol}</td>
                    <td>{r.qty}</td>
                    <td>{money(r.market_value)}</td>
                    <td>
                      {percent(Number(r.market_value) / Number(snap.equity))}
                    </td>
                    <td>{money(r.unrealized_pl)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="card-body">
            {!snap.positions.length && (
              <p>No stock positions at the last account check.</p>
            )}
            <h3>Open orders at broker</h3>
            {snap.open_orders.length ? (
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Stock</th>
                      <th>Side</th>
                      <th>Status</th>
                      <th>Filled / requested</th>
                    </tr>
                  </thead>
                  <tbody>
                    {snap.open_orders.map((o) => (
                      <tr key={o.id}>
                        <td>{o.symbol}</td>
                        <td>{o.side}</td>
                        <td>{o.status}</td>
                        <td>
                          {o.filled_qty} shares /{" "}
                          {o.notional
                            ? money(o.notional)
                            : `${o.qty ?? "—"} shares`}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p>No open broker orders at the last check.</p>
            )}
          </div>
        </section>
      )}
      {!!data?.orders?.length && (
        <section className="card">
          <div className="card-header">
            <div>
              <h2>Paper order lifecycle</h2>
              <p>
                Partial, rejected and uncertain orders remain in this record
                across restarts.
              </p>
            </div>
          </div>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Stock</th>
                  <th>Action</th>
                  <th>Status</th>
                  <th>Order type</th>
                  <th>Requested</th>
                  <th>Filled</th>
                  <th>Average fill</th>
                  <th>Reference price</th>
                  <th>Fill vs reference</th>
                  <th>Client reference</th>
                </tr>
              </thead>
              <tbody>
                {data.orders.map((o) => (
                  <tr key={o.client_id}>
                    <td>{o.symbol}</td>
                    <td>{o.side}</td>
                    <td>
                      {o.state}
                      <small>{o.broker?.reason}</small>
                    </td>
                    <td>
                      {o.request.type === "market" ? "Market DAY" : "Limit DAY"}
                    </td>
                    <td>
                      {o.request.notional
                        ? money(o.request.notional)
                        : `${o.request.qty ?? "—"} shares`}
                    </td>
                    <td>{o.broker?.filled_qty ?? "0"}</td>
                    <td>
                      {o.broker?.filled_avg_price
                        ? money(o.broker.filled_avg_price)
                        : "—"}
                    </td>
                    <td>
                      {references.get(`${o.plan_id}:${o.symbol}:${o.side}`)
                        ? money(
                            references.get(
                              `${o.plan_id}:${o.symbol}:${o.side}`,
                            )!,
                          )
                        : "—"}
                    </td>
                    <td>
                      {references.get(`${o.plan_id}:${o.symbol}:${o.side}`) &&
                      o.broker?.filled_avg_price
                        ? percent(
                            Number(o.broker.filled_avg_price) /
                              references.get(
                                `${o.plan_id}:${o.symbol}:${o.side}`,
                              )! -
                              1,
                            true,
                          )
                        : "—"}
                    </td>
                    <td>
                      <code>{o.client_id}</code>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
      {snap && <PaperPerformance />}
      {!!data?.events?.length && (
        <section className="card">
          <div className="card-header">
            <h2>Paper activity</h2>
          </div>
          <div className="card-body">
            {data.events.slice(0, 20).map((e) => (
              <p key={e.id}>
                <small>{new Date(e.created_at).toLocaleString()}</small>
                <br />
                {e.message}
              </p>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
function Approval({
  cfg,
  connected,
  onApprove,
  busy,
}: {
  cfg: Config;
  connected: boolean;
  onApprove: (body: unknown) => void;
  busy: boolean;
}) {
  const [ack, setAck] = useState(false);
  const phrase = `APPROVE PAPER ${cfg.strategy_id} ${cfg.strategy_version}`;
  return (
    <section className="card">
      <div className="card-header">
        <div>
          <span className="eyebrow">YOUR EXPLICIT DECISION</span>
          <h2>Approve this strategy for paper use</h2>
          <p>
            Approval binds this strategy version, risk policy, universe and
            checked paper account.
          </p>
        </div>
      </div>
      <form
        className="form card-body"
        onSubmit={(e) => {
          e.preventDefault();
          const f = new FormData(e.currentTarget);
          onApprove({
            config_hash: cfg.hash,
            confirmation: f.get("confirmation"),
            rationale: f.get("rationale"),
            acknowledge_limits: ack,
            allow_automatic: f.get("allow_automatic") === "on",
          });
        }}
      >
        <Notice>
          Research results do not prove profitability. Historical membership,
          departed stocks, annual-filing timing/share basis and static sectors
          remain limited. This permission manages the dedicated paper account’s
          approved universe. No live approval is included.
          {cfg.execution_version === "paper-broker-market-day-v1" &&
            ` This policy stages Market DAY orders before the open without a price cap. Fills can gap beyond references. ${cfg.funding_policy === "paper_margin" ? "Paper margin may fund buys before sales fill, and a simulated debit can remain overnight. The cash reserve is a reference target, not a guaranteed final balance." : "Buy dollar budgets use available cash; sale-dependent amounts remain deferred."}`}
        </Notice>
        <label>
          Approval rationale
          <textarea
            name="rationale"
            minLength={10}
            maxLength={2000}
            required
            placeholder="Record the research and validation you reviewed, risks and reasons for this paper experiment."
          />
        </label>
        <label>
          Type {phrase}
          <input
            name="confirmation"
            autoComplete="off"
            required
            pattern={phrase}
            placeholder={phrase}
          />
        </label>
        <label className="check-label">
          <input
            type="checkbox"
            checked={ack}
            onChange={(e) => setAck(e.target.checked)}
          />
          I accept these research/data limits and the displayed policy for this
          dedicated, long-only PAPER account
          {cfg.funding_policy === "paper_margin"
            ? ", including simulated margin and possible overnight debit"
            : ", without margin borrowing"}
          .
        </label>
        <label className="check-label">
          <input type="checkbox" name="allow_automatic" />
          Also permit automatic weekly PAPER preparation and staging under this
          exact policy while Aperture is open.
        </label>
        <button className="button" disabled={!connected || !ack || busy}>
          Record paper strategy approval
        </button>
      </form>
    </section>
  );
}
