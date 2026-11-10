import type { Dataset } from "./types";

export default function HistoricalIssuers({ dataset }: { dataset: Dataset }) {
  const evidence = dataset.metadata?.historical_issuer_evidence;
  if (!evidence || typeof evidence !== "object") return null;
  const rows = Object.entries(evidence)
    .filter(
      ([symbol, proof]) =>
        proof &&
        typeof proof === "object" &&
        proof.symbol === symbol &&
        typeof proof.quote_asof === "string" &&
        typeof proof.url === "string" &&
        typeof proof.basis === "string",
    )
    .sort(([a], [b]) => a.localeCompare(b));
  if (!rows.length) return null;
  return (
    <details className="details">
      <summary>Historical issuer evidence · {rows.length} mappings</summary>
      <p>
        Dated filings identify these historical tickers and their financial
        histories. Each mapping applies to the captured quote vintage. Price,
        corporate-action and filing-availability checks still apply.
      </p>
      <ul>
        {rows.map(([symbol, proof]) => (
          <li key={symbol}>
            <strong>
              {symbol} · {proof.name}
            </strong>
            <p>
              Quote vintage {proof.quote_asof}. {proof.basis}{" "}
              <a href={proof.url} target="_blank" rel="noreferrer">
                Primary filing
              </a>
            </p>
          </li>
        ))}
      </ul>
    </details>
  );
}
