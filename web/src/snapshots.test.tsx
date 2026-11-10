import { expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import {
  snapshotGroups,
  SnapshotOptions,
  reviewedActionCorrections,
} from "./snapshots";
import { afterWarmup, ResearchCoverageChoice } from "./dialogs";
import type { Dataset } from "./types";

function snapshot(n: number, extra = {}) {
  return {
    id: `d${n}`,
    name: "S&P 500",
    kind: "imported",
    start: "2016-01-04",
    end: `2026-11-${String(n).padStart(2, "0")}`,
    created_at: `2026-11-${String(n).padStart(2, "0")}T23:00:00Z`,
    symbols: ["ABC"],
    row_count: 100,
    symbol_count: 1,
    source: "Fixture",
    digest: "hash",
    warnings: [],
    metadata: {
      provider: "alpaca",
      series_id: "index",
      fundamentals: {
        record_count: 1,
        coverage: [],
        availability: "Fixture",
        retrieved_at: "2026-11-01T23:00:00Z",
      },
      ...extra,
    },
  } as Dataset;
}
it("keeps twenty versions in one family and omits completed internal price parents", () => {
  const rows = Array.from({ length: 20 }, (_, n) => snapshot(n + 1));
  const parent = {
    ...snapshot(20),
    id: "price-parent",
    metadata: { provider: "alpaca", series_id: "index" },
  } as Dataset;
  rows[19].metadata!.price_dataset_id = parent.id;
  const groups = snapshotGroups([...rows, parent]);
  expect(groups.latest.map((d) => d.id)).toEqual(["d20"]);
  expect(groups.older).toHaveLength(19);
});
it("shows latest and older snapshots in separate option groups", () => {
  render(
    <select>
      <SnapshotOptions datasets={[snapshot(1), snapshot(2)]} />
    </select>,
  );
  expect(
    screen.getByRole("group", { name: "Latest snapshots" }),
  ).toHaveTextContent("through 2026-11-02");
  expect(
    screen.getByRole("group", { name: /Older snapshots/ }),
  ).toHaveTextContent("through 2026-11-01");
});
it("does not replace a complete snapshot with an unfinished later SEC stage", () => {
  const incomplete = snapshot(2, {
    fundamentals: undefined,
    bundle_role: "prices",
  });
  expect(snapshotGroups([snapshot(1), incomplete]).latest[0].id).toBe("d1");
});
it("keeps distinct saved data series selectable", () => {
  expect(
    snapshotGroups([snapshot(1), snapshot(2, { series_id: "custom" })]).latest,
  ).toHaveLength(2);
});

it("hides intermediate classification price parents while retaining older complete research", () => {
  const old = snapshot(1);
  const raw = snapshot(2, { fundamentals: undefined, bundle_role: "prices" });
  const sectors = {
    ...raw,
    id: "sectors",
    metadata: { ...raw.metadata, sector_parent_dataset_id: raw.id },
  };
  const complete = {
    ...snapshot(3),
    metadata: { ...snapshot(3).metadata, price_dataset_id: sectors.id },
  };
  const groups = snapshotGroups([old, raw, sectors, complete]);
  expect(groups.latest.map((d) => d.id)).toEqual([complete.id]);
  expect(groups.older.map((d) => d.id)).toEqual([old.id]);
});
it("defaults January data to January of the following year", () => {
  expect(afterWarmup("2016-01-04", "2026-11-04")).toBe("2017-01-01");
  expect(afterWarmup("2026-10-01", "2026-11-04")).toBe("2026-10-01");
});
it("makes both approved coverage policies explicit", () => {
  render(<ResearchCoverageChoice />);
  expect(screen.getByLabelText("Data coverage policy")).toHaveValue(
    "coverage_limited",
  );
  expect(screen.getByRole("option", { name: /Strict coverage/ })).toHaveValue(
    "strict",
  );
  expect(screen.getByText(/survivorship and selection bias/)).toBeVisible();
});

it("shows primary-source merger corrections without labeling bare vendor events as reviewed", () => {
  const kinds = [
    "identity_continuations",
    "reviewed_splits",
    "cash_mergers",
    "stock_mergers",
    "stock_and_cash_mergers",
  ];
  const events = kinds.map((kind, i) => ({
    kind,
    source: `SOURCE${i}`,
    effective: "2020-01-02",
    reviewed_evidence: {
      url: `https://www.sec.gov/filing${i}`,
      basis: "Completed transaction",
    },
  }));
  const rows = reviewedActionCorrections(
    snapshot(1, {
      corporate_actions: [
        ...events,
        { kind: "cash_mergers", source: "UNREVIEWED", cash: "10" },
      ],
    }),
  );
  expect(rows.map((r) => r.symbol)).toEqual(events.map((e) => e.source));
  expect(rows.every((r) => r.basis === "Completed transaction")).toBe(true);
});

it("shows reviewed trading-session timing with its primary filing", () => {
  const rows = reviewedActionCorrections(
    snapshot(1, {
      corporate_actions: [
        {
          kind: "cash_mergers",
          source: "NLSN",
          effective: "2022-10-12",
          reviewed_market_timing: {
            url: "https://www.sec.gov/Archives/nielsen.htm",
            basis: "Suspend before October 12 open after October 11 closing.",
          },
        },
        { kind: "cash_mergers", source: "BARE", effective: "2022-10-11" },
      ],
    }),
  );
  expect(rows).toEqual([
    {
      symbol: "NLSN",
      effective: "2022-10-12",
      url: "https://www.sec.gov/Archives/nielsen.htm",
      basis: "Suspend before October 12 open after October 11 closing.",
    },
  ]);
});

it("labels a rejected vendor merger separately from an executed conversion", () => {
  const rows = reviewedActionCorrections(
    snapshot(1, {
      corporate_actions: [
        {
          kind: "rejected_native_merger",
          source: "HES",
          effective: "2024-09-30",
          reviewed_rejection: {
            url: "https://www.sec.gov/Archives/hess-closing.htm",
            basis:
              "Stale instruction; the actual conversion occurred in July 2025.",
          },
        },
      ],
    }),
  );
  expect(rows).toEqual([
    {
      symbol: "HES",
      effective: "Rejected 2024-09-30",
      url: "https://www.sec.gov/Archives/hess-closing.htm",
      basis: "Stale instruction; the actual conversion occurred in July 2025.",
    },
  ]);
});

it("shows source-backed separation economics alongside merger corrections", () => {
  expect(
    reviewedActionCorrections(
      snapshot(1, {
        corporate_actions: [
          {
            kind: "reviewed_separations",
            source: "DWDP",
            effective: "2019-06-03",
            reviewed_evidence: {
              url: "https://www.sec.gov/Archives/corteva.htm",
              basis:
                "One new parent and one Corteva share for every three old shares.",
            },
          },
        ],
      }),
    ),
  ).toEqual([
    {
      symbol: "DWDP",
      effective: "2019-06-03",
      url: "https://www.sec.gov/Archives/corteva.htm",
      basis: "One new parent and one Corteva share for every three old shares.",
    },
  ]);
});
