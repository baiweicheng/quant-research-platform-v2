import {
  render,
  screen,
  fireEvent,
  act,
  waitFor,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, expect, it, vi } from "vitest";
import PaperWorkspace from "./Paper";
import type { State } from "./types";
const state = {
  strategies: [{ id: "momentum", version: "1.0.0", name: "Momentum" }],
} as State;
const cfg = {
  hash: "h",
  strategy_id: "momentum",
  strategy_version: "1.0.0",
  mode: "manual",
  paused: false,
  symbols: ["AAPL", "SPY"],
  data_start: "2022-01-03",
  max_drift: ".03",
  policy: {
    positions: "25",
    max_weight: ".05",
    sector_cap: ".25",
    cash_reserve: ".02",
  },
};
const snapshot = {
  account_key: "test",
  checked_at: new Date().toISOString(),
  cash: "100000",
  equity: "100000",
  spendable_cash: "95000",
  unsettled_sales: "5000",
  issues: [],
  positions: [],
  open_orders: [],
};
function mount(
  paper: unknown,
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } }),
) {
  const fetch = vi.fn().mockImplementation(async (path: string) => ({
    ok: true,
    json: async () =>
      path === "/api/paper"
        ? paper
        : path === "/api/providers"
          ? { watchlist: { symbols: ["AAPL", "SPY"], start: "2022-01-03" } }
          : {},
  }));
  vi.stubGlobal("fetch", fetch);
  render(
    <QueryClientProvider client={client}>
      <PaperWorkspace state={state} />
    </QueryClientProvider>,
  );
  return fetch;
}
afterEach(() => vi.unstubAllGlobals());
it("defaults to manual and saves exact policy and dates without activation", async () => {
  const fetch = mount({ plans: [], orders: [], events: [] });
  expect(
    await screen.findByRole("combobox", { name: "Rebalance mode" }),
  ).toHaveValue("manual");
  fireEvent.change(screen.getByRole("textbox", { name: "US stock universe" }), {
    target: { value: "AAPL SPY" },
  });
  fireEvent.change(screen.getByLabelText("Historical data starts"), {
    target: { value: "2023-01-03" },
  });
  await userEvent.click(
    screen.getByRole("button", { name: "Save paper settings" }),
  );
  const request = fetch.mock.calls.find((c) => c[0] === "/api/paper/config");
  expect(JSON.parse(request![1].body)).toMatchObject({
    mode: "manual",
    data_start: "2023-01-03",
    max_weight: "0.05",
    cash_reserve: "0.02",
  });
  expect(fetch.mock.calls.some((c) => String(c[0]).includes("/approval"))).toBe(
    false,
  );
});

function savedPlan(id: string, planState = "prepared", message = "Ready") {
  return {
    id,
    state: planState,
    message,
    strategy: { id: "momentum", name: "Momentum", version: "1.0.0" },
    decision_session: "2026-11-02",
    execute_session: "2026-11-03",
    last_execution_session: "2026-11-04",
    cash_weight: ".2",
    account: snapshot,
    dataset_name: "Test snapshot",
    changes: [],
    targets: [],
    notes: [],
    signals: [],
    excluded: [],
  };
}

it("requires a fresh acknowledgement when a new prepared plan arrives", async () => {
  const client = new QueryClient();
  const paper = {
    config: cfg,
    snapshot,
    approval: { created_at: new Date().toISOString(), allow_automatic: false },
    plans: [savedPlan("first")],
    orders: [],
    events: [],
  };
  mount(paper, client);
  const ack = await screen.findByRole("checkbox", {
    name: /I reviewed this plan/,
  });
  await userEvent.click(ack);
  expect(
    screen.getByRole("button", { name: "Approve paper rebalance" }),
  ).toBeEnabled();
  await act(async () => {
    client.setQueryData(["paper"], { ...paper, plans: [savedPlan("next")] });
  });
  await waitFor(() =>
    expect(
      screen.getByRole("checkbox", { name: /I reviewed this plan/ }),
    ).not.toBeChecked(),
  );
  expect(
    screen.getByRole("button", { name: "Approve paper rebalance" }),
  ).toBeDisabled();
});

it("offers same-plan quote recovery only for quote blocks and with acknowledgement", async () => {
  const fetch = mount({
    config: cfg,
    snapshot,
    approval: { created_at: new Date().toISOString(), allow_automatic: false },
    plans: [savedPlan("held", "blocked", "AAPL: quote is stale")],
    orders: [],
    events: [],
  });
  const retry = await screen.findByRole("button", {
    name: "Recheck quotes & resume this plan",
  });
  expect(retry).toBeDisabled();
  await userEvent.click(
    screen.getByRole("checkbox", { name: /I rechecked this frozen plan/ }),
  );
  await userEvent.click(retry);
  expect(fetch).toHaveBeenCalledWith(
    "/api/paper/plans/held/retry-quote",
    expect.objectContaining({
      method: "POST",
      body: JSON.stringify({ acknowledge: true }),
    }),
  );
});
it("requires acknowledgement and exact strategy phrase with automatic permission separate", async () => {
  const fetch = mount({
    config: cfg,
    snapshot,
    plans: [],
    orders: [],
    events: [],
    worker_seen: new Date().toISOString(),
  });
  const submit = await screen.findByRole("button", {
    name: "Record paper strategy approval",
  });
  expect(submit).toBeDisabled();
  expect(
    screen.getByRole("checkbox", { name: /Also permit automatic/ }),
  ).not.toBeChecked();
  await userEvent.type(
    screen.getByLabelText("Approval rationale"),
    "Reviewed the limitations and validation.",
  );
  await userEvent.type(
    screen.getByLabelText("Type APPROVE PAPER momentum 1.0.0"),
    "APPROVE PAPER momentum 1.0.0",
  );
  await userEvent.click(
    screen.getByRole("checkbox", { name: /I accept these research/ }),
  );
  await userEvent.click(submit);
  const request = fetch.mock.calls.find((c) => c[0] === "/api/paper/approval");
  expect(JSON.parse(request![1].body)).toMatchObject({
    config_hash: "h",
    confirmation: "APPROVE PAPER momentum 1.0.0",
    allow_automatic: false,
    acknowledge_limits: true,
  });
});
it("prepares read-only data through one action and exposes cash settlement separately", async () => {
  const fetch = mount({
    config: cfg,
    snapshot,
    plans: [],
    orders: [],
    events: [],
  });
  await userEvent.click(
    await screen.findByRole("button", { name: "Prepare weekly paper review" }),
  );
  expect(fetch).toHaveBeenCalledWith(
    "/api/paper/actions/prepare",
    expect.objectContaining({ method: "POST" }),
  );
  expect(screen.getByText("$95,000.00")).toBeVisible();
  expect(screen.getByText("$5,000.00")).toBeVisible();
  expect(
    fetch.mock.calls.some(
      (c) =>
        String(c[0]).includes("/plans/") || String(c[0]).includes("/approval"),
    ),
  ).toBe(false);
});
