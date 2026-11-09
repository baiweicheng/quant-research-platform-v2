import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { TaskDialog } from "./dialogs";
import type { State } from "./types";

const state: State = {
  version: "test",
  datasets: [
    {
      id: "saved",
      name: "Captured prices",
      kind: "imported",
      start: "2022-01-03",
      end: "2025-12-31",
      symbols: ["ABC"],
      symbol_count: 1,
      row_count: 1000,
      source: "Fixture",
      digest: "digest",
      warnings: [],
      created_at: "",
    },
  ],
  strategies: [
    { id: "momentum", name: "Momentum", category: "Technical" },
    { id: "low_volatility", name: "Low volatility", category: "Technical" },
    { id: "quality", name: "Quality", category: "Fundamental" },
  ].map((s) => ({
    ...s,
    version: "1.0.0",
    inputs: "Captured data",
    risk: "Research",
    description: "Fixture",
    implemented: true,
  })),
  jobs: [],
  runs: [],
  reviews: [],
  account: { connected: false, planning_capital: "100000", mode: "research" },
};

function setup(next = state, kind: "backtest" | "review" = "backtest") {
  const fetcher = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ count: 2, jobs: [{ id: "one" }, { id: "two" }] }),
  });
  vi.stubGlobal("fetch", fetcher);
  const queued = vi.fn();
  render(
    <QueryClientProvider client={new QueryClient()}>
      <TaskDialog
        kind={kind}
        state={next}
        initial={next.strategies[0].id}
        onClose={() => {}}
        onQueued={queued}
      />
    </QueryClientProvider>,
  );
  return { fetcher, queued };
}

afterEach(() => vi.unstubAllGlobals());

it("submits selected strategies once with the same visible inputs", async () => {
  const { fetcher, queued } = setup();
  expect(screen.getByRole("checkbox", { name: "Momentum" })).toBeChecked();
  await userEvent.click(
    screen.getByRole("checkbox", { name: "Low volatility" }),
  );
  await userEvent.clear(screen.getByLabelText("Starting capital · USD"));
  await userEvent.type(
    screen.getByLabelText("Starting capital · USD"),
    "125000",
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Run 2 backtests" }),
  );
  await waitFor(() => expect(queued).toHaveBeenCalledOnce());
  expect(fetcher).toHaveBeenCalledOnce();
  expect(fetcher.mock.calls[0][0]).toBe("/api/tasks/backtests");
  expect(JSON.parse(fetcher.mock.calls[0][1].body)).toEqual({
    dataset_id: "saved",
    strategy_ids: ["momentum", "low_volatility"],
    start: "2023-01-01",
    end: "2025-12-31",
    capital: "125000",
    dividend_model: "ex_date",
    coverage_mode: "coverage_limited",
  });
});

it("keeps empty or unsupported fundamental selections out of the queue", async () => {
  const { fetcher } = setup();
  await userEvent.click(screen.getByRole("button", { name: "Select all" }));
  expect(
    screen.getByRole("button", { name: "Run 3 backtests" }),
  ).toBeDisabled();
  expect(screen.getByText(/This selection needs/)).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Clear" }));
  expect(screen.getByText("0 selected")).toBeVisible();
  expect(screen.getByRole("button", { name: "Run backtest" })).toBeDisabled();
  expect(fetcher).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole("checkbox", { name: "Momentum" }));
  expect(screen.getByRole("button", { name: "Run backtest" })).toBeEnabled();
});

it("keeps selected strategies when a larger catalog is filtered", async () => {
  const strategies = Array.from({ length: 10 }, (_, i) => ({
    ...state.strategies[0],
    id: `candidate${i}`,
    name: `Candidate ${i}`,
  }));
  const { fetcher, queued } = setup({ ...state, strategies });
  await userEvent.click(screen.getByRole("button", { name: "Select all" }));
  await userEvent.type(
    screen.getByRole("searchbox", { name: "Find strategies" }),
    "Candidate 9",
  );
  expect(screen.getAllByRole("checkbox")).toHaveLength(1);
  expect(screen.getByText("10 selected")).toBeVisible();
  await userEvent.click(
    screen.getByRole("button", { name: "Run 10 backtests" }),
  );
  await waitFor(() => expect(queued).toHaveBeenCalledOnce());
  expect(JSON.parse(fetcher.mock.calls[0][1].body).strategy_ids).toEqual(
    strategies.map((s) => s.id),
  );
});

it("retains a single strategy for an allocation review", async () => {
  const { fetcher, queued } = setup(state, "review");
  expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  await userEvent.selectOptions(
    screen.getByLabelText("Strategy"),
    "low_volatility",
  );
  await userEvent.click(screen.getByRole("button", { name: "Prepare review" }));
  await waitFor(() => expect(queued).toHaveBeenCalledOnce());
  expect(fetcher.mock.calls[0][0]).toBe("/api/tasks/review");
  expect(JSON.parse(fetcher.mock.calls[0][1].body).strategy_id).toBe(
    "low_volatility",
  );
});
