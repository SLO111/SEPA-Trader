/** Light / dark / system theme. Stored in the browser (instant) and in the account (Settings). */
export type ThemePref = "dark" | "light" | "system";
const KEY = "vn_theme";

export function resolveTheme(pref: ThemePref): "dark" | "light" {
  if (pref === "system") return typeof window !== "undefined" && window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
  return pref;
}

export function getThemePref(): ThemePref {
  try {
    return (localStorage.getItem(KEY) as ThemePref) || "dark";
  } catch {
    return "dark";
  }
}

export function applyTheme(pref: ThemePref) {
  try {
    localStorage.setItem(KEY, pref);
  } catch {
    /* storage unavailable */
  }
  document.documentElement.dataset.theme = resolveTheme(pref);
  window.dispatchEvent(new Event("theme-changed"));
}

/** Colors for lightweight-charts, read from the current theme's CSS variables. */
export function chartColors() {
  const css = typeof window !== "undefined" ? getComputedStyle(document.documentElement) : null;
  const v = (name: string, fallback: string) => (css?.getPropertyValue(name).trim() || fallback);
  const light = typeof document !== "undefined" && document.documentElement.dataset.theme === "light";
  return {
    bg: v("--color-bg", "#0b0e14"),
    text: v("--color-muted", "#8b95a7"),
    grid: light ? "#e8ecf2" : "#161c28",
    border: v("--color-line", "#232c3d"),
  };
}

/** Inline script for <head>: applies the saved theme before the first paint (no flash). */
export const THEME_BOOT = `try{var p=localStorage.getItem("${KEY}")||"dark";var t=p==="system"?(matchMedia("(prefers-color-scheme: light)").matches?"light":"dark"):p;document.documentElement.dataset.theme=t;}catch(e){}`;
