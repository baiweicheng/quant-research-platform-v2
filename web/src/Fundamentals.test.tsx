import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it } from "vitest";
import { FundamentalDetails } from "./Fundamentals";

it("labels structured EPS as usable assumptions rather than verified classes", async () => {
  render(
    <FundamentalDetails
      data={{
        eps_policy: "structured-eps-v1",
        share_basis:
          "Share-class comparability is assumed; known unequal shares are excluded.",
        refresh_policy: "New annual filings trigger refresh.",
        record_count: 12,
        availability: "After the recorded filing date",
        retrieved_at: "2026-11-09T17:00:00Z",
        coverage: [
          {
            symbol: "ABC",
            records: 12,
            quality_ready: true,
            value_ready: true,
            reason: "",
            eps_checks: 10,
            eps_accepted: 9,
          },
          {
            symbol: "UNMAPPED",
            records: 0,
            quality_ready: false,
            value_ready: false,
            reason: "No unique SEC issuer mapping.",
          },
        ],
      }}
    />,
  );
  await userEvent.click(screen.getByText(/SEC filing coverage/));
  expect(screen.getByText(/Unavailable · see coverage notes/)).toBeVisible();
  expect(screen.queryByText(/Legacy snapshot/)).not.toBeInTheDocument();
  expect(screen.getByText(/9 \/ 10 accessions usable/)).toBeVisible();
  expect(
    screen.getByText(/Share-class comparability is assumed/),
  ).toBeVisible();
  expect(
    screen.queryByText(/supported filings|verified classes/),
  ).not.toBeInTheDocument();
});
