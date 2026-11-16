"use client";

import Link from "next/link";
import { put } from "@/lib/api";
import { type Lang, setLang, useLang, useT } from "@/lib/i18n";
import Logo from "@/components/Logo";

export const LEGAL_UPDATED = "November 2026";

/** Public page layout for the Terms, Privacy and Disclaimer (no login needed). */
export default function LegalPage({ title, titleRo, children }: { title: string; titleRo?: string; children: React.ReactNode }) {
  const lang = useLang();
  return (
    <div className="min-h-screen bg-bg text-text">
      <header className="border-b border-line">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-4 py-3">
          <Logo />
          <nav className="flex gap-4 text-sm text-muted">
            <Link href="/terms" className="hover:text-text">{lang === "ro" ? "Termeni" : "Terms"}</Link>
            <Link href="/privacy" className="hover:text-text">{lang === "ro" ? "Confidențialitate" : "Privacy"}</Link>
            <Link href="/disclaimer" className="hover:text-text">{lang === "ro" ? "Avertisment" : "Disclaimer"}</Link>
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-3xl px-4 py-8">
        <div className="flex items-start justify-between gap-3">
          <h1 className="text-2xl font-semibold">{lang === "ro" && titleRo ? titleRo : title}</h1>
          <span className="text-xs text-muted"><LangSwitch /></span>
        </div>
        <p className="mt-1 text-sm text-muted">{lang === "ro" ? "Ultima actualizare: noiembrie 2026" : `Last updated: ${LEGAL_UPDATED}`}</p>
        <div className="legal mt-6 space-y-4 text-sm leading-relaxed text-text/90 [&_h2]:mt-6 [&_h2]:text-base [&_h2]:font-semibold [&_li]:ml-5 [&_li]:list-disc">
          {children}
        </div>
      </main>
    </div>
  );
}

/** One-line legal footer for every app page. */
export function LegalFooter() {
  const t = useT();
  return (
    <footer className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-line px-4 py-1.5 text-[11px] text-muted">
      <span>{t("Vnicorn is an educational simulation platform. Nothing here is investment advice. Data may be delayed or inaccurate.")}</span>
      <span className="ml-auto flex gap-3">
        <Link href="/terms" className="hover:text-text">{t("Terms")}</Link>
        <Link href="/privacy" className="hover:text-text">{t("Privacy")}</Link>
        <Link href="/disclaimer" className="hover:text-text">{t("Risk disclaimer")}</Link>
        <LangSwitch />
      </span>
    </footer>
  );
}

/** EN / RO switch (saved on this device and in the account's preferences). */
export function LangSwitch() {
  const lang = useLang();
  const pick = (l: Lang) => {
    setLang(l);
    put("/api/auth/prefs", { lang: l }).catch(() => {}); // not logged in: device only
  };
  return (
    <span className="inline-flex overflow-hidden rounded border border-line">
      {(["en", "ro"] as const).map((l) => (
        <button key={l} onClick={() => pick(l)} className={`px-1.5 ${lang === l ? "bg-accent text-white" : "hover:text-text"}`}>{l.toUpperCase()}</button>
      ))}
    </span>
  );
}

/** Small badge for simulated / educational content (signals, ideas, vnicornAI). */
export function SimBadge({ className = "" }: { className?: string }) {
  const t = useT();
  return (
    <Link href="/disclaimer" title="Simulated, educational content. Not investment advice."
      className={`inline-flex items-center gap-1 rounded bg-slate-500/15 px-1.5 py-0.5 text-[10px] font-medium text-muted hover:text-text ${className}`}>
      {t("Simulated · not investment advice")}
    </Link>
  );
}


/** Shows the English or the Romanian version of a block, by the interface language. */
export function Bilingual({ en, ro }: { en: React.ReactNode; ro: React.ReactNode }) {
  return <>{useLang() === "ro" ? ro : en}</>;
}
