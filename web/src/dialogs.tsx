import { useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, LoaderCircle, Upload } from "lucide-react";
import { api } from "./api";
import { Modal, Notice } from "./components";
import type { State, Strategy } from "./types";

function afterWarmup(start: string, end: string) {
  const day = new Date(`${start}T12:00:00Z`);
  day.setUTCDate(day.getUTCDate() + 370);
  const candidate = day.toISOString().slice(0, 10);
  return candidate < end ? candidate : start;
}

export function TaskDialog({
  kind,
  state,
  initial,
  onClose,
  onQueued,
}: {
  kind: "review" | "backtest";
  state: State;
  initial?: string;
  onClose: () => void;
  onQueued: () => void;
}) {
  const [datasetId, setDatasetId] = useState(state.datasets[0]?.id ?? "");
  const [strategyId, setStrategyId] = useState(initial ?? "momentum");
  const dataset = state.datasets.find((row) => row.id === datasetId);
  const [start, setStart] = useState(
    dataset ? afterWarmup(dataset.start, dataset.end) : "",
  );
  const [end, setEnd] = useState(dataset?.end ?? "");
  const [capital, setCapital] = useState("100000");
  const client = useQueryClient();
  const task = useMutation({
    mutationFn: (payload: Record<string, string | null>) =>
      api(`/tasks/${kind}`, payload),
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ["state"] });
      onQueued();
      onClose();
    },
  });
  function changeDataset(id: string) {
    setDatasetId(id);
    const next = state.datasets.find((d) => d.id === id)!;
    setStart(afterWarmup(next.start, next.end));
    setEnd(next.end);
    task.reset();
  }
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const values = new FormData(event.currentTarget);
    task.mutate({
      dataset_id: String(values.get("dataset_id")),
      strategy_id: String(values.get("strategy_id")),
      start: kind === "backtest" ? String(values.get("start")) : null,
      end: kind === "backtest" ? String(values.get("end")) : null,
      capital: kind === "backtest" ? String(values.get("capital")) : "100000",
    });
  }
  return (
    <Modal
      open
      title={
        kind === "backtest"
          ? "Set up a backtest"
          : "Prepare an allocation review"
      }
      description={
        kind === "backtest"
          ? "Test a research idea using saved data. Nothing will be traded."
          : "Validate saved data, calculate signals, and build a read-only target allocation."
      }
      onClose={onClose}
    >
      <form onSubmit={submit} className="form">
        <label>
          Dataset
          <select
            name="dataset_id"
            value={datasetId}
            onChange={(e) => changeDataset(e.target.value)}
            required
          >
            <option value="" disabled>
              Choose a dataset
            </option>
            {state.datasets.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
                {d.kind === "synthetic" ? " · Synthetic" : ""}
              </option>
            ))}
          </select>
        </label>
        <label>
          Strategy
          <select
            name="strategy_id"
            value={strategyId}
            onChange={(e) => {
              setStrategyId(e.target.value);
              task.reset();
            }}
          >
            {state.strategies
              .filter((s) => s.implemented)
              .map((s) => (
                <option value={s.id} key={s.id}>
                  {s.name}
                </option>
              ))}
          </select>
        </label>
        {dataset?.kind === "synthetic" && (
          <Notice>
            Synthetic practice data — useful for learning the workflow, never
            evidence of strategy performance.
          </Notice>
        )}
        {kind === "backtest" && (
          <>
            <div className="form-row">
              <label>
                Start date
                <input
                  name="start"
                  aria-label="Start date"
                  type="date"
                  min={dataset?.start}
                  max={dataset?.end}
                  value={start}
                  onChange={(e) => setStart(e.target.value)}
                  required
                />
              </label>
              <label>
                End date
                <input
                  name="end"
                  aria-label="End date"
                  type="date"
                  min={start || dataset?.start}
                  max={dataset?.end}
                  value={end}
                  onChange={(e) => setEnd(e.target.value)}
                  required
                />
              </label>
            </div>
            <p className="field-hint">
              Signals need 253 earlier sessions. Dates default to leave warm-up
              history when available. Earlier periods can remain in cash.
            </p>
            <label>
              Starting capital · USD
              <input
                name="capital"
                type="number"
                min="100"
                max="1000000000"
                step="0.01"
                value={capital}
                onChange={(e) => setCapital(e.target.value)}
                required
              />
            </label>
          </>
        )}
        <details className="details">
          <summary>How this calculation works</summary>
          <p>
            Weekly decisions after the final session close; execution modeled at
            the following session open. Up to 25 stocks, 5% per stock, 25% per
            sector, at least 2% cash. When limits prevent investment, the
            remainder stays in cash.
          </p>
          <p>
            Backtests model 5 basis points of slippage and 1 basis point of fees
            per side. Cash earns 0%. These are research assumptions, not broker
            quotes.
          </p>
          {kind === "review" && (
            <p>
              This release validates imported data; it does not download a
              provider update. Data must include the latest completed session.
              This review cannot be approved for trading yet.
            </p>
          )}
        </details>
        {task.isError && <Notice error>{task.error.message}</Notice>}
        <div className="modal-actions">
          <button className="button secondary" type="button" onClick={onClose}>
            Cancel
          </button>
          <button
            className="button"
            disabled={!dataset || task.isPending}
            type="submit"
          >
            {task.isPending ? (
              <LoaderCircle className="spin" size={16} />
            ) : (
              <ArrowRight size={16} />
            )}
            {kind === "backtest" ? "Run backtest" : "Prepare review"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

export function ImportDialog({
  onClose,
  onImported,
}: {
  onClose: () => void;
  onImported: () => void;
}) {
  const [name, setName] = useState("");
  const [source, setSource] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [inputMode, setInputMode] = useState<"file" | "paste">("file");
  const [pasted, setPasted] = useState("");
  const [localError, setLocalError] = useState("");
  const client = useQueryClient();
  const mutation = useMutation({
    mutationFn: async (values: {
      name: string;
      source: string;
      csv?: string;
    }) => {
      if (inputMode === "file" && !file)
        throw new Error("Choose a CSV file first, or use Paste CSV.");
      if (file && inputMode === "file" && file.size > 16 * 1024 * 1024)
        throw new Error("Choose a CSV smaller than 16 MB.");
      return api<{ already_imported?: boolean }>("/datasets", {
        name: values.name,
        source: values.source,
        price_basis: "as_traded",
        csv: inputMode === "paste" ? values.csv : await file!.text(),
      });
    },
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ["state"] });
      onImported();
      onClose();
    },
  });
  return (
    <Modal
      open
      title="Import market data"
      description="Add an immutable dataset with a recorded source. Your file stays on this Mac."
      onClose={onClose}
    >
      <form
        className="form"
        onSubmit={(e) => {
          e.preventDefault();
          setLocalError("");
          if (!confirmed)
            setLocalError(
              "Confirm the as-traded price convention before importing.",
            );
          else {
            const values = new FormData(e.currentTarget);
            mutation.mutate({
              name: String(values.get("name")),
              source: String(values.get("source")),
              csv: String(values.get("csv") ?? ""),
            });
          }
        }}
      >
        <div className="import-guide">
          <strong>Start with the right price format</strong>
          <p>
            Use as-traded daily OHLC prices, not adjusted close or
            split-adjusted historical bars. A split is new shares per old share
            on its effective date. Dividends require both an ex-date amount and
            pay date.
          </p>
          <a className="text-link" href="/api/template.csv" download>
            Download CSV template <Upload size={14} />
          </a>
        </div>
        <label>
          Dataset name
          <input
            name="name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. My US stock watchlist"
            maxLength={100}
            required
          />
        </label>
        <label>
          Data source
          <input
            name="source"
            value={source}
            onChange={(e) => setSource(e.target.value)}
            placeholder="Provider, export date, and adjustment settings"
            maxLength={500}
            required
          />
        </label>
        <div
          className="input-method"
          role="group"
          aria-label="CSV input method"
        >
          <button
            type="button"
            aria-pressed={inputMode === "file"}
            onClick={() => {
              setInputMode("file");
              mutation.reset();
            }}
          >
            Choose file
          </button>
          <button
            type="button"
            aria-pressed={inputMode === "paste"}
            onClick={() => {
              setInputMode("paste");
              mutation.reset();
            }}
          >
            Paste CSV
          </button>
        </div>
        {inputMode === "file" ? (
          <label>
            CSV file
            <input
              type="file"
              accept=".csv,text/csv"
              onChange={(e) => {
                setFile(e.target.files?.[0] ?? null);
                mutation.reset();
              }}
            />
          </label>
        ) : (
          <label>
            CSV content
            <textarea
              name="csv"
              rows={6}
              value={pasted}
              onChange={(e) => setPasted(e.target.value)}
              placeholder="symbol,date,open,high,low,close,volume"
              required
            />
          </label>
        )}
        <p className="field-hint">
          Up to 100 symbols and 80,000 rows, 16 MB. Include SPY for benchmark
          comparisons. Missing historical sectors use a shared Unknown bucket.
        </p>
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={confirmed}
            onChange={(e) => setConfirmed(e.target.checked)}
            required
          />
          <span>
            I have verified these are as-traded prices and corporate actions are
            represented separately.
          </span>
        </label>
        {(mutation.isError || localError) && (
          <Notice error>{localError || mutation.error?.message}</Notice>
        )}
        <div className="modal-actions">
          <button type="button" className="button secondary" onClick={onClose}>
            Cancel
          </button>
          <button
            className="button"
            type="submit"
            disabled={mutation.isPending}
          >
            {mutation.isPending ? (
              <LoaderCircle size={16} className="spin" />
            ) : (
              <Upload size={16} />
            )}
            Import dataset
          </button>
        </div>
      </form>
    </Modal>
  );
}

export function StrategyDialog({
  strategy,
  onClose,
}: {
  strategy: Strategy;
  onClose: () => void;
}) {
  return (
    <Modal
      open
      title={strategy.name}
      description={strategy.description}
      onClose={onClose}
    >
      <div className="form">
        <div>
          <h3>Inputs</h3>
          <p>{strategy.inputs}</p>
        </div>
        <div>
          <h3>What can go wrong</h3>
          <p>{strategy.risk}</p>
        </div>
        {strategy.implemented ? (
          <>
            <div>
              <h3>Research definition · v{strategy.version}</h3>
              <p>
                {strategy.id === "momentum"
                  ? "Rank cumulative total returns from 252 sessions ago to 21 sessions ago, excluding the most recent month. Only positive scores qualify."
                  : "Rank the sample standard deviation of 252 daily total returns, lowest first. No volatility forecast or leverage is applied."}
              </p>
              <p>
                Both use a fixed stock list with complete warm-up history,
                equal-weight allocation subject to the same position, sector and
                cash limits.
              </p>
            </div>
            <Notice>
              Available for exploratory backtesting. No approval for paper or
              live trading has been granted.
            </Notice>
          </>
        ) : (
          <Notice>
            Planned for the fundamentals milestone. Historical filing
            availability, valuation denominators and coverage must be validated
            before this strategy can run.
          </Notice>
        )}
        <div className="modal-actions">
          <button className="button secondary" onClick={onClose}>
            Got it
          </button>
        </div>
      </div>
    </Modal>
  );
}
