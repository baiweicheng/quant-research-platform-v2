export type Strategy = {
  id: string;
  version: string;
  name: string;
  category: string;
  description: string;
  risk: string;
  inputs: string;
  implemented: boolean;
};
export type Dataset = {
  id: string;
  name: string;
  kind: "imported" | "synthetic";
  start: string;
  end: string;
  symbols: string[];
  row_count: number;
  symbol_count: number;
  source: string;
  digest: string;
  warnings: string[];
  created_at: string;
  metadata?: {
    provider?: string;
    feed?: string;
    retrieved_at?: string;
    action_count?: number;
    coverage?: {
      symbol: string;
      rows: number;
      expected: number;
      missing_count: number;
      missing_examples: string[];
      start: string;
      end: string;
    }[];
    [key: string]: unknown;
  };
};
export type Job = {
  id: string;
  kind: string;
  state: "queued" | "running" | "complete" | "failed";
  progress: number;
  message: string;
  created_at: string;
  updated_at: string;
  result_id: string | null;
};
export type Metrics = {
  return: number | null;
  benchmark_return: number | null;
  difference: number | null;
  drawdown: number | null;
  volatility: number | null;
  cagr: number | null;
};
export type RunSummary = {
  id: string;
  created_at: string;
  dataset_id: string;
  dataset_name: string;
  dataset_kind: string;
  strategy: Strategy;
  start: string;
  end: string;
  trade_count: number;
  metrics: Metrics;
};
export type ReviewSummary = {
  id: string;
  created_at: string;
  dataset_name: string;
  dataset_kind: string;
  strategy: Strategy;
  decision_session: string;
  execute_session: string;
};
export type State = {
  version: string;
  datasets: Dataset[];
  strategies: Strategy[];
  jobs: Job[];
  runs: RunSummary[];
  reviews: ReviewSummary[];
  account: { connected: false; planning_capital: string; mode: string };
};
export const PERIODS = ["1W", "1M", "3M", "6M", "YTD", "1Y", "All"] as const;
export type Period = (typeof PERIODS)[number];
export type Run = Omit<RunSummary, "metrics"> & {
  capital: string;
  frequency: string;
  notes: string[];
  source_digest: string;
  policy: Record<string, string | number>;
  execution_model: string;
  benchmark_model: string;
  curve: {
    session: string;
    equity: string;
    cash: string;
    receivable: string;
    benchmark: string | null;
  }[];
  windows: Record<
    Period,
    {
      start: string;
      end: string;
      start_index: number;
      limited: boolean;
      metrics: Metrics;
    }
  >;
  trades: {
    session: string;
    symbol: string;
    side: string;
    quantity: string;
    price: string;
    fee: string;
  }[];
  holdings: {
    symbol: string;
    quantity: string;
    value: string;
    weight: number;
  }[];
};
export type Review = ReviewSummary & {
  capital: string;
  cash_weight: string;
  targets: { symbol: string; weight: string; sector: string }[];
  excluded: { symbol: string; reason: string }[];
  eligible: number;
  notes: string[];
  status: string;
  source_digest: string;
};
