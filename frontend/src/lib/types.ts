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

export type StrategyDef = { id: string; name: string; category: string; description: string; params: StrategyParam[] };

export type Point = { time: string; value: number; color?: string };

export type StrategyOutput = {
  lines: { name: string; color: string; pane: "price" | "lower"; width: number; data: Point[] }[];
  histograms: { name: string; pane: "price" | "lower"; data: Point[] }[];
  markers: { time: string; position: "aboveBar" | "belowBar"; shape: "arrowUp" | "arrowDown" | "circle"; color: string; text: string }[];
  levels: { price: number; color: string; title: string }[];
};

export type ActiveStrategy = { id: string; params: Record<string, number> };
