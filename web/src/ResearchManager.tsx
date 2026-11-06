import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { LoaderCircle, Trash2 } from "lucide-react";
import { api } from "./api";
import { Modal, Notice } from "./components";

type Target = { kind: "dataset" | "result" | "protocol" | "job"; id: string };
type Item = Target & {
  category: string;
  name: string;
  detail: string;
  created_at: string;
};
type Preview = {
  items: (Target & { name: string })[];
  counts: Record<string, number>;
  blockers: string[];
  fingerprint: string;
  requested_count: number;
  locked_protocols: number;
};
const labels: Record<string, string> = {
  dataset: "dataset snapshot",
  result: "saved report",
  protocol: "validation protocol",
  job: "task record",
  trial: "validation trial",
};

export function DeletionDialog({
  targets,
  onClose,
  onDeleted,
}: {
  targets: Target[];
  onClose: () => void;
  onDeleted?: () => void;
}) {
  const client = useQueryClient();
  const [acknowledged, setAcknowledged] = useState(false);
  const preview = useQuery({
    queryKey: ["deletion-preview", targets],
    queryFn: () => api<Preview>("/research/deletion-preview", { targets }),
    staleTime: 0,
  });
  const remove = useMutation({
    mutationFn: () =>
      api<{ message: string }>("/research/delete", {
        targets,
        fingerprint: preview.data?.fingerprint,
      }),
    onSuccess: async () => {
      // Never leave a deleted report selected or cached in a comparison.
      for (const key of ["result", "review", "trial"])
        client.removeQueries({ queryKey: [key] });
      await Promise.all(
        ["state", "protocols", "research-library"].map((key) =>
          client.invalidateQueries({ queryKey: [key] }),
        ),
      );
      onDeleted?.();
      onClose();
    },
  });
  return (
    <Modal
      title="Delete saved research?"
      description="Review everything affected before permanently deleting. This cannot be undone."
      open
      onClose={() => !remove.isPending && onClose()}
    >
      <div className="form cleanup-confirm">
        {preview.isPending && (
          <p role="status">
            <LoaderCircle className="spin" size={16} /> Checking related
            records…
          </p>
        )}
        {preview.error && <Notice error>{preview.error.message}</Notice>}
        {preview.data && (
          <>
            <p className="field-hint">
              The following records will be deleted together so remaining
              research keeps its inputs and links.
            </p>
            <ul className="cleanup-counts">
              {Object.entries(preview.data.counts).map(([kind, count]) => (
                <li key={kind}>
                  <strong>{count}</strong> {labels[kind] ?? kind}
                  {count === 1 ? "" : "s"}
                </li>
              ))}
            </ul>
            <details className="details">
              <summary>
                See affected items ({preview.data.items.length})
              </summary>
              <ul className="cleanup-items">
                {preview.data.items.map((item) => (
                  <li key={`${item.kind}/${item.id}`}>
                    <strong>{item.name}</strong>
                    <small>
                      {labels[item.kind]} · {item.id.slice(0, 8)}
                    </small>
                  </li>
                ))}
              </ul>
            </details>
            {!!preview.data.locked_protocols && (
              <Notice>
                Deleting a locked protocol also retires its reserved final-test
                period. Previously attempted periods remain recorded as
                explored.
              </Notice>
            )}
            <p className="field-hint">
              Paper account history, orders and approvals are protected. A small
              record of attempted research dates remains so deletion cannot make
              a viewed test period appear unseen. Shared inputs still used
              elsewhere are retained.
            </p>
            {preview.data.blockers.map((message) => (
              <Notice error key={message}>
                {message}
              </Notice>
            ))}
            {!preview.data.blockers.length && (
              <label className="check-row">
                <input
                  type="checkbox"
                  checked={acknowledged}
                  onChange={(e) => setAcknowledged(e.target.checked)}
                />
                I understand these items and their listed related records will
                be permanently deleted.
              </label>
            )}
          </>
        )}
        {remove.error && (
          <Notice error>
            {remove.error.message}{" "}
            <button
              className="text-link"
              onClick={() => {
                setAcknowledged(false);
                remove.reset();
                void preview.refetch();
              }}
            >
              Refresh preview
            </button>
          </Notice>
        )}
        <div className="modal-actions">
          <button
            className="button secondary"
            disabled={remove.isPending}
            onClick={onClose}
          >
            Keep items
          </button>
          <button
            className="button danger"
            disabled={
              !preview.data ||
              !!preview.data.blockers.length ||
              !acknowledged ||
              remove.isPending ||
              preview.isFetching
            }
            onClick={() => remove.mutate()}
          >
            {remove.isPending ? "Deleting…" : "Delete permanently"}
          </button>
        </div>
      </div>
    </Modal>
  );
}

export function DeleteResearchButton({
  kind,
  id,
  name,
  onDeleted,
}: Target & { name: string; onDeleted?: () => void }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button
        className="icon-button cleanup-delete"
        title={`Delete ${name}`}
        aria-label={`Delete ${name}`}
        onClick={() => setOpen(true)}
      >
        <Trash2 size={16} />
      </button>
      {open && (
        <DeletionDialog
          targets={[{ kind, id }]}
          onClose={() => setOpen(false)}
          onDeleted={onDeleted}
        />
      )}
    </>
  );
}

export default function ResearchManager({
  category = "All research",
}: {
  category?: string;
}) {
  const [open, setOpen] = useState(false);
  const [filter, setFilter] = useState(category);
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [deleting, setDeleting] = useState<Target[] | null>(null);
  const [message, setMessage] = useState("");
  const library = useQuery({
    queryKey: ["research-library"],
    queryFn: () => api<{ items: Item[] }>("/research/library"),
    enabled: open,
  });
  const items = library.data?.items ?? [];
  const chosen = items.filter((item) =>
    selected.includes(`${item.kind}/${item.id}`),
  );
  const visible = useMemo(
    () =>
      items.filter(
        (item) =>
          (filter === "All research" || item.category === filter) &&
          `${item.name} ${item.detail} ${item.id}`
            .toLowerCase()
            .includes(search.toLowerCase()),
      ),
    [items, filter, search],
  );
  const key = (item: Target) => `${item.kind}/${item.id}`;
  function toggle(item: Item) {
    setSelected((ids) =>
      ids.includes(key(item))
        ? ids.filter((id) => id !== key(item))
        : [...ids, key(item)],
    );
  }
  return (
    <>
      <button
        className="button secondary"
        onClick={() => {
          setOpen(true);
          setMessage("");
        }}
      >
        <Trash2 size={16} />
        Manage saved research
      </button>
      {open && (
        <Modal
          title="Manage saved research"
          description="Find old research and data, then review a deletion preview. Nothing is deleted until you confirm."
          open
          onClose={() => setOpen(false)}
        >
          <div className="form cleanup-manager">
            <div className="form-row">
              <label>
                Show
                <select
                  value={filter}
                  onChange={(e) => setFilter(e.target.value)}
                >
                  {[
                    "All research",
                    "Backtests",
                    "Allocation reviews",
                    "Validation protocols",
                    "Validation runs",
                    "Datasets",
                    "Task history",
                  ].map((v) => (
                    <option key={v}>{v}</option>
                  ))}
                </select>
              </label>
              <label>
                Search saved items
                <input
                  type="search"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Name, date or dataset"
                />
              </label>
            </div>
            {message && (
              <p role="status" className="cleanup-success">
                {message}
              </p>
            )}
            {library.isPending ? (
              <p role="status">Loading saved research…</p>
            ) : library.error ? (
              <Notice error>{library.error.message}</Notice>
            ) : (
              <>
                {!!visible.length && (
                  <label className="check-row">
                    <input
                      type="checkbox"
                      aria-label="Select all shown items"
                      checked={visible.every((item) =>
                        selected.includes(key(item)),
                      )}
                      onChange={(e) =>
                        setSelected((old) =>
                          e.target.checked
                            ? [...new Set([...old, ...visible.map(key)])]
                            : old.filter(
                                (id) =>
                                  !visible.some((item) => key(item) === id),
                              ),
                        )
                      }
                    />
                    Select all {visible.length} shown items
                  </label>
                )}
                <div className="cleanup-library">
                  {visible.map((item) => (
                    <label className="cleanup-row" key={key(item)}>
                      <input
                        type="checkbox"
                        checked={selected.includes(key(item))}
                        onChange={() => toggle(item)}
                        aria-label={`Select ${item.name} ${item.id.slice(0, 8)}`}
                      />
                      <span>
                        <strong>{item.name}</strong>
                        <small>
                          {item.category} ·{" "}
                          {new Date(item.created_at).toLocaleString()}
                        </small>
                        <small>{item.detail}</small>
                      </span>
                    </label>
                  ))}
                  {!visible.length && <p>No saved items match this view.</p>}
                </div>
              </>
            )}
            <p className="field-hint">
              Dataset deletion may include dependent versions and research. The
              next screen lists every affected record. Trading records cannot be
              deleted here.
            </p>
            <div className="modal-actions">
              <span>{chosen.length} selected</span>
              <button
                className="button secondary"
                onClick={() => setOpen(false)}
              >
                Done
              </button>
              <button
                className="button danger"
                disabled={!chosen.length}
                onClick={() =>
                  setDeleting(chosen.map(({ kind, id }) => ({ kind, id })))
                }
              >
                Review deletion
              </button>
            </div>
            {deleting && (
              <DeletionDialog
                targets={deleting}
                onClose={() => setDeleting(null)}
                onDeleted={() => {
                  setSelected([]);
                  setMessage("Selected research deleted.");
                }}
              />
            )}
          </div>
        </Modal>
      )}
    </>
  );
}
