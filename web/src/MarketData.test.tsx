import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import MarketData from "./MarketData";

const info = {
  alpaca_configured: true,
  latest_session: "2026-11-02",
  first_session: "2016-01-04",
  watchlist: { name: "Old list", symbols: [], start: "2026-10-28" },
  membership: {
    current: null,
    historical: {
      id: "history",
      member_count: 503,
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
it("defaults to the entire index and allows an empty supplement", async () => {
  const fetcher = setup();
  await screen.findByText(/Available history: 1996-01-02/);
  const select = screen.getByLabelText("Stock universe");
  expect(select).toHaveValue("sp500_current");
  expect(
    screen.getByLabelText("Additional stock symbols (optional)"),
  ).not.toBeRequired();
  await userEvent.click(
    screen.getByRole("button", { name: "Download & validate" }),
  );
  await waitFor(() =>
    expect(fetcher).toHaveBeenCalledWith("/api/downloads", expect.anything()),
  );
  const call = fetcher.mock.calls.find(([url]) => url === "/api/downloads");
  expect(JSON.parse(call![1].body)).toMatchObject({
    universe: "sp500_current",
    symbols: [],
  });
});
it("submits extras as a supplement and uses historical source boundaries", async () => {
  const fetcher = setup();
  await screen.findByText(/Available history: 1996-01-02/);
  await userEvent.selectOptions(
    screen.getByLabelText("Stock universe"),
    "sp500_historical",
  );
  await userEvent.type(
    screen.getByLabelText("Additional stock symbols (optional)"),
    "XYZ, ABC",
  );
  expect(screen.getByLabelText("Through session")).toHaveValue("2026-08-18");
  expect(screen.getByLabelText("History from")).toHaveValue("2022-01-03");
  expect(
    screen.getByText(/Historical downloads include all members/),
  ).toBeVisible();
  await userEvent.click(
    screen.getByRole("button", { name: "Download & validate" }),
  );
  await waitFor(() =>
    expect(fetcher).toHaveBeenCalledWith("/api/downloads", expect.anything()),
  );
  const call = fetcher.mock.calls.find(([url]) => url === "/api/downloads");
  expect(JSON.parse(call![1].body)).toMatchObject({
    universe: "sp500_historical",
    symbols: ["XYZ", "ABC"],
  });
});
it("refreshes membership only on an explicit action", async () => {
  const fetcher = setup();
  await screen.findByLabelText("Stock universe");
  expect(fetcher.mock.calls.every(([url]) => url === "/api/providers")).toBe(
    true,
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Refresh current membership" }),
  );
  await waitFor(() =>
    expect(fetcher).toHaveBeenCalledWith(
      "/api/membership/current/refresh",
      expect.anything(),
    ),
  );
});
