export const usd = (v: number, digits = 2) =>
  v.toLocaleString("en-US", { style: "currency", currency: "USD", minimumFractionDigits: digits, maximumFractionDigits: digits });

export const signedUsd = (v: number) => `${v >= 0 ? "+" : "−"}${usd(Math.abs(v))}`;

export const pct = (v: number | null | undefined, digits = 2) =>
  v === null || v === undefined ? "—" : `${v >= 0 ? "+" : ""}${v.toFixed(digits)}%`;

export const tone = (v: number | null | undefined) => (v === null || v === undefined ? "text-muted" : v >= 0 ? "text-up" : "text-down");

export const num = (v: number, digits = 4) => v.toLocaleString("en-US", { maximumFractionDigits: digits });

export const compactUsd = (v: number | null | undefined) => {
  if (v === null || v === undefined) return "—";
  const a = Math.abs(v);
  const s = a >= 1e12 ? `${(a / 1e12).toFixed(2)}T` : a >= 1e9 ? `${(a / 1e9).toFixed(2)}B` : a >= 1e6 ? `${(a / 1e6).toFixed(1)}M` : a.toLocaleString("en-US", { maximumFractionDigits: 0 });
  return `${v < 0 ? "−" : ""}$${s}`;
};

export const fmt = (v: number | null | undefined, digits = 2, suffix = "") =>
  v === null || v === undefined ? "—" : `${v.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits })}${suffix}`;
