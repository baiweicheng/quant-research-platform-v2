import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { RefreshCw } from "lucide-react";
import { api, datasetLabel } from "./api";
import { Notice } from "./components";
import type { Dataset } from "./types";

export default function DatasetUpdates({ datasets }: { datasets: Dataset[] }) {
  const available = datasets.filter((d) => d.metadata?.provider === "alpaca");
  const [selected, setSelected] = useState("");
  const id = selected || available[0]?.id || "";
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
          <p>Bring prices, membership and existing SEC coverage forward.</p>
        </div>
      </div>
      <div className="card-body">
        <p>
          Refresh recent prices and actions, backfill new members, and refresh
          filings when the selected dataset includes SEC data. A new snapshot
          shares unchanged data with earlier snapshots. After completion, select
          the newest snapshot in Research.
        </p>
        <form
          className="form"
          onSubmit={(event) => {
            event.preventDefault();
            task.mutate();
          }}
        >
          <div className="form-grid">
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
                    {datasetLabel(dataset, available)}
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
              ? "Prices + SEC filings"
              : "Prices only"}
            . Older prices and actions outside the recent 10-day refresh window
            stay frozen; a full download revalidates older history.
          </p>
        )}
        {task.error && <Notice error>{task.error.message}</Notice>}
      </div>
    </section>
  );
}
