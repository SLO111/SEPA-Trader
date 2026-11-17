"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import PublicShell from "@/components/PublicShell";
import { LESSONS } from "@/lib/academy";
import { api, post } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const T = {
  en: { title: "SEPA Academy", intro: "Eight short lessons on trend-following the way top growth-stock traders do it, each tied to the tool in Vnicorn that applies it.",
    done: "Mark as done", completed: "✓ Completed", progress: "completed", next: "Next lesson →", back: "← All lessons", min: "min", key: "Key points", edu: "Educational content, not investment advice." },
};

function Academy() {
  const t = T.en;
  const { user } = useAuth();
  const slug = useSearchParams().get("l");
  const [done, setDone] = useState<string[]>([]);
  useEffect(() => {
    if (user) api<{ done: string[] }>("/api/academy/progress").then((r) => setDone(r.done)).catch(() => {});
    else {
      try {
        setDone(JSON.parse(localStorage.getItem("vn_academy") || "[]"));
      } catch {
        /* ignore */
      }
    }
  }, [user]);
  const mark = async (s: string) => {
    if (user) setDone((await post<{ done: string[] }>(`/api/academy/progress/${s}`, {})).done);
    else {
      const next = Array.from(new Set([...done, s]));
      setDone(next);
      try {
        localStorage.setItem("vn_academy", JSON.stringify(next));
      } catch {
        /* ignore */
      }
    }
  };
  const i = LESSONS.findIndex((l) => l.slug === slug);
  const lesson = i >= 0 ? LESSONS[i] : null;

  if (lesson) {
    return (
      <article className="mx-auto max-w-2xl space-y-4 p-4 sm:p-6">
        <div className="flex items-center justify-between">
          <Link href="/academy" className="text-sm text-accent hover:underline">{t.back}</Link>
        </div>
        <h1 className="text-2xl font-semibold">{lesson.title}</h1>
        <p className="text-xs text-muted">{lesson.minutes} {t.min}</p>
        {lesson.body.map((p) => <p key={p.slice(0, 20)} className="leading-relaxed">{p}</p>)}
        <div className="rounded-xl border border-line bg-panel p-4">
          <div className="mb-1 text-[11px] uppercase tracking-wide text-muted">{t.key}</div>
          <ul className="space-y-1 text-sm">{lesson.takeaways.map((k) => <li key={k}>✓ {k}</li>)}</ul>
        </div>
        <Link href={lesson.tryHref} className="inline-block rounded-md bg-accent px-4 py-2 text-sm font-medium text-white">▶ {lesson.tryLabel}</Link>
        <div className="flex flex-wrap items-center gap-3 border-t border-line pt-4">
          {done.includes(lesson.slug) ? <span className="text-sm text-up">{t.completed}</span> : (
            <button onClick={() => mark(lesson.slug)} className="rounded-md border border-up/40 px-3 py-1.5 text-sm text-up hover:bg-up/10">{t.done}</button>
          )}
          {i < LESSONS.length - 1 && <Link href={`/academy?l=${LESSONS[i + 1].slug}`} className="ml-auto text-sm text-accent hover:underline">{t.next}</Link>}
        </div>
        <p className="text-xs text-muted">{t.edu}</p>
      </article>
    );
  }
  return (
    <div className="mx-auto max-w-4xl space-y-5 p-4 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">{t.title}</h1>
          <p className="mt-1 max-w-2xl text-sm text-muted">{t.intro}</p>
        </div>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-panel-2">
        <div className="h-full bg-up" style={{ width: `${(done.length / LESSONS.length) * 100}%` }} />
      </div>
      <p className="text-xs text-muted">{done.length}/{LESSONS.length} {t.progress}</p>
      <div className="grid gap-3 sm:grid-cols-2">
        {LESSONS.map((l) => (
          <Link key={l.slug} href={`/academy?l=${l.slug}`} className="rounded-xl border border-line bg-panel p-4 hover:border-accent/60">
            <div className="flex items-start justify-between gap-2">
              <h2 className="font-semibold">{l.title}</h2>
              {done.includes(l.slug) && <span className="text-up">✓</span>}
            </div>
            <p className="mt-1 line-clamp-2 text-sm text-muted">{l.body[0]}</p>
            <p className="mt-2 text-xs text-muted">{l.minutes} {t.min}</p>
          </Link>
        ))}
      </div>
      <p className="text-xs text-muted">{t.edu}</p>
    </div>
  );
}

export default function AcademyPage() {
  return (
    <PublicShell>
      <div className="h-full overflow-y-auto">
        <Suspense><Academy /></Suspense>
      </div>
    </PublicShell>
  );
}
