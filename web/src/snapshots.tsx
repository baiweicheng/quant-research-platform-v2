import type { Dataset } from "./types";

export function snapshotName(dataset: Dataset) {
  return dataset.metadata?.price_dataset_id && dataset.name.endsWith(" + SEC")
    ? dataset.name.slice(0, -6)
    : dataset.name;
}

export function snapshotFamily(dataset: Dataset) {
  if (dataset.metadata?.series_id) return String(dataset.metadata.series_id);
  const meta = dataset.metadata ?? {};
  const audit = meta.membership as
    { mode?: string; additional_symbols?: string[] } | undefined;
  const download = meta.download as
    { start?: string; symbols?: string[] } | undefined;
  return JSON.stringify([
    dataset.kind,
    meta.provider,
    snapshotName(dataset),
    download?.start ?? dataset.start,
    audit ? "sp500" : "custom",
    [
      ...(audit?.additional_symbols ??
        download?.symbols ??
        dataset.symbols ??
        []),
    ].sort(),
  ]);
}

export function snapshotGroups(datasets: Dataset[]) {
  const families = new Map<string, Dataset[]>();
  const internalPrices = new Set(
    datasets
      .filter((d) => d.metadata?.bundle_role === "prices")
      .map((d) => d.id),
  );
  const parents = new Set(
    datasets.flatMap((d) => [
      d.metadata?.price_dataset_id,
      internalPrices.has(String(d.metadata?.sector_parent_dataset_id))
        ? d.metadata?.sector_parent_dataset_id
        : undefined,
    ]),
  );
  for (const dataset of datasets.filter((d) => !parents.has(d.id))) {
    const key = snapshotFamily(dataset);
    families.set(key, [...(families.get(key) ?? []), dataset]);
  }
  const latest: Dataset[] = [];
  const older: Dataset[] = [];
  for (const family of families.values()) {
    const complete = family.filter(
      (dataset) =>
        dataset.metadata?.fundamentals ||
        dataset.metadata?.provider !== "alpaca",
    );
    const candidates = complete.length ? complete : family;
    const newest = [...candidates].sort(
      (a, b) =>
        b.end.localeCompare(a.end) || b.created_at.localeCompare(a.created_at),
    )[0];
    latest.push(newest);
    older.push(...family.filter((dataset) => dataset.id !== newest.id));
  }
  const byDate = (a: Dataset, b: Dataset) =>
    b.created_at.localeCompare(a.created_at);
  return { latest: latest.sort(byDate), older: older.sort(byDate) };
}

export function snapshotLabel(dataset: Dataset) {
  return `${snapshotName(dataset)} · through ${dataset.end} · saved ${dataset.created_at ? new Date(dataset.created_at).toLocaleString() : "capture time unavailable"}`;
}

export function researchSnapshots(datasets: Dataset[]) {
  return datasets.filter((d) => d.metadata?.bundle_role !== "prices");
}

export function SnapshotOptions({ datasets }: { datasets: Dataset[] }) {
  const { latest, older } = snapshotGroups(researchSnapshots(datasets));
  return (
    <>
      <optgroup label="Latest snapshots">
        {latest.map((dataset) => (
          <option key={dataset.id} value={dataset.id}>
            {snapshotLabel(dataset)}
            {dataset.kind === "synthetic" ? " · Practice" : ""}
          </option>
        ))}
      </optgroup>
      {!!older.length && (
        <optgroup label="Older snapshots · reproduce earlier research">
          {older.map((dataset) => (
            <option key={dataset.id} value={dataset.id}>
              {snapshotLabel(dataset)}
              {!dataset.metadata?.fundamentals &&
              dataset.metadata?.provider === "alpaca"
                ? " · Legacy prices only"
                : ""}
            </option>
          ))}
        </optgroup>
      )}
    </>
  );
}

export function aliasActionGaps(dataset: Dataset) {
  const evidence = dataset.metadata?.identity_resolution;
  if (!evidence || typeof evidence !== "object") return [];
  return Object.entries(evidence)
    .filter(
      ([, value]) =>
        value &&
        typeof value === "object" &&
        "reviewed_alias" in value &&
        !(
          "original_actions_reconciled" in value &&
          value.original_actions_reconciled
        ),
    )
    .map(([symbol]) => symbol)
    .sort();
}

export function mergerActionGaps(dataset: Dataset) {
  const events = dataset.metadata?.corporate_actions;
  if (!Array.isArray(events)) return [];
  return [
    ...new Set(
      events
        .filter(
          (e) =>
            e &&
            typeof e === "object" &&
            (e.unpriced_consideration ||
              (e.kind === "cash_mergers" &&
                Number(e.cash ?? 0) <= 0 &&
                !e.reviewed_evidence?.zero_recovery) ||
              (["stock_mergers", "stock_and_cash_mergers"].includes(e.kind) &&
                !(Array.isArray(e.targets) && e.targets.length) &&
                (!e.target || Number(e.ratio ?? 0) <= 0))),
        )
        .map((e) => String(e.source)),
    ),
  ].sort();
}

export function reviewedActionCorrections(dataset: Dataset) {
  const events = dataset.metadata?.corporate_actions;
  if (!Array.isArray(events)) return [];
  return events
    .filter(
      (event) =>
        [
          "identity_continuations",
          "reviewed_splits",
          "reviewed_separations",
          "reviewed_distributions",
          "reviewed_lifetimes",
          "cash_mergers",
          "stock_mergers",
          "stock_and_cash_mergers",
          "rejected_native_merger",
        ].includes(event?.kind) &&
        typeof (
          event.reviewed_evidence ??
          event.reviewed_market_timing ??
          event.reviewed_rejection
        )?.url === "string",
    )
    .map((event) => {
      const evidence =
        event.reviewed_evidence ??
        event.reviewed_market_timing ??
        event.reviewed_rejection;
      return {
        symbol: String(event.source),
        effective:
          event.kind === "rejected_native_merger"
            ? `Rejected ${event.effective}`
            : String(event.effective),
        url: String(evidence.url),
        basis: String(evidence.basis),
      };
    });
}
