import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, shortDate } from "./api";
import { Notice } from "./components";
import type { Dataset, SectorAudit } from "./types";

const methods: Record<string, string> = {
  captured_current_roster: "Current S&P roster",
  archived_constituent_last_known: "Public constituent archive",
  dated_public_classification: "Dated public classification",
  reviewed_business_proxy: "Reviewed issuer-business proxy",
  reviewed_historical_alias: "Reviewed historical ticker",
  reviewed_warrant_issuer: "Warrant issuer exposure",
  declared_snapshot_sector: "Declared snapshot sector",
  not_applicable: "Fund / benchmark",
  unresolved: "Unresolved",
};

export default function SectorCoverage({ dataset }: { dataset: Dataset }) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const summary = dataset.metadata?.sector_classification;
  const audit = useQuery({
    queryKey: ["sectors", dataset.id],
    queryFn: () => api<SectorAudit>(`/datasets/${dataset.id}/sectors`),
    enabled: open && !!summary,
  });
  if (dataset.kind === "synthetic") return null;
  if (!summary)
    return (
      <Notice>
        This snapshot predates sector coverage auditing. Use Refresh sectors
        above to capture classifications in a new snapshot. Missing labels can
        leave extra cash under the sector cap.
      </Notice>
    );
  const rows = Object.values(audit.data?.records ?? {}).filter((row) =>
    `${row.symbol} ${row.name ?? ""} ${row.sector ?? ""}`
      .toLowerCase()
      .includes(search.toLowerCase()),
  );
  return (
    <details
      className="details"
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary>
        Sector coverage · {summary.classified_count} classified ·{" "}
        {summary.unresolved_count} unresolved
      </summary>
      <p>{summary.warning}</p>
      <p>
        {summary.not_applicable_count} funds or benchmarks have no
        operating-company sector. Evidence captured{" "}
        {shortDate(summary.captured_at.slice(0, 10))}. Sector caps remain
        enforced; unresolved stocks share one Unknown bucket.
      </p>
      {summary.unresolved_count > 0 && (
        <Notice>
          Unresolved sectors: {summary.unresolved_symbols.join(", ")}. These can
          constrain investment and leave additional cash.
        </Notice>
      )}
      <label>
        Find a sector classification
        <input
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Symbol, company or sector"
        />
      </label>
      {audit.isPending ? (
        <p role="status">Loading classification evidence…</p>
      ) : audit.error ? (
        <Notice error>{audit.error.message}</Notice>
      ) : (
        <>
          <p className="field-hint">
            Showing {Math.min(rows.length, 100)} of {rows.length} matching
            entries. Search to narrow the list; the metadata export contains
            every entry.
          </p>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Stock</th>
                  <th>Sector</th>
                  <th>Evidence</th>
                </tr>
              </thead>
              <tbody>
                {rows.slice(0, 100).map((row) => (
                  <tr key={row.symbol}>
                    <td>
                      <strong>{row.symbol}</strong>
                      <small>{row.name}</small>
                    </td>
                    <td>{row.sector ?? "Not applicable"}</td>
                    <td>
                      {methods[row.method] ?? row.method}
                      {row.evidence_date && <small>{row.evidence_date}</small>}
                      {row.source?.startsWith("https://") && (
                        <small>
                          <a href={row.source} target="_blank" rel="noreferrer">
                            Source
                          </a>
                        </small>
                      )}
                      {row.reason && <small>{row.reason}</small>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </details>
  );
}
