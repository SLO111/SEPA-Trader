export const usd = (v: number, digits = 2) =>
  v.toLocaleString("en-US", { style: "currency", currency: "USD", minimumFractionDigits: digits, maximumFractionDigits: digits });

export const signedUsd = (v: number) => `${v >= 0 ? "+" : "−"}${usd(Math.abs(v))}`;

export const pct = (v: number | null | undefined, digits = 2) =>
  v === null || v === undefined ? "—" : `${v >= 0 ? "+" : ""}${v.toFixed(digits)}%`;

export const tone = (v: number | null | undefined) => (v === null || v === undefined ? "text-muted" : v >= 0 ? "text-up" : "text-down");

export const num = (v: number, digits = 4) => v.toLocaleString("en-US", { maximumFractionDigits: digits });
