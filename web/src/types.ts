export type Strategy = {
  id: string;
  version: string;
  name: string;
  category: string;
  description: string;
  risk: string;
  inputs: string;
  implemented: boolean;
  definition?: string;
};
export type FundamentalCoverage = {
  record_count: number;
  availability: string;
  retrieved_at: string;
  coverage: {
    symbol: string;
    records: number;
    reason: string;
    quality_ready: boolean;
    value_ready: boolean;
    latest_period?: string | null;
    latest_filed?: string | null;
    available_at?: string | null;
  }[];
};
export type Signal = {
  symbol: string;
  score: number;
  components: {
    profitability?: string;
    earnings_yield?: string;
    momentum?: number;
    eps_asof?: string;
    percentiles?: Record<string, number>;
    filing?: {
      start: string;
      end: string;
      filed: string;
      available_at: string;
      accession: string;
      url: string;
      sources: Record<string, string>;
      issues: string[];
    };
  };
};
export type Decision = {
  session: string;
  execute_session: string;
  eligible: number;
  signals?: Signal[];
  exclusions?: { symbol: string; reason: string }[];
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
    fundamentals?: FundamentalCoverage;
    coverage?: {
      symbol: string;
      rows: number;
      expected: number;
      missing_count: number;
      missing_examples: string[];
      reason?: string | null;
      start: string | null;
      end: string | null;
    }[];
    unavailable_symbols?: Record<string, string>;
    validation_issues?: string[];
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
  coverage?: { mode: string; excluded_count: number };
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
  account: {
    connected: boolean;
    planning_capital: string;
    mode: string;
    snapshot?: import("./Paper").PaperSnapshot | null;
  };
};
export const PERIODS = ["1W", "1M", "3M", "6M", "YTD", "1Y", "All"] as const;
export type Period = (typeof PERIODS)[number];
export type Run = Omit<RunSummary, "metrics"> & {
  audit_path?: string;
  capital: string;
  dividend_model?: string;
  coverage?: {
    mode: string;
    excluded_count: number;
    universe_count?: number;
    warning?: string;
    excluded?: { symbol: string; reasons: string[] }[];
  };
  frequency: string;
  notes: string[];
  source_digest: string;
  policy: Record<string, string | number>;
  execution_model: string;
  benchmark_model: string;
  decisions?: Decision[];
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
  signals?: Signal[];
  capital: string;
  cash_weight: string;
  targets: {
    symbol: string;
    weight: string;
    sector: string;
    components?: Signal["components"];
  }[];
  excluded: { symbol: string; reason: string }[];
  eligible: number;
  notes: string[];
  status: string;
  source_digest: string;
};
