import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, expect, it, vi } from "vitest";
import ResearchManager, { DeletionDialog } from "./ResearchManager";

const preview = {
  items: [
    { kind: "result", id: "r", name: "Momentum" },
    { kind: "job", id: "j", name: "Backtest task" },
  ],
  counts: { result: 1, job: 1 },
  blockers: [],
  fingerprint: "reviewed-plan",
  requested_count: 1,
  locked_protocols: 0,
};
function mount(child: React.ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(<QueryClientProvider client={client}>{child}</QueryClientProvider>);
}
afterEach(() => vi.unstubAllGlobals());

it("requires the reviewed impact and explicit acknowledgment before deletion", async () => {
  const close = vi.fn();
  const fetcher = vi.fn().mockImplementation(async (url: string) => ({
    ok: true,
    json: async () =>
      url.endsWith("deletion-preview") ? preview : { message: "Deleted" },
  }));
  vi.stubGlobal("fetch", fetcher);
  mount(
    <DeletionDialog targets={[{ kind: "result", id: "r" }]} onClose={close} />,
  );
  const confirm = await screen.findByRole("button", {
    name: "Delete permanently",
  });
  expect(confirm).toBeDisabled();
  await screen.findByText("task record");
  expect(
    screen.getByText(
      /Paper account history, orders and approvals are protected/,
    ),
  ).toBeVisible();
  await userEvent.click(screen.getByRole("checkbox"));
  await userEvent.click(confirm);
  await waitFor(() => expect(close).toHaveBeenCalledOnce());
  const call = fetcher.mock.calls.find(
    ([url]) => url === "/api/research/delete",
  );
  expect(JSON.parse(call![1].body)).toEqual({
    targets: [{ kind: "result", id: "r" }],
    fingerprint: "reviewed-plan",
  });
});

it("blocks protected inputs and permits cancellation without a deletion request", async () => {
  const fetcher = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({
      ...preview,
      blockers: ["Dataset supports a paper trading plan."],
    }),
  });
  vi.stubGlobal("fetch", fetcher);
  const close = vi.fn();
  mount(
    <DeletionDialog targets={[{ kind: "dataset", id: "d" }]} onClose={close} />,
  );
  await screen.findByText("Dataset supports a paper trading plan.");
  expect(
    screen.getByRole("button", { name: "Delete permanently" }),
  ).toBeDisabled();
  expect(screen.queryByRole("checkbox")).toBeNull();
  await userEvent.click(screen.getByRole("button", { name: "Keep items" }));
  expect(close).toHaveBeenCalledOnce();
  expect(
    fetcher.mock.calls.some(([url]) => url === "/api/research/delete"),
  ).toBe(false);
});

it("searches, selects a filtered group and previews batch deletion", async () => {
  const items = [
    {
      kind: "result",
      id: "r1",
      category: "Backtests",
      name: "Momentum",
      detail: "Prices 2017–2026",
      created_at: "2026-11-05T12:00:00Z",
    },
    {
      kind: "result",
      id: "r2",
      category: "Backtests",
      name: "Quality",
      detail: "Prices 2017–2026",
      created_at: "2026-11-05T12:00:00Z",
    },
    {
      kind: "dataset",
      id: "d",
      category: "Datasets",
      name: "Prices",
      detail: "Saved inputs",
      created_at: "2026-11-05T12:00:00Z",
    },
  ];
  const fetcher = vi.fn().mockImplementation(async (url: string) => ({
    ok: true,
    json: async () => (url.endsWith("library") ? { items } : preview),
  }));
  vi.stubGlobal("fetch", fetcher);
  mount(<ResearchManager category="Backtests" />);
  await userEvent.click(
    screen.getByRole("button", { name: "Manage saved research" }),
  );
  await screen.findByText("Momentum");
  expect(screen.queryByText("Saved inputs")).toBeNull();
  await userEvent.type(screen.getByLabelText("Search saved items"), "momentum");
  expect(screen.queryByText("Quality")).toBeNull();
  await userEvent.click(
    screen.getByRole("checkbox", { name: "Select all shown items" }),
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Review deletion" }),
  );
  await screen.findByRole("dialog", { name: "Delete saved research?" });
  const call = fetcher.mock.calls.find(([url]) =>
    url.endsWith("deletion-preview"),
  );
  expect(JSON.parse(call![1].body).targets).toEqual([
    { kind: "result", id: "r1" },
  ]);
  expect(
    within(
      screen.getByRole("dialog", { name: "Delete saved research?" }),
    ).getByRole("button", { name: "Delete permanently" }),
  ).toBeDisabled();
});

it("explains locked protocol deletion and refuses a stale preview without retrying deletion", async () => {
  const fetcher = vi.fn().mockImplementation(async (url: string) =>
    url.endsWith("delete")
      ? {
          ok: false,
          status: 422,
          json: async () => ({
            detail:
              "Related research changed. Review a fresh deletion preview.",
          }),
        }
      : { ok: true, json: async () => ({ ...preview, locked_protocols: 1 }) },
  );
  vi.stubGlobal("fetch", fetcher);
  mount(
    <DeletionDialog
      targets={[{ kind: "protocol", id: "p" }]}
      onClose={vi.fn()}
    />,
  );
  await screen.findByText(/also retires its reserved final-test period/);
  await userEvent.click(screen.getByRole("checkbox"));
  await userEvent.click(
    screen.getByRole("button", { name: "Delete permanently" }),
  );
  await screen.findByText(/Related research changed/);
  expect(
    fetcher.mock.calls.filter(([url]) => url.endsWith("/delete")),
  ).toHaveLength(1);
  await userEvent.click(
    screen.getByRole("button", { name: "Refresh preview" }),
  );
  await waitFor(() => expect(screen.getByRole("checkbox")).not.toBeChecked());
});
