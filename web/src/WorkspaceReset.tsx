import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";
import { DisclosureCard, Modal, Notice } from "./components";

const confirmationText = "RESET WORKSPACE";
const labels = {
  datasets: "Dataset snapshots",
  memberships: "Membership captures",
  results: "Saved results, including backtests",
  protocols: "Validation protocols",
  trials: "Validation trials",
  jobs: "Research task records",
  observations: "Source captures",
  content_blobs: "Shared data blocks",
  parsed_filings: "Parsed filing records",
  preferences: "Annual filing cache entries",
};
type Preview = {
  fingerprint: string;
  counts: Record<string, number>;
  retained_paper_inputs: { datasets: number; memberships: number };
  blockers: string[];
  has_changes: boolean;
};

function ResetDialog({
  onClose,
  onReset,
}: {
  onClose: () => void;
  onReset: (message: string) => void;
}) {
  const [confirmation, setConfirmation] = useState("");
  const [confirmedFingerprint, setConfirmedFingerprint] = useState("");
  const client = useQueryClient();
  const preview = useQuery({
    queryKey: ["workspace-reset-preview"],
    queryFn: () => api<Preview>("/workspace/reset-preview"),
    staleTime: 0,
  });
  const current = preview.data;
  const reset = useMutation({
    mutationFn: (request: { fingerprint: string; confirmation: string }) =>
      api<{ message: string }>("/workspace/reset", request),
    onSuccess: async ({ message }) => {
      for (const key of ["result", "review", "trial", "decision", "sectors"])
        client.removeQueries({ queryKey: [key] });
      await Promise.all(
        ["state", "providers", "protocols", "research-library"].map((key) =>
          client.invalidateQueries({ queryKey: [key] }),
        ),
      );
      onReset(message);
    },
  });
  const ready =
    !!current?.has_changes &&
    !current.blockers.length &&
    !preview.isFetching &&
    !preview.error &&
    !reset.error &&
    confirmation === confirmationText &&
    confirmedFingerprint === current.fingerprint;
  function refresh() {
    setConfirmation("");
    setConfirmedFingerprint("");
    reset.reset();
    void preview.refetch();
  }
  return (
    <Modal
      title="Reset workspace?"
      description="Permanently delete downloaded and imported research data, backtests, allocation reviews, validation runs, research task history and caches."
      open
      onClose={() => !reset.isPending && onClose()}
    >
      <div className="form cleanup-confirm">
        <p>
          Paper trading history, orders, approvals, connection settings and your
          saved watchlist are kept. A small record of previously attempted
          research dates remains so explored periods stay marked as seen.
        </p>
        {preview.isPending && <p role="status">Checking workspace data…</p>}
        {preview.error && <Notice error>{preview.error.message}</Notice>}
        {current && (
          <>
            {current.has_changes ? (
              <ul className="cleanup-counts" aria-label="Records to remove">
                {Object.entries(labels).map(([kind, label]) => {
                  const count = current.counts[kind];
                  return count > 0 ? (
                    <li key={kind}>
                      <strong>{count.toLocaleString()}</strong> {label}
                    </li>
                  ) : null;
                })}
              </ul>
            ) : (
              <p>The research workspace is already empty.</p>
            )}
            {!!(
              current.retained_paper_inputs.datasets ||
              current.retained_paper_inputs.memberships
            ) && (
              <p>
                Paper history retains {current.retained_paper_inputs.datasets}{" "}
                dataset snapshots and{" "}
                {current.retained_paper_inputs.memberships} membership captures.
                They will be kept with the paper records and removed from
                research views.
              </p>
            )}
            {current.blockers.map((reason) => (
              <Notice error key={reason}>
                {reason}
              </Notice>
            ))}
            {current.has_changes && !current.blockers.length && (
              <label>
                Type <strong>{confirmationText}</strong> to confirm
                <input
                  value={confirmation}
                  onChange={(event) => {
                    setConfirmation(event.target.value);
                    setConfirmedFingerprint(current.fingerprint);
                  }}
                  autoComplete="off"
                  spellCheck={false}
                  disabled={reset.isPending || preview.isFetching}
                />
              </label>
            )}
          </>
        )}
        <p className="field-hint">This cannot be undone.</p>
        {reset.error && <Notice error>{reset.error.message}</Notice>}
        {(preview.error ||
          reset.error ||
          !!current?.blockers.length ||
          (!!confirmedFingerprint &&
            confirmedFingerprint !== current?.fingerprint)) && (
          <button
            className="text-link"
            onClick={refresh}
            disabled={preview.isFetching}
          >
            Refresh preview
          </button>
        )}
        <div className="modal-actions">
          <button
            className="button secondary"
            onClick={onClose}
            disabled={reset.isPending}
          >
            Cancel
          </button>
          <button
            className="button danger"
            disabled={!ready || reset.isPending}
            onClick={() =>
              current &&
              reset.mutate({ fingerprint: current.fingerprint, confirmation })
            }
          >
            {reset.isPending ? "Resetting…" : "Reset permanently"}
          </button>
        </div>
      </div>
    </Modal>
  );
}

export default function WorkspaceReset() {
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState("");
  return (
    <DisclosureCard title="Workspace maintenance">
      <div className="card-body">
        <p>
          Clear saved research and datasets while keeping paper trading history.
        </p>
        <button className="button secondary" onClick={() => setOpen(true)}>
          Reset workspace
        </button>
      </div>
      {message && (
        <p className="card-body" role="status">
          {message}
        </p>
      )}
      {open && (
        <ResetDialog
          onClose={() => setOpen(false)}
          onReset={(value) => {
            setMessage(value);
            setOpen(false);
          }}
        />
      )}
    </DisclosureCard>
  );
}
