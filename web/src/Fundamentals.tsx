import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { FileText, ArrowRight } from "lucide-react";
import { api, percent, shortDate } from "./api";
import { Badge, Notice } from "./components";
import type { Dataset, Decision, FundamentalCoverage } from "./types";

export function FundamentalsPanel({ datasets }: { datasets: Dataset[] }) {
  const client = useQueryClient();
  const navigate = useNavigate();
  const config = useQuery({
    queryKey: ["providers"],
    queryFn: () => api<{ sec_configured: boolean }>("/providers"),
    staleTime: 30000,
  });
  const available = datasets.filter((d) => d.kind !== "synthetic");
  const [selected, setSelected] = useState("");
  const id = selected || available[0]?.id || "";
  const task = useMutation({
    mutationFn: () => api(`/fundamentals/${id}`, {}),
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ["state"] });
      navigate("/activity");
    },
  });
  return (
    <section className="card market-data">
      <div className="card-header">
        <div>
          <span className="eyebrow">A BUSINESS BEHIND EVERY PRICE</span>
          <h2>Add SEC fundamentals</h2>
          <p>Annual financial statements, with the filing date preserved.</p>
        </div>
        <Badge tone={config.data?.sec_configured ? "green" : ""}>
          {config.data?.sec_configured
            ? "SEC contact configured"
            : "SEC contact needed"}
        </Badge>
      </div>
      <div className="card-body">
        <p>
          Unlock profitability, quality value, and Value + Momentum. Prices stay
          in their original snapshot; a new combined dataset holds both inputs.
        </p>
        {!config.isPending && !config.data?.sec_configured && (
          <Notice>
            Add SEC_USER_AGENT with your name and contact email to the local
            .env file. SEC data is free and needs no API key.
          </Notice>
        )}
        {!available.length ? (
          <p className="field-hint">
            Download or import actual market data first. Fictional practice
            symbols have no SEC statements.
          </p>
        ) : (
          <form
            className="form"
            onSubmit={(e) => {
              e.preventDefault();
              task.mutate();
            }}
          >
            <label>
              Price dataset
              <select
                value={id}
                onChange={(e) => {
                  setSelected(e.target.value);
                  task.reset();
                }}
              >
                {available.map((d) => (
                  <option value={d.id} key={d.id}>
                    {d.name}
                  </option>
                ))}
              </select>
            </label>
            <div>
              <button
                type="submit"
                className="button secondary"
                disabled={!config.data?.sec_configured || task.isPending}
              >
                <FileText size={16} /> Add fundamentals <ArrowRight size={15} />
              </button>
            </div>
          </form>
        )}
        {task.error && <Notice error>{task.error.message}</Notice>}
        <details className="details">
          <summary>What is supported?</summary>
          <p>
            Annual US-GAAP 10-K and 10-K/A filings, with matching periods and
            USD units. A filing becomes usable after close on the first exchange
            session following its filing date. Amendments affect only later
            decisions.
          </p>
          <p>
            Some sectors use different accounting. Missing, stale, ambiguous and
            unsupported inputs exclude a stock. Multiple listed share classes
            are excluded from per-share valuation. These are annual metrics, not
            estimates of trailing twelve months.
          </p>
        </details>
      </div>
    </section>
  );
}

export function FundamentalDetails({ data }: { data: FundamentalCoverage }) {
  return (
    <details className="details">
      <summary>
        SEC filing coverage · {data.record_count.toLocaleString()} records
      </summary>
      <p>
        {data.coverage.filter((r) => r.quality_ready).length} stocks with
        positive profitability ·{" "}
        {data.coverage.filter((r) => r.value_ready).length} with positive
        compatible EPS at the dataset end. Historical eligibility varies by
        decision.
      </p>
      <p>{data.availability}</p>
      <div className="table-scroll">
        <table className="fundamental-table">
          <thead>
            <tr>
              <th>Stock</th>
              <th>Annual periods / filings</th>
              <th>Profitability</th>
              <th>Valuation</th>
              <th>Latest fiscal end / filed</th>
              <th>Coverage notes</th>
            </tr>
          </thead>
          <tbody>
            {data.coverage.map((row) => (
              <tr key={row.symbol}>
                <td>
                  <strong>{row.symbol}</strong>
                </td>
                <td>{row.records}</td>
                <td>{row.quality_ready ? "Eligible input" : "Excluded"}</td>
                <td>{row.value_ready ? "Eligible input" : "Excluded"}</td>
                <td>
                  {row.latest_period || "—"}
                  <br />
                  {row.latest_filed || "—"}
                </td>
                <td>
                  {row.reason ||
                    "Exact annual units and periods required; see decision audit for actual eligibility."}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}

export function SignalAudit({
  decisions,
  fundamental = false,
}: {
  decisions: Decision[];
  fundamental?: boolean;
}) {
  const available =
    fundamental ||
    decisions.some((d) => d.signals?.some((s) => s.components.filing))
      ? decisions
      : [];
  const [chosen, setChosen] = useState("");
  const decision =
    available.find((d) => d.session === chosen) || available.at(-1);
  if (!decision) return null;
  return (
    <section className="card">
      <div className="card-header">
        <div>
          <h2>Why these stocks?</h2>
          <p>Inspect the inputs that were available at each decision.</p>
        </div>
        <Badge>Filing audit</Badge>
      </div>
      <div className="card-body form">
        <label>
          Signal decision
          <select
            value={decision.session}
            onChange={(e) => setChosen(e.target.value)}
          >
            {available.map((d) => (
              <option value={d.session} key={d.session}>
                {d.session} · {d.eligible} eligible stocks
              </option>
            ))}
          </select>
        </label>
        <p className="field-hint">
          Decided {shortDate(decision.session)} after close · Intended execution{" "}
          {shortDate(decision.execute_session)}. Positive factors are required.
          Blends use average percentile ranks within the jointly eligible
          stocks; ties share a rank.
        </p>
      </div>
      <div className="table-scroll">
        <table className="fundamental-table">
          <thead>
            <tr>
              <th>Stock / rank score</th>
              <th>Gross profit / assets</th>
              <th>Annual earnings yield</th>
              <th>12–1 momentum</th>
              <th>Statement & availability</th>
            </tr>
          </thead>
          <tbody>
            {decision.signals?.map((stock) => {
              const f = stock.components.filing;
              return (
                <tr key={stock.symbol}>
                  <td>
                    <strong>{stock.symbol}</strong>
                    <br />
                    {stock.score.toFixed(4)}
                  </td>
                  <td>
                    {stock.components.profitability === undefined
                      ? "—"
                      : percent(Number(stock.components.profitability))}
                  </td>
                  <td>
                    {stock.components.earnings_yield === undefined
                      ? "—"
                      : percent(Number(stock.components.earnings_yield))}
                  </td>
                  <td>
                    {stock.components.momentum === undefined
                      ? "—"
                      : percent(stock.components.momentum)}
                  </td>
                  <td>
                    {f && (
                      <details>
                        <summary>
                          Fiscal end {f.end} · filed {f.filed}
                        </summary>
                        <p>
                          Annual period {f.start} – {f.end}. Usable{" "}
                          {new Date(f.available_at).toLocaleString()}.
                        </p>
                        <p>Tags: {Object.values(f.sources).join("; ")}</p>
                        <p>{f.issues.join(" ")}</p>
                        <a href={f.url} target="_blank" rel="noreferrer">
                          SEC filing {f.accession}
                        </a>
                      </details>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="card-body">
        <details className="details">
          <summary>
            Excluded stocks ({decision.exclusions?.length ?? 0})
          </summary>
          {decision.exclusions?.length ? (
            decision.exclusions.map((row) => (
              <p key={row.symbol}>
                <strong>{row.symbol}</strong> — {row.reason}
              </p>
            ))
          ) : (
            <p>
              All stocks met this decision’s input and positivity requirements.
            </p>
          )}
        </details>
        <p className="field-hint">
          Rank eligibility is separate from the portfolio caps. Full signal
          components and source fingerprints are saved in the result export.
        </p>
      </div>
    </section>
  );
}
