import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Database, Download, PlugZap } from "lucide-react";
import { api } from "./api";
import { Badge, Notice } from "./components";

type ProviderInfo = {
  alpaca_configured: boolean;
  sec_configured: boolean;
  latest_session: string;
  first_session: string;
  watchlist: {
    name: string;
    universe?: string;
    symbols: string[];
    start: string;
  };
  membership?: { current: Membership | null; historical: Membership | null };
};
type Membership = {
  id: string;
  captured_at: string;
  source: string;
  member_count: number;
  coverage_start: string;
  coverage_end: string;
  added?: string[];
  removed?: string[];
  initial?: boolean;
};

export default function MarketData() {
  const client = useQueryClient();
  const navigate = useNavigate();
  const info = useQuery({
    queryKey: ["providers"],
    queryFn: () => api<ProviderInfo>("/providers"),
    staleTime: 0,
  });
  const enqueue = useMutation({
    mutationFn: ({ path, body }: { path: string; body: unknown }) =>
      api(path, body),
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ["state"] });
      navigate("/activity");
    },
  });
  const cfg = info.data;
  const [universe, setUniverse] = useState("sp500_current");
  const historical =
    universe === "sp500_historical" ? cfg?.membership?.historical : null;
  const end = historical
    ? [
        historical.coverage_end,
        cfg?.latest_session ?? historical.coverage_end,
      ].sort()[0]
    : (cfg?.latest_session ?? "");
  const requestedStart = cfg?.watchlist?.start ?? "2022-01-03";
  const start =
    historical && requestedStart >= end
      ? end > "2022-01-03"
        ? "2022-01-03"
        : [
            historical.coverage_start,
            cfg?.first_session ?? historical.coverage_start,
          ]
            .sort()
            .at(-1)
      : requestedStart;
  return (
    <section className="card market-data">
      <div className="card-header">
        <div>
          <span className="eyebrow">A CONNECTED RESEARCH WORKSPACE</span>
          <h2>Download market data</h2>
          <p>
            Consolidated US daily prices, split events and cash-dividend pay
            dates.
          </p>
        </div>
        <Badge tone={cfg?.alpaca_configured ? "green" : ""}>
          {info.isPending
            ? "Checking configuration"
            : cfg?.alpaca_configured
              ? "Paper keys configured"
              : "Keys needed"}
        </Badge>
      </div>
      <div className="card-body">
        {info.error && <Notice error>{info.error.message}</Notice>}
        {!info.isPending && !cfg?.alpaca_configured && (
          <Notice>
            Add paper credentials to the ignored local .env file using
            ALPACA_API_KEY and ALPACA_SECRET_KEY. This page never displays or
            stores the keys. CSV and practice data remain available.
          </Notice>
        )}
        <div className="provider-summary">
          <span>
            <Database size={16} />
            Alpaca · SIP historical feed · as-traded prices
          </span>
          <button
            className="button secondary small"
            disabled={!cfg?.alpaca_configured || enqueue.isPending}
            onClick={() =>
              enqueue.mutate({ path: "/providers/check", body: {} })
            }
          >
            <PlugZap size={15} />
            Test connection
          </button>
        </div>
        <div className="membership-status">
          <h3>S&P 500 membership</h3>
          {(["current", "historical"] as const).map((kind) => {
            const saved = cfg?.membership?.[kind];
            return (
              <div key={kind}>
                <p>
                  <strong>
                    {kind === "current"
                      ? "Current roster"
                      : "Historical rosters"}
                  </strong>
                  {saved
                    ? ` · ${saved.member_count} securities · captured ${new Date(saved.captured_at).toLocaleString()}`
                    : " · Not downloaded yet"}
                </p>
                {saved && (
                  <p className="field-hint">
                    {kind === "historical"
                      ? `Available history: ${saved.coverage_start} – ${saved.coverage_end}. The final roster is never extended beyond this date.`
                      : saved.initial
                        ? "First capture saved. Future refreshes report additions and removals."
                        : `Changes since previous capture: added ${saved.added?.join(", ") || "none"}; removed ${saved.removed?.join(", ") || "none"}.`}{" "}
                    <a href={saved.source} target="_blank" rel="noreferrer">
                      Source
                    </a>
                  </p>
                )}
                <button
                  type="button"
                  className="button secondary small"
                  disabled={enqueue.isPending}
                  onClick={() =>
                    enqueue.mutate({
                      path: `/membership/${kind}/refresh`,
                      body: {},
                    })
                  }
                >
                  Refresh{" "}
                  {kind === "current"
                    ? "current membership"
                    : "historical membership"}
                </button>
              </div>
            );
          })}
        </div>
        <form
          className="form"
          key={`${cfg?.latest_session ?? "loading"}-${universe}`}
          onSubmit={(e) => {
            e.preventDefault();
            const values = new FormData(e.currentTarget);
            enqueue.mutate({
              path: "/downloads",
              body: {
                name: values.get("name"),
                universe,
                symbols: String(values.get("symbols"))
                  .split(/[\s,;]+/)
                  .filter(Boolean),
                start: values.get("start"),
                end: values.get("end"),
              },
            });
          }}
        >
          <label>
            Dataset name
            <input
              name="name"
              defaultValue={"S&P 500 + supplements"}
              maxLength={100}
              required
            />
          </label>
          <label>
            Stock universe
            <select
              name="universe"
              value={universe}
              onChange={(e) => setUniverse(e.target.value)}
            >
              <option value="sp500_current">
                Current S&P 500 + optional supplements
              </option>
              <option value="sp500_historical">
                Historical S&P 500 members + optional supplements
              </option>
              <option value="custom">Custom list only</option>
            </select>
          </label>
          <label>
            {universe === "custom"
              ? "Stock symbols"
              : "Additional stock symbols (optional)"}
            <textarea
              name="symbols"
              rows={3}
              defaultValue={
                cfg?.watchlist?.symbols
                  ?.filter((s) => s !== "SPY")
                  .join(", ") ?? ""
              }
              required={universe === "custom"}
              placeholder="Optional names outside the S&P 500"
            />
          </label>
          <p className="field-hint">
            The full S&P 500 is included by default, with every listed share
            class. Additional symbols supplement the index. SPY is always
            included only as a benchmark. Downloads refresh membership when its
            capture is over 24 hours old.
          </p>
          <Notice>
            {universe === "sp500_current"
              ? "Current members support current reviews. To backtest history, choose Historical S&P 500 members; today's roster cannot be backdated."
              : universe === "sp500_historical"
                ? "Historical downloads include all members present during the selected period, including departures. Dates outside the source coverage and missing member prices stop the job. The public history is retrospective, with no certified announcement times or security identities; results remain exploratory."
                : "A custom fixed list can introduce survivorship and selection bias in historical tests."}
          </Notice>
          <div className="form-row">
            <label>
              History from
              <input
                name="start"
                type="date"
                defaultValue={start}
                min={cfg?.first_session}
                max={cfg?.latest_session}
                required
              />
            </label>
            <label>
              Through session
              <input
                name="end"
                type="date"
                defaultValue={end}
                min={cfg?.first_session}
                max={cfg?.latest_session}
                required
              />
            </label>
          </div>
          <div className="inline">
            <button
              className="button"
              disabled={!cfg?.alpaca_configured || enqueue.isPending}
              type="submit"
            >
              <Download size={16} />
              Download & validate
            </button>
            <small>
              Existing snapshots stay unchanged. Repeated identical data
              deduplicates.
            </small>
          </div>
        </form>
        {enqueue.error && <Notice error>{enqueue.error.message}</Notice>}
        <details className="details">
          <summary>What is checked, and what is still uncertain?</summary>
          <p>
            Downloads check active and archived US listings, retaining inactive
            names for historical prices. Unavailable or ambiguous identities
            stop the download rather than silently dropping departures. Paper
            trading separately requires tradable listings. Split ratios are
            checked against adjusted provider bars; unsupported actions stop the
            download. Per-stock gaps and raw response fingerprints are retained.
            Historical membership, delisted coverage and historical sectors are
            not certified. No alternate feed is silently substituted.
          </p>
          <p>
            Data uses the latest completed session after close + 15 minutes.
            Daily prices follow Alpaca’s trade-condition rules, and a backtest
            open is a fill assumption. Corporate actions can arrive late; no
            free vendor is treated as infallible.
          </p>
        </details>
      </div>
    </section>
  );
}
