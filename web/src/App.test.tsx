import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import { MetricStrip, PeriodPicker } from "./components";
import { ImportDialog, TaskDialog } from "./dialogs";
import type { State } from "./types";
import { percent, points } from "./api";
import { SignalAudit } from "./Fundamentals";

function ConnectedSignalAudit(props: React.ComponentProps<typeof SignalAudit>) {
  return (
    <QueryClientProvider client={new QueryClient()}>
      <SignalAudit {...props} />
    </QueryClientProvider>
  );
}
const state: State = {
  version: "0.1.0",
  datasets: [],
  strategies: [
    {
      id: "momentum",
      name: "Momentum",
      version: "1.0.0",
      category: "Technical",
      description: "Relative strength.",
      risk: "Reversals.",
      inputs: "253 sessions.",
      implemented: true,
    },
    {
      id: "value_momentum",
      name: "Value + Momentum",
      version: "pending",
      category: "Technical + fundamental",
      description: "Blend signals.",
      risk: "Drawdowns.",
      inputs: "PIT filings.",
      implemented: false,
    },
  ],
  jobs: [],
  runs: [],
  reviews: [],
  account: { connected: false, planning_capital: "100000", mode: "research" },
};
function wrapper(children: React.ReactNode) {
  return (
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  );
}
function mockState() {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: true, json: async () => state }),
  );
}
afterEach(() => vi.unstubAllGlobals());

describe("honest research workspace", () => {
  it("shows planning capital without fabricated account returns", async () => {
    mockState();
    render(wrapper(<App />));
    expect(await screen.findByText("$100,000.00")).toBeVisible();
    expect(
      screen.getByText("Research only · No brokerage account connected"),
    ).toBeVisible();
    expect(screen.getAllByText("—")).toHaveLength(3);
    expect(screen.queryByText(/approve orders/i)).not.toBeInTheDocument();
  });
  it("guides weekly preparation to Data when no dataset exists", async () => {
    mockState();
    render(wrapper(<App />));
    await userEvent.click(
      await screen.findByRole("button", { name: "Prepare weekly review" }),
    );
    expect(
      screen.getByRole("heading", { name: "Good research starts here." }),
    ).toBeVisible();
    expect(
      screen.getByText(
        "Add a dataset or create the practice universe to begin.",
      ),
    ).toBeVisible();
  });
  it("explains fundamental gating instead of offering a fake runnable strategy", async () => {
    mockState();
    render(wrapper(<App />));
    await userEvent.click(
      await screen.findByRole("link", { name: "Research" }),
    );
    expect(await screen.findByText("Fundamentals milestone")).toBeVisible();
    const details = screen.getAllByRole("button", { name: /How it works/ });
    await userEvent.click(details[1]);
    expect(screen.getByRole("dialog")).toHaveTextContent(
      "Historical filing availability",
    );
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
  it("recovers connection failures through Retry", async () => {
    const fetch = vi
      .fn()
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValue({ ok: true, json: async () => state });
    vi.stubGlobal("fetch", fetch);
    render(wrapper(<App />));
    await userEvent.click(
      await screen.findByRole("button", { name: "Retry connection" }),
    );
    expect(await screen.findByText("$100,000.00")).toBeVisible();
  });
  it("queues a real task with chosen inputs and keeps synthetic labeling", async () => {
    const fetch = vi
      .fn()
      .mockResolvedValue({ ok: true, json: async () => ({ id: "job" }) });
    vi.stubGlobal("fetch", fetch);
    const dataset = {
      id: "data",
      name: "Practice",
      kind: "synthetic" as const,
      start: "2022-01-03",
      end: "2025-12-31",
      symbols: ["ABC"],
      row_count: 1000,
      symbol_count: 1,
      source: "test",
      digest: "hash",
      warnings: [],
      created_at: "",
    };
    const queued = vi.fn();
    render(
      wrapper(
        <TaskDialog
          kind="backtest"
          state={{ ...state, datasets: [dataset] }}
          onClose={() => {}}
          onQueued={queued}
        />,
      ),
    );
    expect(screen.getByText(/Synthetic practice data/)).toBeVisible();
    fireEvent.change(screen.getByLabelText("Start date"), {
      target: { value: "2024-01-02" },
    });
    // A native date editor/autofill can update the visible DOM before React's
    // change callback. Submit must use what the user actually sees.
    const input = screen.getByLabelText("Start date") as HTMLInputElement;
    Object.getOwnPropertyDescriptor(
      HTMLInputElement.prototype,
      "value",
    )!.set!.call(input, "2024-02-01");
    await userEvent.click(screen.getByRole("button", { name: "Run backtest" }));
    await waitFor(() => expect(queued).toHaveBeenCalled());
    expect(JSON.parse(fetch.mock.calls[0][1].body)).toMatchObject({
      dataset_id: "data",
      strategy_id: "momentum",
      start: "2024-02-01",
      capital: "100000",
    });
    expect(fetch.mock.calls[0][1].headers["X-Aperture-Client"]).toBe("1");
  });
  it("shows actionable server errors inside the task dialog", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 422,
        json: async () => ({
          detail: "Dataset is stale. Import updated data.",
        }),
      }),
    );
    const dataset = {
      id: "d",
      name: "Market",
      kind: "imported" as const,
      start: "2022-01-03",
      end: "2025-12-31",
      symbols: ["ABC"],
      row_count: 1000,
      symbol_count: 1,
      source: "test",
      digest: "hash",
      warnings: [],
      created_at: "",
    };
    render(
      wrapper(
        <TaskDialog
          kind="review"
          state={{ ...state, datasets: [dataset] }}
          onClose={() => {}}
          onQueued={() => {}}
        />,
      ),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Prepare review" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Dataset is stale",
    );
  });
});

it("offers every approved chart period and preserves selection semantics", async () => {
  const change = vi.fn();
  render(<PeriodPicker value="YTD" onChange={change} />);
  for (const name of ["1W", "1M", "3M", "6M", "YTD", "1Y", "All"])
    expect(screen.getByRole("button", { name })).toBeVisible();
  expect(screen.getByRole("button", { name: "YTD" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await userEvent.click(screen.getByRole("button", { name: "1W" }));
  expect(change).toHaveBeenCalledWith("1W");
});
it("keeps percentage-point comparison distinct from percentage return", () => {
  expect(percent(0.12, true)).toBe("+12.00%");
  expect(points(0.025)).toBe("+2.50 pp");
  render(
    <MetricStrip
      metrics={{
        return: 0.12,
        difference: 0.025,
        drawdown: -0.18,
        benchmark_return: 0.095,
        volatility: null,
        cagr: null,
      }}
    />,
  );
  expect(screen.getByText("+12.00%")).toBeVisible();
  expect(screen.getByText("+2.50 pp")).toBeVisible();
  expect(screen.getByText("-18.00%")).toBeVisible();
});

it("imports pasted CSV and displays row-level validation errors", async () => {
  const fetch = vi.fn().mockResolvedValue({
    ok: false,
    status: 422,
    json: async () => ({ detail: "Row 2: inconsistent OHLC bounds." }),
  });
  vi.stubGlobal("fetch", fetch);
  render(wrapper(<ImportDialog onClose={() => {}} onImported={() => {}} />));
  await userEvent.type(screen.getByLabelText("Dataset name"), "Test prices");
  await userEvent.type(screen.getByLabelText("Data source"), "Hand-authored");
  await userEvent.click(screen.getByRole("button", { name: "Paste CSV" }));
  const csv =
    "symbol,date,open,high,low,close,volume\nABC,2025-01-06,100,90,99,101,1000";
  fireEvent.change(screen.getByLabelText("CSV content"), {
    target: { value: csv },
  });
  await userEvent.click(screen.getByRole("checkbox"));
  await userEvent.click(screen.getByRole("button", { name: "Import dataset" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Row 2: inconsistent OHLC",
  );
  expect(JSON.parse(fetch.mock.calls[0][1].body)).toMatchObject({
    csv,
    name: "Test prices",
    source: "Hand-authored",
    price_basis: "as_traded",
  });
});

it("reads a selected CSV file and completes import", async () => {
  const fetch = vi
    .fn()
    .mockResolvedValue({ ok: true, json: async () => ({ id: "dataset" }) });
  vi.stubGlobal("fetch", fetch);
  const done = vi.fn();
  render(wrapper(<ImportDialog onClose={() => {}} onImported={done} />));
  await userEvent.type(screen.getByLabelText("Dataset name"), "File prices");
  await userEvent.type(screen.getByLabelText("Data source"), "Fixture");
  const csv =
    "symbol,date,open,high,low,close,volume\nABC,2025-01-06,100,102,99,101,1000";
  const file = new File([csv], "prices.csv", { type: "text/csv" });
  await userEvent.upload(screen.getByLabelText("CSV file"), file);
  expect(
    (screen.getByLabelText("CSV file") as HTMLInputElement).files,
  ).toHaveLength(1);
  expect(screen.getByLabelText("CSV file")).toBeValid();
  await userEvent.click(screen.getByRole("checkbox"));
  await userEvent.click(screen.getByRole("button", { name: "Import dataset" }));
  await waitFor(() => expect(done).toHaveBeenCalled());
  expect(JSON.parse(fetch.mock.calls[0][1].body).csv).toBe(csv);
});

it("downloads a custom stock list from the interface without exposing credentials", async () => {
  const fetch = vi.fn(async (path: string) => ({
    ok: true,
    json: async () =>
      path === "/api/providers"
        ? {
            alpaca_configured: true,
            sec_configured: true,
            latest_session: "2025-12-31",
            first_session: "2016-01-04",
            watchlist: {
              name: "My stocks",
              symbols: ["AAPL", "SPY"],
              start: "2022-01-03",
            },
          }
        : state,
  }));
  vi.stubGlobal("fetch", fetch);
  render(wrapper(<App />));
  await userEvent.click(await screen.findByRole("link", { name: "Data" }));
  const downloadButton = await screen.findByRole("button", {
    name: "Download & validate",
  });
  await waitFor(() => expect(downloadButton).toBeEnabled());
  await userEvent.selectOptions(
    screen.getByLabelText("Stock universe"),
    "custom",
  );
  fireEvent.change(screen.getByLabelText("Stock symbols"), {
    target: { value: "AAPL, CUSTOM" },
  });
  await userEvent.click(
    screen.getByRole("button", { name: "Download & validate" }),
  );
  await screen.findByRole("heading", { name: "Your work, kept in view." });
  const call = vi
    .mocked(globalThis.fetch)
    .mock.calls.find((call) => call[0] === "/api/downloads")!;
  expect(JSON.parse(String(call[1]?.body))).toMatchObject({
    symbols: ["AAPL", "CUSTOM"],
    start: "2016-01-04",
    end: "2025-12-31",
  });
  expect(String(call[1]?.body)).not.toMatch(/secret|api_key/i);
});

it("opens Data for a completed download rather than treating it as a portfolio review", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        ...state,
        jobs: [
          {
            id: "download",
            kind: "download",
            state: "complete",
            progress: 100,
            message: "Saved bars",
            created_at: "2025-12-31T12:00:00Z",
            updated_at: "2025-12-31T12:00:00Z",
            result_id: "snapshot",
          },
        ],
      }),
    }),
  );
  render(wrapper(<App />));
  await userEvent.click(await screen.findByRole("link", { name: "Activity" }));
  await userEvent.click(screen.getByRole("button", { name: "Open data" }));
  expect(
    screen.getByRole("heading", { name: "Good research starts here." }),
  ).toBeVisible();
});

it("blocks fundamental runs until the selected dataset includes SEC statements", async () => {
  const dataset = {
    id: "prices",
    name: "Prices",
    kind: "imported" as const,
    start: "2022-01-03",
    end: "2025-12-31",
    symbols: ["ABC"],
    row_count: 1000,
    symbol_count: 1,
    source: "Fixture",
    digest: "hash",
    warnings: [],
    created_at: "",
  };
  const strategies = state.strategies.map((s) => ({ ...s, implemented: true }));
  render(
    wrapper(
      <TaskDialog
        kind="backtest"
        state={{ ...state, strategies, datasets: [dataset] }}
        initial="value_momentum"
        onClose={() => {}}
        onQueued={() => {}}
      />,
    ),
  );
  expect(screen.getByRole("button", { name: "Run backtest" })).toBeDisabled();
  expect(
    screen.getByText(/Select a downloaded market and SEC snapshot/),
  ).toBeVisible();
  await userEvent.selectOptions(screen.getByLabelText("Strategy"), "momentum");
  expect(screen.getByRole("button", { name: "Run backtest" })).toBeEnabled();
});

it("shows the actual selected decision's filing and excluded-stock audit", async () => {
  const components = {
    profitability: "0.2",
    earnings_yield: "0.04",
    momentum: 0.12,
    filing: {
      start: "2022-01-01",
      end: "2022-12-31",
      filed: "2023-02-10",
      available_at: "2023-02-13T21:15:00Z",
      accession: "0000000001-23-000001",
      url: "https://www.sec.gov/Archives/edgar/data/1/000000000123000001/",
      sources: { gross_profit: "Revenues - CostOfRevenue" },
      issues: [],
    },
  };
  render(
    <ConnectedSignalAudit
      decisions={[
        {
          session: "2023-08-25",
          execute_session: "2023-08-28",
          eligible: 1,
          signals: [{ symbol: "ABC", score: 0.5, components }],
          exclusions: [
            { symbol: "MISSING", reason: "No annual filing available." },
          ],
        },
        {
          session: "2023-09-01",
          execute_session: "2023-09-05",
          eligible: 1,
          signals: [{ symbol: "XYZ", score: 0.5, components }],
          exclusions: [],
        },
      ]}
    />,
  );
  expect(screen.getByText("XYZ")).toBeVisible();
  await userEvent.selectOptions(
    screen.getByLabelText("Signal decision"),
    "2023-08-25",
  );
  expect(screen.getByText("ABC")).toBeVisible();
  expect(screen.queryByText("XYZ")).not.toBeInTheDocument();
  expect(screen.getByText("20.00%")).toBeVisible();
  await userEvent.click(
    screen.getByText("Fiscal end 2022-12-31 · filed 2023-02-10"),
  );
  expect(screen.getByRole("link", { name: /SEC filing/ })).toHaveAttribute(
    "href",
    components.filing.url,
  );
  await userEvent.click(screen.getByText("Excluded stocks (1)"));
  expect(screen.getByText(/No annual filing available/)).toBeVisible();
});

it("keeps zero-eligible fundamental decisions inspectable", async () => {
  render(
    <ConnectedSignalAudit
      fundamental
      decisions={[
        {
          session: "2023-01-09",
          execute_session: "2023-01-10",
          eligible: 0,
          signals: [],
          exclusions: [{ symbol: "ABC", reason: "No filing was available." }],
        },
      ]}
    />,
  );
  expect(
    screen.getByRole("heading", { name: "Why these stocks?" }),
  ).toBeVisible();
  expect(screen.getByLabelText("Signal decision")).toHaveValue("2023-01-09");
  await userEvent.click(screen.getByText("Excluded stocks (1)"));
  expect(screen.getByText(/No filing was available/)).toBeVisible();
});

it("queues SEC enrichment for the chosen saved dataset through Data", async () => {
  const dataset = {
    id: "prices",
    name: "Prices",
    kind: "imported" as const,
    start: "2022-01-03",
    end: "2025-12-31",
    symbols: ["ABC"],
    row_count: 1000,
    symbol_count: 1,
    source: "Fixture",
    digest: "hash",
    warnings: [],
    created_at: "",
  };
  const fetch = vi.fn(async (path: string) => ({
    ok: true,
    json: async () =>
      path === "/api/providers"
        ? {
            sec_configured: true,
            alpaca_configured: false,
            latest_session: "2025-12-31",
            first_session: "2016-01-04",
            watchlist: {
              name: "My list",
              symbols: ["ABC"],
              start: "2022-01-03",
            },
          }
        : { ...state, datasets: [dataset] },
  }));
  vi.stubGlobal("fetch", fetch);
  render(wrapper(<App />));
  await userEvent.click(await screen.findByRole("link", { name: "Data" }));
  const add = await screen.findByRole("button", { name: "Complete snapshot" });
  await waitFor(() => expect(add).toBeEnabled());
  await userEvent.click(add);
  expect(
    await screen.findByRole("heading", { name: "Your work, kept in view." }),
  ).toBeVisible();
  const call = fetch.mock.calls.find(
    (c) => c[0] === "/api/fundamentals/prices",
  );
  expect(call).toBeDefined();
});
