export type PlanLimits = {
  label: string;
  max_watchlists: number;
  max_symbols_per_watchlist: number;
  max_strategies_on_chart: number;
  max_portfolios: number;
  realtime_data: boolean;
  data_delay_minutes: number;
  alerts: boolean;
  reports: boolean;
  move_detector: boolean;
  backtesting: boolean;
  trade_review: boolean;
  max_journal_trades: number;
  max_alert_rules: number;
};

export type User = {
  id: number;
  email: string;
  name: string;
  role: "user" | "admin";
  plan: "free" | "pro" | "premium";
  limits: PlanLimits;
  created_at: string;
  is_active?: boolean;
  subscription_status?: string | null;
};

export type Watchlist = { id: number; name: string; color: string; symbols: string[] };

export type Quote = {
  symbol: string;
  price?: number;
  change?: number;
  change_pct?: number;
  volume?: number;
  date?: string;
  error?: string;
};

export type Candle = { time: string | number; open: number; high: number; low: number; close: number; volume: number; session?: "pre" | "regular" | "post" };

export type CandlesResponse = {
  symbol: string;
  name: string;
  sector: string;
  exchange: string;
  quote: Quote;
  delay_minutes: number;
  live_at?: string | null;
  candles: Candle[];
};

export type StrategyParam = { key: string; label: string; default: number; min: number; max: number; step: number; type: "int" | "float" | "select"; options?: [number, string][] | null };

export type StrategyDef = { id: string; name: string; category: string; description: string; params: StrategyParam[]; requires: string | null };

export type Point = { time: string | number; value: number; color?: string };

export type StrategyOutput = {
  lines: { name: string; color: string; pane: "price" | "lower"; width: number; data: Point[] }[];
  histograms: { name: string; pane: "price" | "lower"; data: Point[] }[];
  markers: { time: string | number; position: "aboveBar" | "belowBar"; shape: "arrowUp" | "arrowDown" | "circle"; color: string; text: string }[];
  levels: { price: number; color: string; title: string }[];
};

// uid: one entry per instance, so the same indicator can be on the chart several times.
export type ActiveStrategy = { uid: string; id: string; params: Record<string, number>; hidden?: boolean };

export type SymbolInfo = {
  symbol: string; name: string; exchange: string; sector: string; industry: string;
  quote: Quote; live_at: string | null;
  day: { open: number; high: number; low: number };
  week52: { high: number; low: number };
  volume: { today: number; avg_50d: number; relative: number | null };
  stats: { market_cap_b: number | null; pe: number | null; dividend_yield: number | null; eps_growth: number | null; beta: number | null };
  next_earnings: string | null;
  extended: { session: "pre_market" | "after_hours"; price: number; change: number; change_pct: number; reference_close: number; time: string } | null;
  overnight: null;
  sepa: { rs_rating: number | null; template_passed: number; vcp: boolean; pivot: number | null; bull_score: number; bear_score: number; signals: string[] } | null;
};

export type Factor = { key: string; label: string; value: number; weight: number; contribution: number };
export type ScoreBlock = { score: number | null; label: string; factors: Factor[] };

export type SepaReport = {
  symbol: string;
  rs_rating: number | null;
  trend_template: { criteria: { label: string; passed: boolean }[]; passed_count: number; all_passed: boolean };
  vcp: {
    detected: boolean;
    reason?: string;
    contractions: { start: string; end: string; high: number; low: number; depth_pct: number }[];
    pivot?: number;
    stop?: number;
    risk_pct?: number;
    distance_pct?: number;
    checks?: Record<string, boolean>;
  };
  move_detector: { bull: ScoreBlock; bear: ScoreBlock } | null;
};

export type ScanRow = {
  symbol: string;
  name: string;
  sector: string;
  price: number;
  change_pct: number;
  rs_rating: number | null;
  template_passed: number;
  vcp: boolean;
  pivot: number | null;
  pivot_distance_pct: number | null;
  bull_score: number;
  bear_score: number;
  signals: string[];
};

export type Severity = "bull" | "bear" | "info";

export type AlertItem = {
  id: number;
  rule_id: number | null;
  symbol: string;
  type: string;
  type_label: string;
  severity: Severity;
  title: string;
  message: string;
  data: Record<string, number>;
  bar_date: string;
  read: boolean;
  created_at: string;
};

export type EventType = { id: string; label: string; severity: Severity; description: string };

export type EventCatalog = { events: EventType[]; defaults: string[]; channels: { app: boolean; email: boolean; telegram: boolean } };

export type Channel = "app" | "email" | "telegram";

export type AlertRule = {
  id: number;
  name: string;
  scope: "symbol" | "watchlist" | "universe";
  symbol: string | null;
  watchlist_id: number | null;
  events: string[];
  price_level: number | null;
  bull_threshold: number;
  bear_threshold: number;
  channels: Channel[];
  active: boolean;
  auto?: boolean;
  created_at: string;
};

export type NotifySettings = {
  email: string;
  email_enabled: boolean;
  telegram_enabled: boolean;
  telegram_chat_id: string;
  email_available: boolean;
  telegram_available: boolean;
};

export type ProfileKey =
  | "aggressive" | "growth" | "momentum" | "conservative" | "dividend" | "value"
  | "blue_chip" | "defensive" | "small_cap" | "speculative" | "balanced" | "concentrated";

export type ClassificationBrief = { primary: ProfileKey | null; label: string; secondary: ProfileKey[]; risk_level: number | null };

export type Classification = ClassificationBrief & {
  scores: { key: ProfileKey; label: string; description: string; score: number }[];
  insights: string[];
  sectors: { sector: string; weight: number }[];
};

export type PortfolioSummary = {
  id: number;
  name: string;
  description: string;
  template_id: string | null;
  created_at: string;
  positions_count: number;
  value: number;
  cost: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number | null;
  realized_pnl: number;
  day_change: number;
  day_change_pct: number | null;
  classification: ClassificationBrief;
  symbols: string[];
};

export type Holding = {
  symbol: string; name: string; sector: string; shares: number; avg_cost: number; price: number; value: number; cost: number;
  pnl: number; pnl_pct: number | null; day_change: number; day_change_pct: number; weight: number;
  beta: number | null; dividend_yield: number | null; pe: number | null;
};

export type PortfolioTxn = { id: number; date: string; symbol: string; side: "buy" | "sell"; shares: number; price: number; fees: number };

export type PortfolioDetail = Omit<PortfolioSummary, "classification"> & {
  classification: Classification;
  positions: Holding[];
  dividends: { date: string; symbol: string; per_share: number; shares: number; amount: number }[];
  dividends_total: number;
  transactions: PortfolioTxn[];
};

export type Performance = {
  period: string;
  start?: string;
  end?: string;
  series: { time: string; portfolio: number; benchmark?: number }[];
  portfolio_return: number | null;
  benchmark_return: number | null;
  start_value: number;
  end_value: number;
  pnl: number;
};

export type PortfolioTemplate = {
  id: string; name: string; profile: ProfileKey; risk: number; description: string; symbols: string[];
  detected: { label: string; risk_level: number | null; dividend_yield: number | null };
};

export type FinRow = Record<string, number | string | null> & { period: string };

export type Company = {
  symbol: string; name: string; sector: string; industry: string; exchange: string; currency: string; demo: boolean;
  profile: { description: string; website: string | null; employees: number | null; headquarters: string | null };
  stats: { market_cap_b?: number | null; shares_outstanding_m?: number | null; beta?: number | null; week52_high?: number | null; week52_low?: number | null; avg_volume?: number | null; eps_ttm?: number | null };
  valuation: { pe?: number | null; forward_pe?: number | null; peg?: number | null; ps?: number | null; pb?: number | null; ev_ebitda?: number | null };
  profitability: { gross_margin?: number | null; operating_margin?: number | null; net_margin?: number | null; roe?: number | null; roa?: number | null; revenue_growth?: number | null; eps_growth?: number | null };
  health: { cash_b?: number | null; debt_b?: number | null; debt_to_equity?: number | null; current_ratio?: number | null };
  dividends: { yield: number | null; annual: number | null; payout_ratio: number | null; ex_date: string | null; history: { date: string; amount: number }[] };
  financials: { annual: FinRow[]; quarterly: FinRow[] };
  earnings: { next_date: string | null; history: { date: string; eps_estimate: number | null; eps_actual: number | null; surprise_pct: number | null }[] };
  analysts: { rating: string | null; score: number | null; counts: Record<string, number>; total: number; target_mean: number | null; target_high: number | null; target_low: number | null; upside_pct: number | null } | null;
  ownership: {
    institutional_pct: number | null; insider_pct: number | null;
    top_holders: { name: string; pct: number | null; shares: number | null; value: number | null }[];
    insider_transactions: { date: string | null; insider: string; position: string; transaction: string; shares: number | null; value: number | null }[];
  };
  news: { title: string; url: string; publisher: string | null; published: string | null }[];
};

export type Peer = { symbol: string; name: string; price: number; change_pct: number; market_cap_b: number | null; pe: number | null; dividend_yield: number | null; rs_rating: number | null };

export type StockData = {
  company: Company;
  quote: Quote;
  returns: Record<string, number | null>;
  sepa: SepaReport;
  peers: Peer[];
  takeaways: { tone: "positive" | "negative" | "neutral"; text: string }[];
  verdict: string;
  key_facts?: { facts: string[]; headline: { title: string; url: string | null; publisher: string | null } | null };
};
