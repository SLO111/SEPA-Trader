"use client";

import Link from "next/link";
import { Logo } from "@/components/AppShell";
import { useAuth } from "@/lib/auth";

const FEATURES = [
  { title: "Professional charts", text: "Candlesticks, multiple timeframes and unlimited watchlists." },
  { title: "Strategy overlays", text: "Moving averages, RSI, MACD, Bollinger Bands and BUY/SELL bots. Stack as many as you like." },
  { title: "Move Detector", text: "An algorithm that finds stocks set up for a major move, up or down." },
  { title: "Smart alerts", text: "Breakouts, unusual volume, gaps and warning signs, in real time." },
  { title: "Portfolios", text: "Track performance and automatically see the risk profile of each portfolio." },
  { title: "Journal & Trade Review", text: "Expectancy, win rate and a grade for every trade, so you can sharpen your edge." },
];

const PLANS = [
  { name: "Free", price: "0", items: ["15-minute delayed data", "1 watchlist, up to 10 tickers", "3 indicators per chart", "1 portfolio"] },
  { name: "Pro", price: "29", items: ["Real-time data", "Unlimited watchlists", "All strategies", "Move Detector + alerts"], highlight: true },
  { name: "Premium", price: "59", items: ["Everything in Pro", "Company PDF reports", "Backtesting", "Trade Review"] },
];

export default function Home() {
  const { user } = useAuth();
  return (
    <div className="min-h-screen">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4">
        <Logo />
        <div className="flex items-center gap-2 text-sm">
          {user ? (
            <Link href="/chart" className="rounded-md bg-accent px-4 py-2 font-medium text-white hover:bg-blue-500">Open app</Link>
          ) : (
            <>
              <Link href="/login" className="rounded-md px-3 py-2 text-muted hover:text-text">Log in</Link>
              <Link href="/register" className="rounded-md bg-accent px-4 py-2 font-medium text-white hover:bg-blue-500">Start free</Link>
            </>
          )}
        </div>
      </header>

      <section className="mx-auto max-w-6xl px-4 pb-16 pt-12 sm:pt-20">
        <p className="mb-4 text-sm font-medium text-accent">Technical analysis · SEPA method · Alerts</p>
        <h1 className="max-w-3xl text-4xl font-bold leading-tight tracking-tight sm:text-5xl">
          Find the market&apos;s leaders before they&apos;re obvious to everyone.
        </h1>
        <p className="mt-5 max-w-2xl text-lg text-muted">
          Charts, strategies, portfolios and an algorithm that detects stocks set up for major moves, all in one platform.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Link href={user ? "/chart" : "/register"} className="rounded-md bg-accent px-5 py-2.5 font-medium text-white hover:bg-blue-500">
            {user ? "Go to charts" : "Create a free account"}
          </Link>
          <a href="#pricing" className="rounded-md border border-line px-5 py-2.5 text-muted hover:text-text">See plans</a>
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

      <section id="pricing" className="mx-auto max-w-6xl px-4 pb-24">
        <h2 className="mb-8 text-2xl font-bold">Plans</h2>
        <div className="grid gap-4 md:grid-cols-3">
          {PLANS.map((p) => (
            <div key={p.name} className={`rounded-xl border p-6 ${p.highlight ? "border-accent bg-accent/5" : "border-line bg-panel"}`}>
              <h3 className="font-semibold">{p.name}</h3>
              <p className="mt-2">
                <span className="text-3xl font-bold">${p.price}</span>
                <span className="text-muted">/month</span>
              </p>
              <ul className="mt-5 space-y-2 text-sm text-muted">
                {p.items.map((i) => (
                  <li key={i}>✓ {i}</li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <p className="mt-4 text-xs text-muted">Prices are indicative. Online payments will be enabled in a later release.</p>
      </section>

      <footer className="border-t border-line py-6 text-center text-xs text-muted">
        SEPA Trader · For educational purposes only. Not financial advice.
      </footer>
    </div>
  );
}
