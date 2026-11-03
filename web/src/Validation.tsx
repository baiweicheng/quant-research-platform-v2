import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, download, percent } from "./api";
import { Badge, Notice } from "./components";
import { RunDetail } from "./Research";
import type { Metrics, Period, Run, State } from "./types";

type Protocol = {
  id: string;
  name: string;
  hypothesis: string;
  dataset_name: string;
  strategy: { name: string; version: string };
  start: string;
  development_end: string;
  holdout_start: string;
  end: string;
  holdout_state: string;
  holdout_label: string;
  prior_exposures: string[];
  fingerprint: string;
};
type Trial = {
  id: string;
  protocol_id: string;
  job_id: string;
  label: string;
  phase: string;
  state: string;
  start: string;
  end: string;
  metrics?: Metrics;
  trade_count?: number;
  error?: string;
};
type Registry = {
  protocols: Protocol[];
  trials: Trial[];
  workspace_attempts: number;
};

function defaults(start: string, end: string) {
  const a = new Date(`${start}T12:00:00Z`);
  a.setUTCDate(a.getUTCDate() + 370);
  const b = new Date(`${end}T12:00:00Z`);
  b.setUTCDate(b.getUTCDate() - 180);
  return {
    start: a.toISOString().slice(0, 10),
    split: b.toISOString().slice(0, 10),
  };
}
export default function Validation({ state }: { state: State }) {
  const client = useQueryClient();
  const registry = useQuery({
    queryKey: ["protocols"],
    queryFn: () => api<Registry>("/research/protocols"),
    refetchInterval: 2500,
  });
  const [datasetId, setDataset] = useState(state.datasets[0]?.id ?? "");
  const ds = state.datasets.find((d) => d.id === datasetId);
  const [selected, setSelected] = useState("");
  const [trialId, setTrial] = useState("");
  const [period, setPeriod] = useState<Period>("All");
  const [acknowledge, setAcknowledge] = useState(false);
  const protocol =
    registry.data?.protocols.find((p) => p.id === selected) ??
    registry.data?.protocols[0];
  const trials =
    registry.data?.trials.filter((t) => t.protocol_id === protocol?.id) ?? [];
  const result = useQuery({
    queryKey: ["trial", trialId],
    queryFn: () => api<Run>(`/research/trials/${trialId}`),
    enabled: !!trialId,
  });
  const create = useMutation({
    mutationFn: (body: unknown) => api<Protocol>("/research/protocols", body),
    onSuccess: async (p) => {
      setSelected(p.id);
      await client.invalidateQueries({ queryKey: ["protocols"] });
    },
  });
  const evaluate = useMutation({
    mutationFn: (phase: string) =>
      api(`/research/protocols/${protocol?.id}/evaluate`, {
        phase,
        acknowledge,
      }),
    onSuccess: async () => {
      setAcknowledge(false);
      await Promise.all([
        client.invalidateQueries({ queryKey: ["protocols"] }),
        client.invalidateQueries({ queryKey: ["state"] }),
      ]);
    },
  });
  const retire = useMutation({
    mutationFn: () => api(`/research/protocols/${protocol?.id}/retire`, {}),
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ["protocols"] });
    },
  });
  function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const values = Object.fromEntries(new FormData(e.currentTarget));
    create.mutate({ ...values, capital: "100000" });
  }
  return (
    <>
      <section className="card">
        <div className="card-header">
          <div>
            <span className="eyebrow">RESEARCH VALIDATION</span>
            <h2>Separate discovery from confirmation.</h2>
            <p>
              Freeze one recipe, test chronological windows, then release a
              final period once.
            </p>
          </div>
          <Badge>
            {registry.data?.workspace_attempts ?? 0} workspace attempts
          </Badge>
        </div>
        <div className="card-body">
          <Notice>
            Fixed-list history remains exploratory. Validation cannot repair
            missing departed stocks or prove profitability. An already viewed
            period is labelled as explored. Tests outside this workspace are
            unknown.
          </Notice>
          <details className="details" open={!registry.data?.protocols.length}>
            <summary>Create a frozen research protocol</summary>
            <form className="form" onSubmit={submit} key={datasetId}>
              <label>
                Protocol name
                <input
                  name="name"
                  required
                  maxLength={100}
                  placeholder="Momentum robustness review"
                />
              </label>
              <label>
                Research hypothesis
                <textarea
                  name="hypothesis"
                  required
                  minLength={10}
                  maxLength={2000}
                  placeholder="Write what you expect and what would make you reject the idea before seeing the final test."
                />
              </label>
              <label>
                Dataset
                <select
                  name="dataset_id"
                  value={datasetId}
                  onChange={(e) => setDataset(e.target.value)}
                  required
                >
                  <option value="" disabled>
                    Choose saved data
                  </option>
                  {state.datasets.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Strategy
                <select name="strategy_id">
                  {state.strategies.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name} · v{s.version}
                    </option>
                  ))}
                </select>
              </label>
              <div className="form-row">
                <label>
                  Development start
                  <input
                    name="start"
                    type="date"
                    required
                    defaultValue={ds ? defaults(ds.start, ds.end).start : ""}
                  />
                </label>
                <label>
                  Final test starts
                  <input
                    name="holdout_start"
                    type="date"
                    required
                    defaultValue={ds ? defaults(ds.start, ds.end).split : ""}
                  />
                </label>
                <label>
                  Final test ends
                  <input
                    name="end"
                    type="date"
                    required
                    defaultValue={ds?.end}
                  />
                </label>
              </div>
              <p className="field-hint">
                At least 252 development sessions and 63 final-test sessions,
                plus earlier warm-up history. Default policy: 25 positions, 5%
                stock cap, 25% sector cap, 2% cash. Research policy only.
              </p>
              <button className="button" disabled={create.isPending || !ds}>
                {create.isPending ? "Freezing…" : "Freeze protocol"}
              </button>
              {create.error && <Notice error>{create.error.message}</Notice>}
            </form>
          </details>
        </div>
      </section>
      {registry.error && <Notice error>{registry.error.message}</Notice>}
      {protocol && (
        <section className="card">
          <div className="card-header">
            <div>
              <h2>Your validation record</h2>
              <p>All attempts and failed trials remain visible.</p>
            </div>
            <button
              className="button small secondary"
              onClick={() =>
                download(`protocol-${protocol.id}.json`, { protocol, trials })
              }
            >
              Export protocol & registry
            </button>
          </div>
          <div className="card-body">
            <label className="review-select">
              Frozen protocol
              <select
                value={protocol.id}
                onChange={(e) => {
                  setSelected(e.target.value);
                  setTrial("");
                  setAcknowledge(false);
                  evaluate.reset();
                }}
              >
                {registry.data?.protocols.map((p) => (
                  <option value={p.id} key={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </label>
            <p>
              <strong>
                {protocol.strategy.name} v{protocol.strategy.version}
              </strong>{" "}
              · {protocol.dataset_name}
            </p>
            <p>{protocol.hypothesis}</p>
            <p>
              Development: {protocol.start} – {protocol.development_end}
              <br />
              Final test: {protocol.holdout_start} – {protocol.end}
            </p>
            <Notice>
              {protocol.holdout_label}. {protocol.prior_exposures.length} prior
              overlapping attempts recorded. Final test:{" "}
              {protocol.holdout_state}.
            </Notice>
            <p>
              Development includes the baseline, three nonoverlapping forward
              windows, higher trading costs, a 3% stock cap, 15 positions and
              monthly rebalancing. Each window starts with cash; prior
              observations supply signal warm-up. The recipe stays fixed; there
              is no fitted optimizer or combined out-of-sample return.
            </p>
            <div className="validation-actions">
              <button
                className="button secondary"
                disabled={
                  evaluate.isPending || protocol.holdout_state !== "locked"
                }
                onClick={() => evaluate.mutate("development")}
              >
                Run development validation
              </button>
              {protocol.holdout_state === "locked" && (
                <>
                  <label className="check-label">
                    <input
                      type="checkbox"
                      checked={acknowledge}
                      onChange={(e) => setAcknowledge(e.target.checked)}
                    />
                    I have finished development. Release consumes the final
                    test, including a failed attempt.
                  </label>
                  <button
                    className="button"
                    disabled={!acknowledge || evaluate.isPending}
                    onClick={() => evaluate.mutate("holdout")}
                  >
                    Release final test once
                  </button>
                </>
              )}
            </div>
            {evaluate.error && <Notice error>{evaluate.error.message}</Notice>}
            {evaluate.isSuccess && (
              <Notice>
                Evaluation queued. Progress is saved in Activity; trials appear
                below as they finish.
              </Notice>
            )}
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Trial</th>
                    <th>Dates</th>
                    <th>Status</th>
                    <th>Return</th>
                    <th>vs SPY</th>
                    <th>Drawdown</th>
                    <th>Fills</th>
                    <th>Review</th>
                  </tr>
                </thead>
                <tbody>
                  {trials.map((t) => (
                    <tr key={t.id}>
                      <td>
                        {t.label}
                        <small>{t.phase}</small>
                      </td>
                      <td>
                        {t.start} – {t.end}
                      </td>
                      <td>
                        {t.state}
                        {t.error && <small>{t.error}</small>}
                      </td>
                      <td>{percent(t.metrics?.return, true)}</td>
                      <td>{percent(t.metrics?.difference, true)}</td>
                      <td>{percent(t.metrics?.drawdown)}</td>
                      <td>{t.trade_count ?? "—"}</td>
                      <td>
                        {t.state === "complete" && (
                          <button
                            className="button small secondary"
                            onClick={() => {
                              setTrial(t.id);
                              setPeriod("All");
                            }}
                          >
                            Inspect trial
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="field-hint">
              Trial counts expose repeated searching; no statistical
              significance or multiple-testing correction is claimed. Failure to
              trade is not evidence of robustness. Final-test results never
              activate a strategy.
            </p>
            {protocol.holdout_state === "locked" && (
              <button
                className="text-link"
                disabled={retire.isPending}
                onClick={() => retire.mutate()}
              >
                Retire protocol and lift its date reservation
              </button>
            )}
            {retire.error && <Notice error>{retire.error.message}</Notice>}
            <p className="digest">
              Protocol fingerprint: {protocol.fingerprint}
            </p>
          </div>
        </section>
      )}
      {result.error && <Notice error>{result.error.message}</Notice>}
      {result.data && (
        <RunDetail run={result.data} period={period} setPeriod={setPeriod} />
      )}
    </>
  );
}
