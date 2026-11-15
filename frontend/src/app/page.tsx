"use client";

import Link from "next/link";
import { Logo } from "@/components/AppShell";
import { useAuth } from "@/lib/auth";

const FEATURES = [
  { title: "Charturi profesionale", text: "Lumânări, timeframe-uri multiple și liste nelimitate de tickere." },
  { title: "Strategii suprapuse", text: "Medii mobile, RSI, MACD, Bollinger și boți BUY/SELL, activate câte vrei deodată." },
  { title: "Move Detector", text: "Algoritm care caută acțiunile pregătite pentru o mișcare majoră, în sus sau în jos." },
  { title: "Alerte inteligente", text: "Breakout-uri, volum neobișnuit, gap-uri și semnale de avertizare, în timp real." },
  { title: "Portofolii", text: "Urmărești performanța și afli automat ce profil de risc are fiecare portofoliu." },
  { title: "Jurnal & Trade Review", text: "Expectancy, win rate și o notă pentru fiecare tranzacție, ca să-ți rafinezi avantajul." },
];

const PLANS = [
  { name: "Free", price: "0", items: ["Date cu întârziere de 15 min", "1 listă, max. 10 tickere", "3 indicatori pe chart", "1 portofoliu"] },
  { name: "Pro", price: "29", items: ["Date în timp real", "Liste nelimitate", "Toate strategiile", "Move Detector + alerte"], highlight: true },
  { name: "Premium", price: "59", items: ["Tot ce are Pro", "Rapoarte PDF pe companii", "Backtesting", "Trade Review"] },
];

export default function Home() {
  const { user } = useAuth();
  return (
    <div className="min-h-screen">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4">
        <Logo />
        <div className="flex items-center gap-2 text-sm">
          {user ? (
            <Link href="/chart" className="rounded-md bg-accent px-4 py-2 font-medium text-white hover:bg-blue-500">Deschide aplicația</Link>
          ) : (
            <>
              <Link href="/login" className="rounded-md px-3 py-2 text-muted hover:text-text">Intră</Link>
              <Link href="/register" className="rounded-md bg-accent px-4 py-2 font-medium text-white hover:bg-blue-500">Începe gratuit</Link>
            </>
          )}
        </div>
      </header>

      <section className="mx-auto max-w-6xl px-4 pb-16 pt-12 sm:pt-20">
        <p className="mb-4 text-sm font-medium text-accent">Analiză tehnică · Metoda SEPA · Alerte</p>
        <h1 className="max-w-3xl text-4xl font-bold leading-tight tracking-tight sm:text-5xl">
          Găsește liderii pieței înainte să fie evidenți pentru toți.
        </h1>
        <p className="mt-5 max-w-2xl text-lg text-muted">
          Charturi, strategii, portofolii și un algoritm care detectează acțiunile pregătite pentru mișcări majore, într-o singură platformă.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Link href={user ? "/chart" : "/register"} className="rounded-md bg-accent px-5 py-2.5 font-medium text-white hover:bg-blue-500">
            {user ? "Mergi la charturi" : "Creează cont gratuit"}
          </Link>
          <a href="#preturi" className="rounded-md border border-line px-5 py-2.5 text-muted hover:text-text">Vezi planurile</a>
        </div>
      </section>

      <section className="mx-auto grid max-w-6xl gap-4 px-4 pb-20 sm:grid-cols-2 lg:grid-cols-3">
        {FEATURES.map((f) => (
          <div key={f.title} className="rounded-xl border border-line bg-panel p-5">
            <h3 className="font-semibold">{f.title}</h3>
            <p className="mt-2 text-sm text-muted">{f.text}</p>
          </div>
        ))}
      </section>

      <section id="preturi" className="mx-auto max-w-6xl px-4 pb-24">
        <h2 className="mb-8 text-2xl font-bold">Planuri</h2>
        <div className="grid gap-4 md:grid-cols-3">
          {PLANS.map((p) => (
            <div key={p.name} className={`rounded-xl border p-6 ${p.highlight ? "border-accent bg-accent/5" : "border-line bg-panel"}`}>
              <h3 className="font-semibold">{p.name}</h3>
              <p className="mt-2">
                <span className="text-3xl font-bold">${p.price}</span>
                <span className="text-muted">/lună</span>
              </p>
              <ul className="mt-5 space-y-2 text-sm text-muted">
                {p.items.map((i) => (
                  <li key={i}>✓ {i}</li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <p className="mt-4 text-xs text-muted">Prețurile sunt orientative. Plățile online vor fi activate într-o etapă ulterioară.</p>
      </section>

      <footer className="border-t border-line py-6 text-center text-xs text-muted">
        SEPA Trader · Informațiile au scop educațional și nu reprezintă sfat financiar.
      </footer>
    </div>
  );
}
