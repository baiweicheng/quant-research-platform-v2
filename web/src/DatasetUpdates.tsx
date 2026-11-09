import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { RefreshCw } from "lucide-react";
import { api } from "./api";
import { snapshotGroups, snapshotLabel } from "./snapshots";
import { Notice } from "./components";
import type { Dataset } from "./types";

export default function DatasetUpdates({
  datasets,
  preparing = false,
}: {
  datasets: Dataset[];
  preparing?: boolean;
}) {
  const available = snapshotGroups(datasets).latest.filter(
    (d) => d.metadata?.provider === "alpaca",
  );
  const [selected, setSelected] = useState("");
  const id = available.some((dataset) => dataset.id === selected)
    ? selected
    : available[0]?.id || "";
  const chosen = available.find((d) => d.id === id);
  const client = useQueryClient();
  const navigate = useNavigate();
  const task = useMutation({
    mutationFn: () => api(`/datasets/${id}/update`, {}),
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ["state"] });
      navigate("/activity");
    },
  });
  const sectors = useMutation({
    mutationFn: () => api(`/datasets/${id}/sectors`, {}),
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ["state"] });
      navigate("/activity");
    },
  });
  const filings = useMutation({
    mutationFn: () => api(`/fundamentals/${id}`, {}),
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ["state"] });
      navigate("/activity");
    },
  });
  if (!available.length) return null;
  return (
    <section className="card market-data">
      <div className="card-header">
        <div>
          <span className="eyebrow">KEEP YOUR RESEARCH CURRENT</span>
          <h2>Update a saved dataset</h2>
          <p>Bring prices, sectors, membership and SEC filings forward.</p>
        </div>
      </div>
      <div className="card-body">
        <p>
          Update the latest snapshot with recent prices, corporate actions,
          membership, sector classifications and SEC filings. New members
          receive historical backfill. A new snapshot shares unchanged data with
          earlier snapshots. After completion, select the newest snapshot in
          Research.
        </p>
        <form
          className="form"
          onSubmit={(event) => {
            event.preventDefault();
            task.mutate();
          }}
        >
          <div className="snapshot-update-controls">
            <label>
              Dataset to update
              <select
                value={id}
                onChange={(event) => {
                  setSelected(event.target.value);
                  task.reset();
                  sectors.reset();
                }}
              >
                {available.map((dataset) => (
                  <option key={dataset.id} value={dataset.id}>
                    {snapshotLabel(dataset)}
                  </option>
                ))}
              </select>
            </label>
            <div className="form-action">
              <button
                className="button secondary"
                disabled={preparing || !id || task.isPending}
              >
                <RefreshCw size={16} />
                {preparing
                  ? "Preparing data…"
                  : task.isPending
                    ? "Queueing update…"
                    : "Update dataset"}
              </button>
            </div>
          </div>
        </form>
        {chosen && (
          <p className="field-hint">
            Currently through {chosen.end} ·{" "}
            {preparing
              ? "Checks are in progress and complete automatically"
              : chosen.metadata?.fundamentals
                ? "Market data + SEC filings"
                : chosen.metadata?.bundle_role === "prices"
                  ? "SEC download unfinished · Update completes it"
                  : "Legacy snapshot · SEC filings will be added"}
            . Earlier prices stay frozen. Reviewed missing merger terms can be
            added with source evidence; a full download revalidates older
            history.
          </p>
        )}
        {task.error && <Notice error>{task.error.message}</Notice>}
        <p className="field-hint">
          Update dataset already includes prices, sectors and SEC filings. No
          separate share-class refresh is needed for normal updates.
        </p>
        <details className="details">
          <summary>More refresh options</summary>
          <p>
            Use these only to retry a stage or refresh one input separately.
          </p>
          <div className="form-action">
            <button
              type="button"
              className="button secondary"
              disabled={preparing || !id || sectors.isPending || task.isPending}
              onClick={() => sectors.mutate()}
            >
              {sectors.isPending ? "Queueing sectors…" : "Refresh sectors"}
            </button>
          </div>
          <p className="field-hint">
            Sector information is included in every download and update. Refresh
            sectors alone reuses saved prices and filings in a new snapshot.
            Current or last-known labels are used where complete historical
            classifications are unavailable.
          </p>
          {sectors.error && <Notice error>{sectors.error.message}</Notice>}
          <div className="form-action">
            <button
              className="button secondary"
              disabled={preparing || filings.isPending || !id}
              onClick={() => filings.mutate()}
            >
              Refresh SEC filings & share classes
            </button>
          </div>
          <p className="field-hint">
            Recheck filing-specific share units in a new snapshot using saved
            prices. First-time verification reads historical SEC filings and can
            take longer; completed filing checks are reused on retries and
            updates. New or changed filings are checked again. Earlier snapshots
            and results stay available.
          </p>
          {filings.error && <Notice error>{filings.error.message}</Notice>}
        </details>
      </div>
    </section>
  );
}
