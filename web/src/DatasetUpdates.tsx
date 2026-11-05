import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { RefreshCw } from "lucide-react";
import { api } from "./api";
import { snapshotGroups, snapshotLabel } from "./snapshots";
import { Notice } from "./components";
import type { Dataset } from "./types";

export default function DatasetUpdates({ datasets }: { datasets: Dataset[] }) {
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
  if (!available.length) return null;
  return (
    <section className="card market-data">
      <div className="card-header">
        <div>
          <span className="eyebrow">KEEP YOUR RESEARCH CURRENT</span>
          <h2>Update a saved dataset</h2>
          <p>Bring prices, membership and SEC filings forward.</p>
        </div>
      </div>
      <div className="card-body">
        <p>
          Update the latest snapshot with recent prices, corporate actions,
          membership and SEC filings. New members receive historical backfill. A
          new snapshot shares unchanged data with earlier snapshots. After
          completion, select the newest snapshot in Research.
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
                disabled={!id || task.isPending}
              >
                <RefreshCw size={16} />
                {task.isPending ? "Queueing update…" : "Update dataset"}
              </button>
            </div>
          </div>
        </form>
        {chosen && (
          <p className="field-hint">
            Currently through {chosen.end} ·{" "}
            {chosen.metadata?.fundamentals
              ? "Market data + SEC filings"
              : chosen.metadata?.bundle_role === "prices"
                ? "SEC download incomplete · complete it below"
                : "Legacy snapshot · SEC filings will be added"}
            . Older prices and actions outside the recent 10-day refresh window
            stay frozen; a full download revalidates older history.
          </p>
        )}
        {task.error && <Notice error>{task.error.message}</Notice>}
      </div>
    </section>
  );
}
