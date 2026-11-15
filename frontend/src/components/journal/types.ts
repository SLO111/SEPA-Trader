export type JTrade = {
  id: number; symbol: string; side: "long" | "short"; entry_date: string; entry_price: number; shares: number;
  stop_price: number | null; target_price: number | null; exit_date: string | null; exit_price: number | null; fees: number;
  setup: string; notes: string; last_price: number | null; status: "open" | "closed";
  pnl: number | null; return_pct: number | null; r_multiple: number | null; hold_days: number | null;
  risk_pct: number | null; risk_amount: number | null; reward_risk: number | null;
};

export type JStats = {
  closed_trades: number; open_trades: number; wins?: number; losses?: number; win_rate?: number;
  avg_win_pct?: number; avg_loss_pct?: number; win_loss_ratio?: number | null; expectancy_pct?: number; expectancy_r?: number | null;
  expectancy_usd?: number; profit_factor?: number | null; total_pnl?: number; largest_win?: number; largest_loss?: number;
  avg_hold_win?: number | null; avg_hold_loss?: number | null; max_win_streak?: number; max_loss_streak?: number;
  max_drawdown?: number; r_std?: number | null; profitable_months_pct?: number | null;
  equity_curve?: { time: string; value: number }[]; monthly?: { month: string; pnl: number }[];
  r_distribution?: number[]; by_setup?: { setup: string; trades: number; win_rate: number; pnl: number; avg_r: number | null }[];
};

export type Review = {
  grade: "A" | "B" | "C" | "D" | "F" | null; score: number | null; summary: string;
  checks: { category: string; status: "pass" | "warn" | "fail"; text: string; weight: number }[];
  strengths?: string[]; mistakes?: string[]; notes?: string[];
};
