import type { Dataset } from "./types";

export function datasetLabel(dataset: Dataset, all: Dataset[]) {
  if (all.filter((d) => d.name === dataset.name).length < 2)
    return dataset.name;
  return `${dataset.name} · ${dataset.start}–${dataset.end} · saved ${new Date(dataset.created_at).toLocaleString()}`;
}

export async function api<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(
    `/api${path}`,
    body === undefined
      ? undefined
      : {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Aperture-Client": "1",
          },
          body: JSON.stringify(body),
        },
  );
  if (!response.ok) {
    let message = `The local service returned ${response.status}. Please try again.`;
    try {
      const result = await response.json();
      if (typeof result.detail === "string") message = result.detail;
      else if (Array.isArray(result.detail))
        message = result.detail.map((e: { msg: string }) => e.msg).join(". ");
    } catch {
      /* Keep the actionable HTTP fallback. */
    }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

export const money = (value: string | number) =>
  new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  }).format(Number(value));
export const percent = (value: number | null | undefined, signed = false) =>
  value == null
    ? "—"
    : `${signed && value > 0 ? "+" : ""}${(value * 100).toFixed(2)}%`;
export const points = (value: number | null | undefined) =>
  value == null ? "—" : `${value > 0 ? "+" : ""}${(value * 100).toFixed(2)} pp`;
export const shortDate = (value: string) =>
  new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${value.slice(0, 10)}T12:00:00Z`));
export function download(name: string, data: unknown) {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }),
  );
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = name;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
