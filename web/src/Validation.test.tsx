import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, expect, it, vi } from "vitest";
import Validation from "./Validation";
import type { State } from "./types";
const state = {
  datasets: [
    { id: "d", name: "Prices", start: "2022-01-03", end: "2026-11-02" },
  ],
  strategies: [{ id: "momentum", name: "Momentum", version: "1.0.0" }],
} as State;
const protocol = {
  id: "p",
  name: "Study",
  hypothesis: "Test persistence",
  dataset_name: "Prices",
  strategy: { name: "Momentum", version: "1.0.0" },
  start: "2023-01-03",
  development_end: "2025-12-31",
  holdout_start: "2026-01-02",
  end: "2026-11-02",
  holdout_state: "locked",
  holdout_label: "Previously explored period",
  prior_exposures: ["old"],
  fingerprint: "abc",
};
function mount() {
  render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <Validation state={state} />
    </QueryClientProvider>,
  );
}
afterEach(() => vi.unstubAllGlobals());
it("requires explicit final-test release and shows earlier exposure", async () => {
  const fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({
      protocols: [protocol],
      trials: [],
      workspace_attempts: 5,
    }),
  });
  vi.stubGlobal("fetch", fetch);
  mount();
  const release = await screen.findByRole("button", {
    name: "Release final test once",
  });
  expect(release).toBeDisabled();
  expect(screen.getByText(/1 prior overlapping attempts/)).toBeVisible();
  await userEvent.click(screen.getByRole("checkbox"));
  await userEvent.click(release);
  expect(fetch).toHaveBeenCalledWith(
    "/api/research/protocols/p/evaluate",
    expect.objectContaining({
      body: JSON.stringify({ phase: "holdout", acknowledge: true }),
    }),
  );
});
it("submits the exact form dates rather than stale display state", async () => {
  const fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ protocols: [], trials: [], workspace_attempts: 0 }),
  });
  vi.stubGlobal("fetch", fetch);
  mount();
  await userEvent.type(
    screen.getByLabelText("Protocol name"),
    "Independent review",
  );
  await userEvent.type(
    screen.getByLabelText("Research hypothesis"),
    "Test this hypothesis.",
  );
  fireEvent.change(screen.getByLabelText("Development start"), {
    target: { value: "2023-02-01" },
  });
  await userEvent.click(
    screen.getByRole("button", { name: "Freeze protocol" }),
  );
  const call = fetch.mock.calls.find(
    (c) => c[0] === "/api/research/protocols" && c[1],
  );
  expect(JSON.parse(call![1].body).start).toBe("2023-02-01");
});
