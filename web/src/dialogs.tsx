import { useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, LoaderCircle } from "lucide-react";
import { api } from "./api";
import {
  snapshotGroups,
  SnapshotOptions,
  researchSnapshots,
} from "./snapshots";
import { Modal, Notice } from "./components";
import type { State, Strategy } from "./types";

export function afterWarmup(start: string, end: string) {
  const day = new Date(`${start}T12:00:00Z`);
  if (start.slice(5) <= "01-07")
    day.setUTCFullYear(day.getUTCFullYear() + 1, 0, 1);
  else day.setUTCDate(day.getUTCDate() + 370);
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
  const initialRecipe = state.strategies.find((s) => s.id === initial);
  const [datasetId, setDatasetId] = useState(
    (
      snapshotGroups(researchSnapshots(state.datasets)).latest.find((d) =>
        initialRecipe?.requires_periodic_income
          ? !!d.metadata?.fundamentals?.has_periodic_captures
          : initialRecipe?.requires_annual_income
            ? !!d.metadata?.fundamentals?.annual_income_count
            : !["quality", "quality_value", "value_momentum"].includes(
                initial || "",
              ) || !!d.metadata?.fundamentals?.record_count,
      ) || snapshotGroups(researchSnapshots(state.datasets)).latest[0]
    )?.id ?? "",
  );
  const [strategyId, setStrategyId] = useState(initial ?? "momentum");
  const [strategyIds, setStrategyIds] = useState([initial ?? "momentum"]);
  const [strategySearch, setStrategySearch] = useState("");
  const selectedStrategies = kind === "backtest" ? strategyIds : [strategyId];
  const availableStrategies = state.strategies.filter((s) => s.implemented);
  const visibleStrategies = availableStrategies.filter((s) =>
    `${s.name} ${s.category}`
      .toLowerCase()
      .includes(strategySearch.toLowerCase()),
  );
  const dataset = state.datasets.find((row) => row.id === datasetId);
  const needsFundamentals = ["quality", "quality_value", "value_momentum"].some(
    (id) => selectedStrategies.includes(id),
  );
  const missingFundamentals =
    needsFundamentals && !dataset?.metadata?.fundamentals?.record_count;
  const requiresAnnualIncome = availableStrategies.some(
    (s) => s.requires_annual_income && selectedStrategies.includes(s.id),
  );
  const missingAnnualIncome =
    requiresAnnualIncome &&
    !dataset?.metadata?.fundamentals?.annual_income_count;
  const missingPeriodicIncome =
    availableStrategies.some(
      (s) => s.requires_periodic_income && selectedStrategies.includes(s.id),
    ) && !dataset?.metadata?.fundamentals?.has_periodic_captures;
  const legacyClasses =
    ["quality_value", "value_momentum"].some((id) =>
      selectedStrategies.includes(id),
    ) && dataset?.metadata?.fundamentals?.normalizer === "annual-us-gaap-v1";
  const lightweightEps =
    ["quality_value", "value_momentum"].some((id) =>
      selectedStrategies.includes(id),
    ) && !!dataset?.metadata?.fundamentals?.eps_policy;
  const olderEps =
    lightweightEps &&
    dataset?.metadata?.fundamentals?.eps_policy !== "structured-eps-v2";
  const [start, setStart] = useState(
    dataset ? afterWarmup(dataset.start, dataset.end) : "",
  );
  const [end, setEnd] = useState(dataset?.end ?? "");
  const [capital, setCapital] = useState("100000");
  const client = useQueryClient();
  const task = useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      api(
        kind === "backtest" && Array.isArray(payload.strategy_ids)
          ? "/tasks/backtests"
          : `/tasks/${kind}`,
        payload,
      ),
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
    const selection =
      kind === "backtest" ? strategyIds : [String(values.get("strategy_id"))];
    if (!selection.length) return;
    task.mutate({
      dataset_id: String(values.get("dataset_id")),
      ...(selection.length > 1
        ? { strategy_ids: selection }
        : { strategy_id: selection[0] }),
      start: kind === "backtest" ? String(values.get("start")) : null,
      end: kind === "backtest" ? String(values.get("end")) : null,
      capital: kind === "backtest" ? String(values.get("capital")) : "100000",
      dividend_model: String(values.get("dividend_model") || "ex_date"),
      coverage_mode: String(values.get("coverage_mode") || "strict"),
      cost_profile: String(values.get("cost_profile") || "standard"),
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
            <SnapshotOptions datasets={state.datasets} />
          </select>
        </label>
        {kind === "backtest" ? (
          <fieldset className="strategy-picker" disabled={task.isPending}>
            <legend>Strategies</legend>
            <div className="strategy-picker-actions">
              <span>{strategyIds.length} selected</span>
              <div className="inline">
                <button
                  type="button"
                  className="text-link"
                  onClick={() => {
                    setStrategyIds((ids) => [
                      ...new Set([
                        ...ids,
                        ...visibleStrategies.map((s) => s.id),
                      ]),
                    ]);
                    task.reset();
                  }}
                >
                  {strategySearch ? "Select matches" : "Select all"}
                </button>
                <button
                  type="button"
                  className="text-link"
                  disabled={!strategyIds.length}
                  onClick={() => {
                    setStrategyIds([]);
                    task.reset();
                  }}
                >
                  Clear
                </button>
              </div>
            </div>
            {availableStrategies.length > 8 && (
              <input
                type="search"
                aria-label="Find strategies"
                placeholder="Find strategies"
                value={strategySearch}
                onChange={(e) => setStrategySearch(e.target.value)}
              />
            )}
            <div
              className={`strategy-picker-list${availableStrategies.length > 8 ? " scrollable" : ""}`}
            >
              {visibleStrategies.map((s) => (
                <label className="checkbox-label" key={s.id}>
                  <input
                    type="checkbox"
                    name="strategy_id"
                    value={s.id}
                    aria-label={s.name}
                    checked={strategyIds.includes(s.id)}
                    onChange={(e) => {
                      setStrategyIds((ids) =>
                        e.target.checked
                          ? [...ids, s.id]
                          : ids.filter((id) => id !== s.id),
                      );
                      task.reset();
                    }}
                  />
                  <span>
                    {s.name}
                    <small>
                      {s.category}
                      {s.frequency === "monthly" && " · Month-end"}
                    </small>
                  </span>
                </label>
              ))}
              {!visibleStrategies.length && (
                <p className="field-hint">No matching strategies.</p>
              )}
            </div>
            <p className="field-hint">
              Each selected strategy gets its own result using the same data,
              dates and assumptions below.
            </p>
          </fieldset>
        ) : (
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
              {availableStrategies.map((s) => (
                <option value={s.id} key={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </label>
        )}
        {!dataset &&
          state.datasets.some((d) => d.metadata?.bundle_role === "prices") && (
            <Notice>
              The download's SEC stage is still unfinished. Follow Activity, or
              use Complete SEC download in Data before running research.
            </Notice>
          )}
        {dataset?.kind === "synthetic" && (
          <Notice>
            Synthetic practice data — useful for learning the workflow, never
            evidence of strategy performance.
          </Notice>
        )}
        {lightweightEps && (
          <p className="field-hint">
            EPS uses lightweight share-class assumptions. Known unequal-share
            earnings need a verified share-class amount.
          </p>
        )}
        {olderEps && (
          <Notice>
            In Data, update this dataset to load the latest filing checks and
            recover additional share-class earnings.
          </Notice>
        )}
        {legacyClasses && (
          <Notice>
            This snapshot retains the legacy EPS share-class screen. In Data,
            use Refresh SEC financial data, then choose the new snapshot to
            apply the current EPS policy. Earlier saved inputs stay unchanged.
          </Notice>
        )}
        {missingFundamentals && (
          <Notice>
            Select a downloaded market and SEC snapshot. This selection needs
            filing-dated statements as well as prices.
          </Notice>
        )}
        {missingPeriodicIncome && (
          <Notice>
            Choose a completed market and SEC snapshot with saved companyfacts
            for this weekly earnings strategy.
          </Notice>
        )}
        {missingAnnualIncome && (
          <Notice>
            Add or refresh SEC financials in Data, then select the updated
            snapshot with comparable annual net income.
          </Notice>
        )}
        {kind === "backtest" && requiresAnnualIncome && (
          <p className="field-hint">
            Profitable Liquidity Leaders rebalances at month end.
          </p>
        )}
        {dataset?.kind === "imported" && (
          <Notice>
            {dataset.metadata?.sector_classification
              ? "The 25% sector cap uses dated classifications for reviewed S&P revisions. Other captured classifications may reflect later information. Concentrated selections can leave more cash than the 2% minimum reserve."
              : "This snapshot has no sector coverage audit. Refresh sectors in Data for a new classified snapshot; unresolved labels can leave substantial cash under the 25% sector cap."}
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
              {selectedStrategies.length > 0 &&
              selectedStrategies.every((id) =>
                ["quality", "quality_value"].includes(id),
              )
                ? "Signals need 20 earlier price sessions and an available annual filing."
                : "Signals need 253 earlier price sessions."}{" "}
              Dates default to leave warm-up history when available. Earlier
              periods can remain in cash.
            </p>
            <ResearchCoverageChoice />
            <label>
              Dividend accounting
              <select name="dividend_model" defaultValue="ex_date">
                <option value="ex_date">
                  Total-return research · reinvest on ex-date
                </option>
                <option value="pay_date">
                  Cash-flow simulation · verified payment dates
                </option>
              </select>
            </label>
            <p className="field-hint">
              Total-return research reinvests distributions at the ex-date
              close. Cash-flow simulation waits for verified payment dates and
              can require additional historical data.
            </p>
            <label>
              Trading costs
              <select name="cost_profile" defaultValue="standard">
                <option value="standard">Standard</option>
                <option value="higher">Higher costs</option>
              </select>
            </label>
            <p className="field-hint">
              Standard uses 5 bps of base slippage per side. Higher costs uses
              15 bps. Both add a 1 bp fee allowance and a liquidity adjustment.
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
            Backtests use each strategy's weekly or month-end decision schedule
            and model execution at the following session open. Up to 25 stocks,
            5% per stock, 25% per sector, at least 2% cash. When limits prevent
            investment, the remainder stays in cash.
          </p>
          <p>
            Backtests estimate the liquidity adjustment from order size and
            earlier daily trading volume. Fees are a research allowance. Cash
            earns 0%.
          </p>
          {kind === "review" && (
            <p>
              This review uses saved inputs. Update prices and any required SEC
              fundamentals in Data first. Prices must include the latest
              completed session. This review cannot be approved for trading yet.
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
            disabled={
              !dataset ||
              !selectedStrategies.length ||
              missingFundamentals ||
              missingPeriodicIncome ||
              missingAnnualIncome ||
              task.isPending
            }
            type="submit"
          >
            {task.isPending ? (
              <LoaderCircle className="spin" size={16} />
            ) : (
              <ArrowRight size={16} />
            )}
            {kind === "backtest"
              ? strategyIds.length > 1
                ? `Run ${strategyIds.length} backtests`
                : "Run backtest"
              : "Prepare review"}
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
                {strategy.definition ||
                  (strategy.id === "momentum"
                    ? "Rank cumulative total returns from 252 sessions ago to 21 sessions ago, excluding the most recent month. Only positive scores qualify."
                    : "Rank the sample standard deviation of 252 daily total returns, lowest first. No volatility forecast or leverage is applied.")}
              </p>
              <p>
                Stocks need complete signal history. Allocation follows the
                position, sector and cash limits.
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

export function ResearchCoverageChoice() {
  return (
    <>
      <label>
        Data coverage policy
        <select name="coverage_mode" defaultValue="coverage_limited">
          <option value="coverage_limited">
            Coverage-limited research · exclusions disclosed
          </option>
          <option value="strict">
            Strict coverage · require complete inputs
          </option>
        </select>
      </label>
      <p className="field-hint">
        Coverage-limited research excludes stocks with missing or unverified
        inputs during possible holding periods. Every exclusion is saved. This
        can introduce survivorship and selection bias; results do not represent
        the complete S&P 500.
      </p>
    </>
  );
}
