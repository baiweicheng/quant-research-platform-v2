export type Strategy = {
  id: string;
  version: string;
  name: string;
  category: string;
  description: string;
  risk: string;
  inputs: string;
  implemented: boolean;
  research_only?: boolean;
  requires_annual_income?: boolean;
  requires_periodic_income?: boolean;
  frequency?: "monthly" | "weekly";
  variant_of?: string;
  definition?: string;
};
export type FundamentalCoverage = {
  normalizer?: string;
  annual_income_count?: number;
  has_periodic_captures?: boolean;
  eps_policy?: string;
  share_basis?: string;
  refresh_policy?: string;
  record_count: number;
  availability: string;
  retrieved_at: string;
  coverage: {
    symbol: string;
    records: number;
    reason: string;
    quality_ready: boolean;
    value_ready: boolean;
    annual_income_ready?: boolean;
    latest_period?: string | null;
    latest_filed?: string | null;
    available_at?: string | null;
    share_class_filings?: number;
    share_class_verified?: number;
    eps_checks?: number;
    eps_accepted?: number;
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
    median_dollar_volume?: string;
    median_dollar_volume_126?: string;
    intermediate_log_return?: number;
    relative_volatility_ratio?: number;
    sector_breadth?: number;
    beta_to_spy?: number;
    above_200_session_average?: number;
    income_growth?: number;
    cik?: string;
    form?: string;
    filed?: string;
    accession?: string;
    source_url?: string;
    concept?: string;
    period_end?: string;
    income?: string;
    prior_income?: string;
    earnings_growth?: number;
    filing_relative_return?: number;
    weak_market_relative_return?: number;
    strong_market_relative_return?: number;
    beta_126?: number;
    pullback_score?: number;
    residual_63?: number;
    residual_126?: number;
    stock_return?: number;
    daytime_relative_log_return?: number;
    overnight_followthrough_log_return?: number;
    annual_income?: {
      cik: string;
      accession: string;
      filed: string;
      end: string;
      available_at: string;
      net_income: string;
      net_income_tag: string;
      previous_net_income: string;
      previous_end: string;
    };
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
  factor_coverage?: {
    members: number;
    assessed: number;
    market_log_return_126?: number;
    sleeve?: "relative" | "pullback";
    market_regime?: {
      state: "weak" | "mixed" | "strong";
      average_gap: number;
      short_return: number;
    };
    factors: Record<
      string,
      { positive: number; nonpositive: number; unavailable: number }
    >;
  };
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
    sector_classification?: SectorAudit;
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
  strategy_id?: string;
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
  exposure?: Exposure | null;
  sector_classification?: Partial<SectorAudit> | null;
};
export type Exposure = {
  mean_stock_weight: number;
  mean_cash_weight: number;
  min_target_stock_weight: number | null;
  max_target_stock_weight: number | null;
  basis?: string;
};
export type SectorAudit = {
  version: string;
  policy: string;
  warning: string;
  classified_count: number;
  unresolved_count: number;
  not_applicable_count: number;
  unresolved_symbols: string[];
  classification_digest: string;
  captured_at: string;
  records?: Record<
    string,
    {
      symbol: string;
      sector: string | null;
      name?: string;
      method: string;
      source?: string;
      reason?: string;
      evidence_date?: string | null;
    }
  >;
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
type TradingCosts = {
  total: string;
  fees: string;
  slippage: string;
  average_bps: number | null;
  without_liquidity_data: number;
  above_one_percent_daily_volume: number;
};
export type Run = Omit<RunSummary, "metrics"> & {
  engine_version?: string;
  audit_path?: string;
  capital: string;
  dividend_model?: string;
  coverage?: {
    mode: string;
    excluded_count: number;
    universe_count?: number;
    price_window_policy?: string;
    warning?: string;
    excluded?: { symbol: string; reasons: string[] }[];
    decision_scope?: "supplemental" | "fixed_list";
    decision_exclusions?: {
      symbol: string;
      reason: string;
      decisions: number;
      first: string;
      last: string;
    }[];
  };
  frequency: string;
  notes: string[];
  source_digest: string;
  policy: Record<string, string | number>;
  execution_model: string;
  trading_costs?: { strategy: TradingCosts; benchmark: TradingCosts };
  calendar_year_returns?: {
    year: string;
    start: string;
    end: string;
    return: number;
    benchmark_return: number | null;
    difference: number | null;
  }[];
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
      return_attribution?: {
        stock_gain: string;
        trading_cost_impact: string;
        net_change: string;
        stock_return: number;
        trading_cost_contribution: number;
        net_return: number;
        benchmark_gross_return?: number;
      };
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
  factor_coverage?: Decision["factor_coverage"];
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
