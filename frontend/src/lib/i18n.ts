"use client";

import { useEffect, useState } from "react";

export type Lang = "en" | "ro";
const KEY = "vn_lang";

export function getLang(): Lang {
  try {
    return localStorage.getItem(KEY) === "ro" ? "ro" : "en";
  } catch {
    return "en";
  }
}

export function setLang(l: Lang) {
  try {
    localStorage.setItem(KEY, l);
  } catch {
    /* ignore */
  }
  document.documentElement.lang = l;
  window.dispatchEvent(new Event("lang-changed"));
}

/** The interface language (English / Romanian), live-updated when it is switched anywhere. */
export function useLang(): Lang {
  const [l, setL] = useState<Lang>("en");
  useEffect(() => {
    setL(getLang());
    const on = () => setL(getLang());
    window.addEventListener("lang-changed", on);
    return () => window.removeEventListener("lang-changed", on);
  }, []);
  return l;
}

const RO: Record<string, string> = {
  // navigation
  Charts: "Grafice", Markets: "Piețe", Signals: "Semnale", Backtest: "Backtest", Portfolio: "Portofoliu", Feed: "Noutăți", Alerts: "Alerte",
  Community: "Comunitate", Admin: "Admin", "Trade ideas": "Idei de tranzacționare", "Move Detector": "Move Detector", "vnicorn Pulse": "vnicorn Pulse",
  Portfolios: "Portofolii", Journal: "Jurnal", Leaderboard: "Clasament", "Track record": "Istoric rezultate", Academy: "Academie",
  "Log out": "Ieșire", "Log in": "Autentificare", "Sign up free": "Cont gratuit", Settings: "Setări", "Search stocks…": "Caută acțiuni…",
  // common
  Terms: "Termeni", Privacy: "Confidențialitate", "Risk disclaimer": "Avertisment de risc", Loading: "Se încarcă", Save: "Salvează", Cancel: "Anulează",
  "Unlock with Pro": "Deblochează cu Pro", "Unlock with Premium": "Deblochează cu Premium", Upgrade: "Upgrade",
  "Vnicorn is an educational simulation platform. Nothing here is investment advice. Data may be delayed or inaccurate.":
    "Vnicorn este o platformă educațională de simulare. Nimic de aici nu este sfat de investiții. Datele pot fi întârziate sau inexacte.",
  "Simulated · not investment advice": "Simulare · nu e sfat de investiții",
  // auth
  "Log in to your account": "Intră în cont", "Create a free account": "Creează un cont gratuit", Name: "Nume", Email: "Email", Password: "Parolă",
  "Password (at least 8 characters)": "Parolă (minim 8 caractere)", "Referral code (optional)": "Cod de recomandare (opțional)",
  "Create account": "Creează contul", "Please wait…": "Așteaptă…", "Don't have an account? ": "Nu ai cont? ", "Already have an account? ": "Ai deja cont? ",
  "Sign up": "Înregistrare",
  "New accounts get Premium free for 14 days": "Conturile noi primesc Premium gratuit 14 zile",
  "(+7 days with a referral code)": "(+7 zile cu un cod de recomandare)",
  "I accept the": "Accept", "the": "", "and the": "și",
  "Vnicorn is an educational simulation, not investment advice.": "Vnicorn este o simulare educațională, nu sfat de investiții.",
  // billing
  "Plans & billing": "Planuri și plată", Monthly: "Lunar", Yearly: "Anual", "2 months free": "2 luni gratis", "Current plan": "Planul curent",
  "Most popular": "Cel mai ales", "Free forever": "Gratuit pentru totdeauna", "On trial": "În perioada de probă",
  // settings
  Profile: "Profil", Appearance: "Aspect", Preferences: "Preferințe", Notifications: "Notificări", Subscription: "Abonament",
  "Invite friends": "Invită prieteni", "Delete account": "Șterge contul", Language: "Limba", "Copy link": "Copiază linkul",
  // daily summary
  "PINNED": "FIXAT", "Market mood": "Starea pieței", "Top movers": "Cele mai mari mișcări", "Market exposure: ": "Expunere recomandată: ",
  "Earnings next trading day": "Rezultate financiare în următoarea zi de tranzacționare", "Email me the daily summary": "Trimite-mi rezumatul zilnic pe email",
  "Show ▼": "Arată ▼", "Hide ▲": "Ascunde ▲",
};

/** Translate an English UI string (falls back to English). */
export function tr(s: string, l: Lang): string {
  if (l !== "ro") return s;
  return RO[s] ?? s;
}

export function useT() {
  const l = useLang();
  return (s: string) => tr(s, l);
}
