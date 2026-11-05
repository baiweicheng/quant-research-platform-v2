import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, expect, it, vi } from "vitest";
import SectorCoverage from "./Sectors";
import { FundamentalsPanel } from "./Fundamentals";
import { MemoryRouter } from "react-router-dom";
import type { Dataset, SectorAudit } from "./types";

afterEach(() => vi.unstubAllGlobals());

it("does not offer SEC completion for an already completed sector-price chain", () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({
      ok: true,
      json: async () => ({ sec_configured: true }),
    })),
  );
  const raw = {
    id: "raw",
    name: "Research",
    kind: "imported",
    start: "2016-01-04",
    end: "2026-11-04",
    created_at: "2026-11-05T00:00:00Z",
    symbols: ["ABC"],
    row_count: 1,
    symbol_count: 1,
    source: "Fixture",
    digest: "digest",
    warnings: [],
    metadata: { provider: "alpaca", bundle_role: "prices" },
  } as Dataset;
  const sector = {
    ...raw,
    id: "sector",
    metadata: { ...raw.metadata, sector_parent_dataset_id: raw.id },
  };
  const complete = {
    ...raw,
    id: "complete",
    metadata: {
      ...raw.metadata,
      bundle_role: "complete",
      price_dataset_id: sector.id,
      fundamentals: {
        record_count: 1,
        availability: "Fixture",
        retrieved_at: "2026-11-05T00:00:00Z",
        coverage: [],
      },
    },
  } as Dataset;
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <FundamentalsPanel datasets={[raw, sector, complete]} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  expect(
    screen.queryByRole("heading", { name: "Complete SEC download" }),
  ).not.toBeInTheDocument();
});
it("loads source evidence on demand and searches every classification", async () => {
  const audit = {
    classified_count: 2,
    unresolved_count: 1,
    not_applicable_count: 1,
    unresolved_symbols: ["MISSING"],
    captured_at: "2026-11-05T12:00:00Z",
    warning: "Current and last-known static sector proxies.",
    records: {
      ABC: {
        symbol: "ABC",
        sector: "Health Care",
        method: "dated_public_classification",
        source: "https://example.com/source",
      },
      REVIEW: {
        symbol: "REVIEW",
        sector: "Energy",
        method: "reviewed_business_proxy",
      },
      MISSING: { symbol: "MISSING", sector: "Unknown", method: "unresolved" },
      SPY: { symbol: "SPY", sector: null, method: "not_applicable" },
    },
  } as unknown as SectorAudit;
  const fetcher = vi.fn(async () => ({ ok: true, json: async () => audit }));
  vi.stubGlobal("fetch", fetcher);
  render(
    <QueryClientProvider client={new QueryClient()}>
      <SectorCoverage
        dataset={
          {
            id: "data",
            kind: "imported",
            metadata: { sector_classification: audit },
          } as Dataset
        }
      />
    </QueryClientProvider>,
  );
  expect(fetcher).not.toHaveBeenCalled();
  await userEvent.click(screen.getByText(/Sector coverage/));
  expect(await screen.findByText("ABC")).toBeVisible();
  expect(screen.getByText("Reviewed issuer-business proxy")).toBeVisible();
  expect(screen.getByText("Not applicable")).toBeVisible();
  await userEvent.type(
    screen.getByLabelText("Find a sector classification"),
    "ABC",
  );
  expect(screen.queryByText("REVIEW")).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Source" })).toHaveAttribute(
    "href",
    "https://example.com/source",
  );
});
