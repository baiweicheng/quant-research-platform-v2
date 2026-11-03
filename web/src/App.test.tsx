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
  fireEvent.change(screen.getByLabelText("Stock symbols"), {
    target: { value: "AAPL, CUSTOM" },
  });
  await userEvent.click(downloadButton);
  await screen.findByRole("heading", { name: "Your work, kept in view." });
  const call = vi
    .mocked(globalThis.fetch)
    .mock.calls.find((call) => call[0] === "/api/downloads")!;
  expect(JSON.parse(String(call[1]?.body))).toMatchObject({
    symbols: ["AAPL", "CUSTOM"],
    start: "2022-01-03",
    end: "2025-12-31",
  });
  expect(String(call[1]?.body)).not.toMatch(/secret|api_key/i);
});

it("opens Data for a completed download rather than treating it as a portfolio review", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValue({
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
