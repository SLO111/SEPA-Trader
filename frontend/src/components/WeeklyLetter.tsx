"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Letter = { id: number; title: string; created_at: string; week: string; paragraphs: string[]; locked?: boolean };

/** The latest weekly market letter (Premium; a teaser on other plans). */
export default function WeeklyLetter() {
  const [l, setL] = useState<Letter | null>(null);
  const [open, setOpen] = useState(false);
  useEffect(() => {
    api<Letter | null>("/api/feed/letter").then(setL).catch(() => {});
  }, []);
  if (!l) return null;
  return (
    <section className="mb-4 rounded-xl border border-violet-500/30 bg-gradient-to-br from-violet-500/10 to-panel">
      <button onClick={() => setOpen((o) => !o)} className="flex w-full items-start gap-3 p-4 text-left">
        <span className="text-xl leading-none">✉️</span>
        <span className="min-w-0 flex-1">
          <span className="mb-0.5 block text-[11px] text-muted">WEEKLY LETTER · {l.week}</span>
          <span className="block font-medium leading-snug">{l.title}</span>
        </span>
        <span className="text-xs text-muted">{open ? "Hide ▲" : "Read ▼"}</span>
      </button>
      {open && (
        <div className="space-y-3 border-t border-line px-4 pb-4 pt-3 text-sm leading-relaxed">
          {l.paragraphs.map((p) => <p key={p.slice(0, 30)}>{p}</p>)}
          {l.locked && (
            <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3">
              🔒 The full letter (groups, leaders, warnings, earnings, the week&apos;s track record) is part of Premium.{" "}
              <Link href="/billing" className="font-semibold text-amber-300 underline">Unlock</Link>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
