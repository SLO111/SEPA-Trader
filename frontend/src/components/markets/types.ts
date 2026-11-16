export type FearGreed = {
  score: number | null;
  label: string;
  as_of?: string;
  previous: { close: number | null; week: number | null; month: number | null; year: number | null };
  components?: { key: string; label: string; description: string; score: number; rating: string; value: number }[];
  history?: { time: string; value: number }[];
};

export type MoverRow = {
  symbol: string; name: string; sector: string; price: number; change: number; change_pct: number; volume: number;
  rel_volume: number | null; dollar_volume: number; from_high_pct: number; rsi14: number; above_ma50: boolean;
  return_1w: number; return_1m: number; return_3m: number | null;
};

export type SectorRow = {
  sector: string; stocks: number; change_pct: number | null; return_1w: number | null; return_1m: number | null; return_3m: number | null;
  avg_rs: number | null; pct_above_ma50: number; leaders: string[]; rank_1m: number; rank_3m: number; trend: "Improving" | "Weakening" | "Steady"; emerging: boolean;
};

export type LeaderRow = { symbol: string; name: string; price: number; change_pct: number; rs_rating: number; bull_score: number; template_passed: number; leadership: number; vcp: boolean };

export type Overview = {
  demo: boolean;
  indices: { symbol: string; label: string; price: number; change: number; change_pct: number; spark: number[] }[];
  fear_greed: FearGreed;
  cycle: { symbol: string; label: string; stage: 1 | 2 | 3 | 4; name: string; since: string; weeks: number; ma30w: number; slope_pct: number }[];
  gainers: MoverRow[]; losers: MoverRow[]; active: MoverRow[];
  sectors: SectorRow[];
  leaders: LeaderRow[];
  breadth: { advancing: number; declining: number; new_highs: number; new_lows: number; pct_above_ma50: number | null };
};

export type EarningsCal = {
  demo: boolean;
  upcoming: { symbol: string; name: string; date: string; days_until: number; eps_estimate: number | null; last_surprise_pct: number | null }[];
  recent: { symbol: string; name: string; date: string; eps_estimate: number | null; eps_actual: number | null; surprise_pct: number | null; reaction_pct: number | null }[];
};

export type ExtRow = { symbol: string; name: string; session: string; price: number; reference_close: number; change: number; change_pct: number; volume: number; time: string };
export type Extended = { available: boolean; reason: string | null; pre_market: ExtRow[]; after_hours: ExtRow[] };

export type Fed = {
  demo: boolean; as_of: string;
  target_range: { lower: number; upper: number }; effective_rate: number;
  treasury: { bill_3m: number | null; note_2y: number | null; note_10y: number | null }; curve_2s10s_bp: number | null;
  next_meeting: string | null; meetings: { date: string; past: boolean }[];
  outlook: { implied_change_bp: number; direction: "cut" | "hike" | "hold"; probabilities: { cut: number; hike: number; hold: number }; method: string } | null;
  decisions: { date: string; upper: number; lower: number; change_bp: number; action: "Cut" | "Hike" }[];
  history: { upper: { time: string; value: number }[]; effective: { time: string; value: number }[]; note_2y: { time: string; value: number }[] };
};

export type ScreenRow = {
  symbol: string; name: string; sector: string; price: number; change_pct: number; from_high_pct: number; rsi14: number; above_ma50: boolean;
  return_1m: number; return_3m: number | null; market_cap_b: number | null; pe: number | null; eps_growth: number | null; peg: number | null;
  dividend_yield: number | null; beta: number | null; rs_rating: number | null; template_passed: number | null; bull_score: number | null;
  bear_score: number | null; vcp: boolean | null; sector_pe: number | null; pe_vs_sector_pct: number | null;
};
