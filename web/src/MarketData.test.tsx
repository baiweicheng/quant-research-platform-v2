import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import MarketData from "./MarketData";

const info = {
  alpaca_configured: true,
  sec_configured: true,
  latest_session: "2026-11-02",
  first_session: "2016-01-04",
  watchlist: { name: "Old list", symbols: [], start: "2026-10-28" },
  membership: {
    current: null,
    historical: {
      id: "history",
      member_count: 503,
      unique_member_count: 1200,
      captured_at: "2026-11-03T12:00:00Z",
      source: "https://example.com/source",
      coverage_start: "1996-01-02",
      coverage_end: "2026-08-18",
    },
  },
};
function setup() {
  const fetcher = vi.fn().mockImplementation(async (_url, init) => ({
    ok: true,
    json: async () => (init ? { id: "job" } : info),
  }));
  vi.stubGlobal("fetch", fetcher);
  render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <MemoryRouter>
        <MarketData />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return fetcher;
}
afterEach(() => vi.unstubAllGlobals());
it("defaults to S&P only with the earliest supported start and no custom input", async () => {
  const fetcher = setup();
  await screen.findByText(/Historical backtest membership: 1996-01-02/);
  const select = screen.getByLabelText("Stock universe");
  expect(select).toHaveValue("sp500");
  expect(screen.getAllByRole("option")).toHaveLength(3);
  expect(screen.getByText(/1,200 unique securities/)).toBeVisible();
  expect(
    screen.queryByLabelText("Additional stock symbols"),
  ).not.toBeInTheDocument();
  expect(screen.getByLabelText("Dataset name")).toHaveValue("S&P 500");
  expect(screen.getByLabelText("History from")).toHaveValue("2016-01-04");
  await userEvent.click(
    screen.getByRole("button", { name: "Download & validate" }),
  );
  await waitFor(() =>
    expect(fetcher).toHaveBeenCalledWith("/api/downloads", expect.anything()),
  );
  const call = fetcher.mock.calls.find(([url]) => url === "/api/downloads");
  expect(JSON.parse(call![1].body)).toMatchObject({
    universe: "sp500",
    symbols: [],
  });
});
it("submits supplements and keeps price dates separate from membership coverage", async () => {
  const fetcher = setup();
  await screen.findByText(/Historical backtest membership: 1996-01-02/);
  await userEvent.selectOptions(
    screen.getByLabelText("Stock universe"),
    "sp500_plus",
  );
  expect(screen.getByLabelText("Dataset name")).toHaveValue(
    "S&P 500 + custom list",
  );
  await userEvent.type(
    screen.getByLabelText("Additional stock symbols"),
    "XYZ, ABC",
  );
  expect(screen.getByLabelText("Through session")).toHaveValue("2026-11-02");
  expect(screen.getByLabelText("History from")).toHaveValue("2016-01-04");
  expect(
    screen.getByText(/Backtests automatically use dated membership/),
  ).toBeVisible();
  await userEvent.click(
    screen.getByRole("button", { name: "Download & validate" }),
  );
  await waitFor(() =>
    expect(fetcher).toHaveBeenCalledWith("/api/downloads", expect.anything()),
  );
  const call = fetcher.mock.calls.find(([url]) => url === "/api/downloads");
  expect(JSON.parse(call![1].body)).toMatchObject({
    universe: "sp500",
    symbols: ["XYZ", "ABC"],
    start: "2016-01-04",
    end: "2026-11-02",
  });
});
it("refreshes membership only on an explicit action", async () => {
  const fetcher = setup();
  await screen.findByLabelText("Stock universe");
  expect(fetcher.mock.calls.every(([url]) => url === "/api/providers")).toBe(
    true,
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Refresh S&P 500 membership" }),
  );
  await waitFor(() =>
    expect(fetcher).toHaveBeenCalledWith(
      "/api/membership/all/refresh",
      expect.anything(),
    ),
  );
});

it("keeps custom lists explicit and explains the final change date", async () => {
  const fetcher = setup();
  await screen.findByText(/Historical backtest membership: 1996-01-02/);
  await userEvent.click(screen.getByText("Membership sources and changes"));
  expect(
    screen.getByText(/A last change date is not an expiry date/),
  ).toBeVisible();
  await userEvent.selectOptions(
    screen.getByLabelText("Stock universe"),
    "custom",
  );
  expect(screen.getByLabelText("Stock symbols")).toBeRequired();
  expect(screen.getByLabelText("Dataset name")).toHaveValue(
    "Custom stock list",
  );
  await userEvent.type(screen.getByLabelText("Stock symbols"), "ABC");
  await userEvent.click(
    screen.getByRole("button", { name: "Download & validate" }),
  );
  await waitFor(() =>
    expect(fetcher).toHaveBeenCalledWith("/api/downloads", expect.anything()),
  );
  const call = fetcher.mock.calls.find(([url]) => url === "/api/downloads");
  expect(JSON.parse(call![1].body)).toMatchObject({
    universe: "custom",
    symbols: ["ABC"],
  });
});

it("preserves a user-written dataset name when the universe changes", async () => {
  setup();
  await screen.findByText(/Historical backtest membership: 1996-01-02/);
  await userEvent.clear(screen.getByLabelText("Dataset name"));
  await userEvent.type(screen.getByLabelText("Dataset name"), "My research");
  await userEvent.selectOptions(
    screen.getByLabelText("Stock universe"),
    "custom",
  );
  expect(screen.getByLabelText("Dataset name")).toHaveValue("My research");
});
