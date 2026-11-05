import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import DatasetUpdates from "./DatasetUpdates";
import type { Dataset } from "./types";

const price = {
  id: "prices",
  name: "S&P 500",
  kind: "imported",
  start: "2016-01-04",
  end: "2026-11-03",
  symbols: ["ABC"],
  row_count: 100,
  symbol_count: 1,
  source: "Alpaca",
  digest: "digest",
  warnings: [],
  created_at: "2026-11-04T10:00:00Z",
  metadata: { provider: "alpaca" },
} as Dataset;
const sec = {
  ...price,
  id: "sec",
  name: "S&P 500 + SEC",
  metadata: {
    provider: "alpaca",
    fundamentals: {
      record_count: 1,
      coverage: [],
      availability: "Fixture",
      retrieved_at: "2026-11-04T10:00:00Z",
    },
  },
} as Dataset;
function setup(datasets = [sec, price], fail = false) {
  const fetcher = vi.fn(async () => ({
    ok: !fail,
    status: fail ? 400 : 202,
    json: async () =>
      fail
        ? { detail: "Provider unavailable; existing snapshots preserved." }
        : { id: "job" },
  }));
  vi.stubGlobal("fetch", fetcher);
  render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <MemoryRouter>
        <DatasetUpdates datasets={datasets} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return fetcher;
}
afterEach(() => vi.unstubAllGlobals());

it("updates the selected SEC vintage and explains sharing and older history", async () => {
  const fetcher = setup();
  expect(screen.getByLabelText("Dataset to update")).toHaveValue("sec");
  expect(screen.getByText(/Prices \+ SEC filings/)).toBeVisible();
  expect(screen.getByText(/shares unchanged data/)).toBeVisible();
  expect(screen.getByText(/10-day refresh window/)).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Update dataset" }));
  await waitFor(() =>
    expect(fetcher).toHaveBeenCalledWith(
      "/api/datasets/sec/update",
      expect.anything(),
    ),
  );
});

it("preserves selection and displays a provider failure", async () => {
  const fetcher = setup([sec, price], true);
  await userEvent.selectOptions(
    screen.getByLabelText("Dataset to update"),
    "prices",
  );
  await userEvent.click(screen.getByRole("button", { name: "Update dataset" }));
  await screen.findByText(
    "Provider unavailable; existing snapshots preserved.",
  );
  expect(screen.getByLabelText("Dataset to update")).toHaveValue("prices");
  expect(fetcher).toHaveBeenCalledTimes(1);
});

it("does not offer downloaded updates for practice or CSV snapshots", () => {
  setup([
    { ...price, metadata: {} },
    { ...price, id: "practice", kind: "synthetic", metadata: {} },
  ]);
  expect(
    screen.queryByRole("button", { name: "Update dataset" }),
  ).not.toBeInTheDocument();
});
