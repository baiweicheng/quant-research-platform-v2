import { render as baseRender, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { RunDetail } from "./Research";
import type { Run } from "./types";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
const render = (node: React.ReactNode) =>
  baseRender(
    <QueryClientProvider client={new QueryClient()}>
      {node}
    </QueryClientProvider>,
  );
vi.mock("./Chart", () => ({ default: () => <div>Chart fixture</div> }));
const run = {
  id: "result",
  created_at: "2026-11-05T10:00:00Z",
  dataset_id: "data",
  dataset_name: "Research",
  dataset_kind: "imported",
  strategy: { id: "momentum", name: "Momentum", version: "1.0.0" },
  start: "2025-01-02",
  end: "2026-11-04",
  trade_count: 0,
  capital: "100000",
  frequency: "monthly",
  source_digest: "hash",
  notes: [],
  execution_model: "Next open",
  benchmark_model: "Same assumptions",
  dividend_model: "ex_date",
  policy: {
    max_weight: ".03",
    sector_cap: ".20",
    cash_reserve: ".10",
    slippage_bps: "15",
    fee_bps: "2",
  },
  coverage: {
    mode: "coverage_limited",
    excluded_count: 1,
    universe_count: 2,
    warning: "Coverage-limited research can introduce survivorship bias.",
    excluded: [
      { symbol: "OLD", reasons: ["Missing terminal price; no exit assumed."] },
    ],
  },
  curve: [],
  trades: [],
  holdings: [],
  decisions: [],
  windows: {
    All: {
      start: "2025-01-02",
      end: "2026-11-04",
      start_index: 0,
      limited: false,
      metrics: {
        return: 0,
        benchmark_return: 0,
        difference: 0,
        drawdown: 0,
        volatility: 0,
        cagr: 0,
      },
    },
  },
} as unknown as Run;
it("displays the saved sensitivity policy rather than default assumptions", () => {
  render(<RunDetail run={run} period="All" setPeriod={() => {}} />);
  expect(screen.getByText("3.00% per position")).toBeVisible();
  expect(screen.getByText("20.00% per sector")).toBeVisible();
  expect(screen.getByText("At least 10.00%")).toBeVisible();
  expect(
    screen.getByText("15 bps slippage + 2 bp fee, each side"),
  ).toBeVisible();
});
it("keeps every coverage exclusion and the selected dividend convention visible", () => {
  render(<RunDetail run={run} period="All" setPeriod={() => {}} />);
  expect(screen.getByText(/survivorship bias/)).toBeVisible();
  expect(screen.getByText("OLD")).toBeInTheDocument();
  expect(
    screen.getByText("Missing terminal price; no exit assumed."),
  ).toBeInTheDocument();
  expect(
    screen.getByText(/not payment-date cash availability/),
  ).toBeInTheDocument();
});

it("makes the low equity exposure of a legacy result prominent without changing returns", () => {
  const saved = {
    ...run,
    curve: [
      {
        session: "2025-01-02",
        equity: "100",
        cash: "75",
        receivable: "0",
        benchmark: "100",
      },
      {
        session: "2026-11-04",
        equity: "110",
        cash: "82.5",
        receivable: "0",
        benchmark: "120",
      },
    ],
  };
  render(<RunDetail run={saved} period="All" setPeriod={() => {}} />);
  expect(
    screen.getByText("Average allocation: 25.00% stocks / 75.00% cash."),
  ).toBeVisible();
  expect(
    screen.getByText(/SPY is a fully invested buy-and-hold comparison/),
  ).toBeVisible();
  expect(
    screen.getByText(/original classifications and returns are preserved/),
  ).toBeVisible();
});

it("loads the selected saved decision without replacing it with another date's audit", async () => {
  const { SignalAudit } = await import("./Fundamentals");
  const user = (await import("@testing-library/user-event")).default;
  const fetcher = vi.fn().mockImplementation(async (url: string) => ({
    ok: true,
    json: async () => ({
      session: url.endsWith("2026-11-04") ? "2026-11-04" : "2026-10-30",
      execute_session: "2026-11-05",
      eligible: 1,
      signals: [
        {
          symbol: url.endsWith("2026-11-04") ? "LATEST" : "EARLIER",
          score: 1,
          components: {},
        },
      ],
      exclusions: [],
    }),
  }));
  vi.stubGlobal("fetch", fetcher);
  render(
    <SignalAudit
      fundamental
      auditPath="/results/saved"
      decisions={[
        { session: "2026-10-30", execute_session: "2026-11-02", eligible: 1 },
        { session: "2026-11-04", execute_session: "2026-11-05", eligible: 1 },
      ]}
    />,
  );
  expect(await screen.findByText("LATEST")).toBeVisible();
  await user.selectOptions(
    screen.getByLabelText("Signal decision"),
    "2026-10-30",
  );
  expect(await screen.findByText("EARLIER")).toBeVisible();
  expect(screen.queryByText("LATEST")).not.toBeInTheDocument();
  expect(fetcher).toHaveBeenCalledWith(
    "/api/results/saved/decisions/2026-10-30",
    undefined,
  );
  vi.unstubAllGlobals();
});
