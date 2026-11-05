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
  unique_member_count?: number;
  coverage_start: string;
  coverage_end: string;
  last_change?: string;
  verified_through?: string;
  verification_basis?: string;
  events?: { source: string }[];
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
  const [universe, setUniverse] = useState("sp500");
  const names: Record<string, string> = {
    sp500: "S&P 500",
    sp500_plus: "S&P 500 + custom list",
    custom: "Custom stock list",
  };
  const [datasetName, setDatasetName] = useState("S&P 500");
  const current = cfg?.membership?.current;
  const historical = cfg?.membership?.historical;
  const end = cfg?.latest_session ?? "";
  const start = cfg?.first_session ?? "2016-01-04";
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
          <p>
            {current
              ? `${current.member_count} current securities`
              : "Current roster not downloaded yet"}
            {historical?.unique_member_count != null &&
              ` · ${historical.unique_member_count.toLocaleString()} unique securities in the historical archive`}
          </p>
          <p className="field-hint">
            {historical
              ? `Historical backtest membership: ${historical.coverage_start} – ${historical.coverage_end}.`
              : "Historical membership not downloaded yet."}{" "}
            {cfg && `Prices can be downloaded through ${cfg.latest_session}.`}
          </p>
          <button
            type="button"
            className="button secondary small"
            disabled={enqueue.isPending}
            onClick={() =>
              enqueue.mutate({ path: "/membership/all/refresh", body: {} })
            }
          >
            Refresh S&P 500 membership
          </button>
          <details className="details">
            <summary>Membership sources and changes</summary>
            {(["current", "historical"] as const).map((kind) => {
              const saved = cfg?.membership?.[kind];
              return (
                saved && (
                  <div key={kind}>
                    <p>
                      <strong>
                        {kind === "current"
                          ? "Current roster"
                          : "Historical archive"}
                      </strong>
                      {` · captured ${new Date(saved.captured_at).toLocaleString()}`}{" "}
                      ·{" "}
                      <a href={saved.source} target="_blank" rel="noreferrer">
                        Source
                      </a>
                    </p>
                    <p className="field-hint">
                      {kind === "historical"
                        ? `Last recorded change: ${saved.last_change ?? saved.coverage_end}; ${saved.member_count} securities in that roster. A last change date is not an expiry date. ${saved.verified_through ? `Verified through ${saved.verified_through} using dated announcements and current-roster reconciliation.` : "Update membership to verify later coverage."}`
                        : saved.initial
                          ? "First capture saved. Future refreshes report additions and removals."
                          : `Changes since previous capture: added ${saved.added?.join(", ") || "none"}; removed ${saved.removed?.join(", ") || "none"}.`}
                    </p>
                    {saved.events && (
                      <p className="field-hint">
                        Dated primary evidence:{" "}
                        {[
                          ...new Set(saved.events.map((event) => event.source)),
                        ].map((source, index) => (
                          <span key={source}>
                            {index > 0 && " · "}
                            <a href={source} target="_blank" rel="noreferrer">
                              Source {index + 1}
                            </a>
                          </span>
                        ))}
                      </p>
                    )}
                  </div>
                )
              );
            })}
          </details>
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
                universe: universe === "sp500_plus" ? "sp500" : universe,
                symbols: (universe === "sp500"
                  ? ""
                  : String(values.get("symbols"))
                )
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
              value={datasetName}
              onChange={(e) => setDatasetName(e.target.value)}
              maxLength={100}
              required
            />
          </label>
          <label>
            Stock universe
            <select
              name="universe"
              value={universe}
              onChange={(e) => {
                const next = e.target.value;
                setDatasetName((old) =>
                  old === names[universe] ? names[next] : old,
                );
                setUniverse(next);
              }}
            >
              <option value="sp500">
                S&P 500 — current and historical members
              </option>
              <option value="sp500_plus">S&P 500 + custom list</option>
              <option value="custom">Custom list only</option>
            </select>
          </label>
          {universe !== "sp500" && (
            <label>
              {universe === "custom"
                ? "Stock symbols"
                : "Additional stock symbols"}
              <textarea
                name="symbols"
                rows={3}
                defaultValue={
                  cfg?.watchlist?.symbols
                    ?.filter((s) => s !== "SPY")
                    .join(", ") ?? ""
                }
                required
                placeholder={
                  universe === "custom"
                    ? "AAPL, MSFT, …"
                    : "Symbols outside the S&P 500"
                }
              />
            </label>
          )}
          <p className="field-hint">
            {universe !== "custom"
              ? "Includes today's full S&P 500 and every historical member recorded during the selected period, including departures and separate share classes. Membership refreshes when over 24 hours old or coverage trails a new completed session."
              : "Downloads only your custom stock list."}{" "}
            SPY is always included only as a benchmark.
          </p>
          <Notice>
            {universe !== "custom"
              ? "One download collects available current and historical prices. Unresolved securities stay visible with per-stock reasons; tests and reviews requiring them are blocked. Backtests automatically use dated membership within supported coverage. Newer prices do not fill missing membership changes. Public history remains retrospective and exploratory."
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
