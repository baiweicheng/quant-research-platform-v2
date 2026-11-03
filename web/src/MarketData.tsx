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
  watchlist: { name: string; symbols: string[]; start: string };
};

export default function MarketData() {
  const client = useQueryClient();
  const navigate = useNavigate();
  const info = useQuery({
    queryKey: ["providers"],
    queryFn: () => api<ProviderInfo>("/providers"),
    staleTime: 30000,
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
        <form
          className="form"
          key={cfg?.latest_session ?? "loading"}
          onSubmit={(e) => {
            e.preventDefault();
            const values = new FormData(e.currentTarget);
            enqueue.mutate({
              path: "/downloads",
              body: {
                name: values.get("name"),
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
            Watchlist name
            <input
              name="name"
              defaultValue={cfg?.watchlist?.name ?? "US stock watchlist"}
              maxLength={100}
              required
            />
          </label>
          <label>
            Stock symbols
            <textarea
              name="symbols"
              rows={3}
              defaultValue={
                cfg?.watchlist?.symbols?.join(", ") ?? "AAPL, MSFT, SPY"
              }
              required
            />
          </label>
          <p className="field-hint">
            Start with roughly 25–50 companies. Custom US-listed names outside
            the S&P 500 are welcome; SPY is always included as the benchmark.
            This is a current watchlist, not a historical index-membership
            database.
          </p>
          <div className="form-row">
            <label>
              History from
              <input
                name="start"
                type="date"
                defaultValue={cfg?.watchlist?.start ?? "2022-01-03"}
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
                defaultValue={cfg?.latest_session ?? ""}
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
            Every selected name must be an active US exchange listing. Split
            ratios are checked against adjusted provider bars; unsupported
            actions stop the download. Per-stock gaps and raw response
            fingerprints are retained. Historical membership, delisted coverage
            and historical sectors are not certified. No alternate feed is
            silently substituted.
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
