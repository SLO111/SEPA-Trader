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

export type Candle = { time: string; open: number; high: number; low: number; close: number; volume: number };

export type CandlesResponse = {
  symbol: string;
  name: string;
  sector: string;
  exchange: string;
  quote: Quote;
  delay_minutes: number;
  candles: Candle[];
};

export type StrategyParam = { key: string; label: string; default: number; min: number; max: number; step: number; type: "int" | "float" };

export type StrategyDef = { id: string; name: string; category: string; description: string; params: StrategyParam[]; requires: string | null };

export type Point = { time: string; value: number; color?: string };

export type StrategyOutput = {
  lines: { name: string; color: string; pane: "price" | "lower"; width: number; data: Point[] }[];
  histograms: { name: string; pane: "price" | "lower"; data: Point[] }[];
  markers: { time: string; position: "aboveBar" | "belowBar"; shape: "arrowUp" | "arrowDown" | "circle"; color: string; text: string }[];
  levels: { price: number; color: string; title: string }[];
};

export type ActiveStrategy = { id: string; params: Record<string, number> };

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
