"use client";

/* eslint-disable @next/next/no-img-element */
import Link from "next/link";
import Logo from "@/components/Logo";
import { useAuth } from "@/lib/auth";
import { useLang } from "@/lib/i18n";
import { LangSwitch } from "@/components/legal/LegalPage";

const STATS = [
  { value: "500+", label: "US stocks scanned every day" },
  { value: "Top 50", label: "trade ideas after each close" },
  { value: "AI", label: "odds & expected value on every plan" },
  { value: "24/7", label: "alerts from your watchlists" },
];

const BENTO = [
  {
    title: "Daily trade ideas with a full plan",
    text: "Every evening the algorithm reads daily, weekly and monthly trends and historical support and resistance, then publishes the best setups with entry, stop, trim, target and R/R. Take one with a click and follow its result.",
    img: "/screenshots/ideas.webp",
    span: "lg:col-span-2",
  },
  {
    title: "Pro charts",
    text: "Pre-market and after-hours candles, OHLC on hover, indicators stacked as you like: moving averages, VCP, Trend Template, Structure Count, market cycle.",
    img: "/screenshots/chart.webp",
    span: "",
  },
  {
    title: "Market at a glance",
    text: "Indexes, market cycle stage, Fear & Greed, breadth, movers, earnings calendar, Fed monitor and an S&P 500 heatmap.",
    img: "/screenshots/markets.webp",
    span: "",
  },
  {
    title: "Company insight in one page",
    text: "Key facts, analyst rating, technical rating, financials, earnings, dividends, ownership and news, with a sticky menu to jump anywhere.",
    img: "/screenshots/stock.webp",
    span: "lg:col-span-2",
  },
];

const FEATURES = [
  ["vnicornAI", "A machine-learning model that builds the plan (stop, trim, target) with the best expected value and tells you its odds. Published only where its walk-forward test beats the baseline."],
  ["Move Detector", "Bull and Bear scores that flag stocks set up for a major move, before it is obvious."],
  ["Market cycle", "Accumulation, Markup, Distribution, Markdown, measured on the 30-week average."],
  ["Structure Count 4/4", "A step count that confirms who is in control, with a trailing defence line."],
  ["Automatic alerts", "Breakouts, gaps, unusual volume and warnings for every stock in your watchlists."],
  ["Daily summary", "The day in one card, pinned over the weekend, and by email if you want it."],
  ["Track record", "Every idea is followed after publication, so results are public, not promises."],
];

const STEPS = [
  ["Build your watchlists", "Add the stocks you follow. Alerts are created for them automatically."],
  ["Get the evening plan", "After the close: the market summary and the top ideas with entry, stop, trim and target."],
  ["Act and measure", "Take an idea with one click and see how it performs, in R and in %, trade by trade."],
];

const PLANS = [
  { name: "Free", price: "0", items: ["Charts, indicators & free screener", "1 watchlist, up to 10 tickers", "1 portfolio + TradeGrader", "Market overview, exposure & heatmap", "SEPA Academy"] },
  { name: "Pro", price: "19", items: ["Top 10 trade ideas a day + Move Detector", "vnicorn Pulse + Ask vnicornAI (20/month)", "Full Trend Template + VCP", "Backtesting, analytics, EPS & sales growth", "Email alerts & daily summary", "5 portfolios"], highlight: true },
  { name: "Premium", price: "49", items: ["Everything in Pro", "All 50 ideas incl. shorts + vnicornAI picks", "Unlimited Ask vnicornAI", "Industry groups + weekly letter", "Strategy builder + CSV export", "Unlimited watchlists & portfolios"] },
];

const FAQ = [
  ["Is this a real trading account?", "No. Vnicorn is an educational simulation: Buy and Sell create simulated trades and records in your own portfolios. No real orders are ever placed, and no broker is connected."],
  ["Is the data real?", "Prices come from public market data and may be delayed. Fundamentals and earnings refresh daily."],
  ["How are the trade ideas made?", "By rules, after each close: trend agreement across timeframes, market cycle stage, the Structure Count, relative strength and the distance to support and resistance. Every idea gets a stop, a trim level and a target with at least 2:1 reward to risk."],
  ["Can I see if the ideas work?", "Yes. Every idea is tracked after publication (entry, trim, target or stop) and the track record is visible in the app. You can also take ideas yourself and follow your own results."],
  ["Is this financial advice?", "No. Vnicorn Investments is an analysis and education tool. Decisions and risk are always yours."],
];

const RO_L: Record<string, string> = {
  "US stocks scanned every day": "acțiuni americane analizate zilnic",
  "trade ideas after each close": "idei de tranzacționare după fiecare închidere",
  "odds & expected value on every plan": "șanse și valoare așteptată pentru fiecare plan",
  "alerts from your watchlists": "alerte din watchlist-urile tale",
  "Daily trade ideas with a full plan": "Idei zilnice cu plan complet",
  "Every evening the algorithm reads daily, weekly and monthly trends and historical support and resistance, then publishes the best setups with entry, stop, trim, target and R/R. Take one with a click and follow its result.": "În fiecare seară algoritmul citește tendințele zilnice, săptămânale și lunare și suporturile și rezistențele istorice, apoi publică cele mai bune setup-uri cu intrare, stop, trim, target și R/R. Iei una cu un click și îi urmărești rezultatul.",
  "Pro charts": "Grafice profesionale",
  "Pre-market and after-hours candles, OHLC on hover, indicators stacked as you like: moving averages, VCP, Trend Template, Structure Count, market cycle.": "Lumânări pre-market și after-hours, OHLC la trecerea mouse-ului, indicatori combinați cum vrei: medii mobile, VCP, Trend Template, Structure Count, ciclul pieței.",
  "Market at a glance": "Piața dintr-o privire",
  "Indexes, market cycle stage, Fear & Greed, breadth, movers, earnings calendar, Fed monitor and an S&P 500 heatmap.": "Indici, etapa ciclului pieței, Fear & Greed, lățimea pieței, cele mai mari mișcări, calendarul rezultatelor, monitorul Fed și o hartă S&P 500.",
  "Company insight in one page": "Totul despre o companie într-o pagină",
  "Key facts, analyst rating, technical rating, financials, earnings, dividends, ownership and news, with a sticky menu to jump anywhere.": "Date cheie, ratingul analiștilor, ratingul tehnic, situații financiare, rezultate, dividende, acționariat și știri, cu un meniu fix pentru navigare rapidă.",
  "A machine-learning model that builds the plan (stop, trim, target) with the best expected value and tells you its odds. Published only where its walk-forward test beats the baseline.": "Un model de învățare automată care construiește planul (stop, trim, target) cu cea mai bună valoare așteptată și îți spune șansele. Publicat doar acolo unde testul walk-forward bate referința.",
  "Bull and Bear scores that flag stocks set up for a major move, before it is obvious.": "Scoruri Bull și Bear care semnalează acțiunile pregătite pentru o mișcare mare, înainte să fie evidentă.",
  "Market cycle": "Ciclul pieței",
  "Accumulation, Markup, Distribution, Markdown, measured on the 30-week average.": "Acumulare, creștere, distribuție, scădere, măsurate pe media de 30 de săptămâni.",
  "A step count that confirms who is in control, with a trailing defence line.": "O numărătoare pe pași care confirmă cine controlează piața, cu o linie de apărare mobilă.",
  "Automatic alerts": "Alerte automate",
  "Breakouts, gaps, unusual volume and warnings for every stock in your watchlists.": "Breakout-uri, gap-uri, volum neobișnuit și avertismente pentru fiecare acțiune din watchlist-uri.",
  "Daily summary": "Rezumat zilnic",
  "The day in one card, pinned over the weekend, and by email if you want it.": "Ziua într-un card, fixat și în weekend, și pe email dacă vrei.",
  "Track record": "Istoric rezultate",
  "Every idea is followed after publication, so results are public, not promises.": "Fiecare idee e urmărită după publicare, deci rezultatele sunt publice, nu promisiuni.",
  "Build your watchlists": "Construiește-ți watchlist-urile",
  "Add the stocks you follow. Alerts are created for them automatically.": "Adaugă acțiunile pe care le urmărești. Alertele se creează automat.",
  "Get the evening plan": "Primește planul de seară",
  "After the close: the market summary and the top ideas with entry, stop, trim and target.": "După închidere: rezumatul pieței și cele mai bune idei cu intrare, stop, trim și target.",
  "Act and measure": "Acționează și măsoară",
  "Take an idea with one click and see how it performs, in R and in %, trade by trade.": "Iei o idee cu un click și vezi cum evoluează, în R și în %, tranzacție cu tranzacție.",
  "Charts, indicators & free screener": "Grafice, indicatori și screener gratuit",
  "1 watchlist, up to 10 tickers": "1 watchlist, până la 10 simboluri",
  "1 portfolio + TradeGrader": "1 portofoliu + TradeGrader",
  "Market overview, exposure & heatmap": "Prezentarea pieței, expunere și hartă",
  "SEPA Academy": "Academia SEPA",
  "Top 10 trade ideas a day + Move Detector": "Top 10 idei pe zi + Move Detector",
  "vnicorn Pulse + Ask vnicornAI (20/month)": "vnicorn Pulse + Ask vnicornAI (20/lună)",
  "Full Trend Template + VCP": "Trend Template complet + VCP",
  "Backtesting, analytics, EPS & sales growth": "Backtesting, statistici, creșterea EPS și a vânzărilor",
  "Email alerts & daily summary": "Alerte pe email și rezumat zilnic",
  "5 portfolios": "5 portofolii",
  "Everything in Pro": "Tot ce e în Pro",
  "All 50 ideas incl. shorts + vnicornAI picks": "Toate cele 50 de idei, inclusiv short + vnicornAI picks",
  "Unlimited Ask vnicornAI": "Ask vnicornAI nelimitat",
  "Industry groups + weekly letter": "Grupuri de industrie + scrisoare săptămânală",
  "Strategy builder + CSV export": "Constructor de strategii + export CSV",
  "Unlimited watchlists & portfolios": "Watchlist-uri și portofolii nelimitate",
  "Is this a real trading account?": "Este un cont real de tranzacționare?",
  "No. Vnicorn is an educational simulation: Buy and Sell create simulated trades and records in your own portfolios. No real orders are ever placed, and no broker is connected.": "Nu. Vnicorn este o simulare educațională: Buy și Sell creează tranzacții simulate și înregistrări în portofoliile tale. Nu se plasează niciodată ordine reale și nu e conectat niciun broker.",
  "Is the data real?": "Datele sunt reale?",
  "Prices come from public market data and may be delayed. Fundamentals and earnings refresh daily.": "Prețurile provin din date publice de piață și pot fi întârziate. Datele fundamentale și rezultatele se actualizează zilnic.",
  "How are the trade ideas made?": "Cum sunt create ideile?",
  "By rules, after each close: trend agreement across timeframes, market cycle stage, the Structure Count, relative strength and the distance to support and resistance. Every idea gets a stop, a trim level and a target with at least 2:1 reward to risk.": "Prin reguli, după fiecare închidere: concordanța tendinței pe mai multe intervale, etapa ciclului, Structure Count, puterea relativă și distanța față de suport și rezistență. Fiecare idee are un stop, un nivel de trim și un target cu un raport câștig/risc de cel puțin 2:1.",
  "Can I see if the ideas work?": "Pot vedea dacă ideile funcționează?",
  "Yes. Every idea is tracked after publication (entry, trim, target or stop) and the track record is visible in the app. You can also take ideas yourself and follow your own results.": "Da. Fiecare idee e urmărită după publicare (intrare, trim, target sau stop) și istoricul e public. Poți lua și tu idei și să-ți urmărești propriile rezultate.",
  "Is this financial advice?": "Este sfat financiar?",
  "No. Vnicorn Investments is an analysis and education tool. Decisions and risk are always yours.": "Nu. Vnicorn Investments este un instrument de analiză și educație. Deciziile și riscul îți aparțin mereu.",
  "Prices in EUR. Pay yearly and get 2 months free. 14 days of Premium free for new accounts. Cancel anytime.": "Prețuri în EUR. Plata anuală îți aduce 2 luni gratuite. 14 zile de Premium gratuit pentru conturile noi. Anulezi oricând.",
  "/month": "/lună",
  "Most popular": "Cel mai ales",
  "Start free": "Începe gratuit",
  "Choose": "Alege",
  "Features": "Funcții",
  "How it works": "Cum funcționează",
  "Pricing": "Prețuri",
  "Academy": "Academie",
  "Open app": "Deschide aplicația",
  "Log in": "Autentificare",
  "New: vnicornAI builds and rates every trade plan": "Nou: vnicornAI construiește și evaluează fiecare plan",
  "Spot the next": "Găsește următorii",
  "market leaders": "lideri ai pieței",
  "before everyone else.": "înaintea tuturor.",
  "Vnicorn scans the market every evening and hands you a clear plan: the best setups with entry, stop, trim and target, the market cycle, and alerts on every stock you follow.": "Vnicorn analizează piața în fiecare seară și îți dă un plan clar: cele mai bune setup-uri cu intrare, stop, trim și target, ciclul pieței și alerte pentru fiecare acțiune urmărită.",
  "Open the app": "Deschide aplicația",
  "Start free, no card needed": "Începe gratuit, fără card",
  "See what's inside": "Vezi ce conține",
  "Everything in one place": "Totul într-un singur loc",
  "A professional trading desk, without the noise.": "Un birou de tranzacționare profesionist, fără zgomot.",
  "Three steps. Every trading day.": "Trei pași. În fiecare zi de tranzacționare.",
  "Simple pricing": "Prețuri simple",
  "Start free. Upgrade when the ideas earn their keep.": "Începe gratuit. Treci la un plan plătit când ideile își merită prețul.",
  "Questions": "Întrebări",
  "Your edge, every evening.": "Avantajul tău, în fiecare seară.",
  "Join free and get tonight's market summary and trade ideas.": "Înscrie-te gratuit și primește rezumatul pieței și ideile din seara asta.",
  "Create my free account": "Creează-mi contul gratuit"
};

function Frame({ src, alt, className = "" }: { src: string; alt: string; className?: string }) {
  return (
    <div className={`overflow-hidden rounded-xl border border-white/10 bg-[#0d1119] shadow-2xl shadow-black/50 ${className}`}>
      <div className="flex items-center gap-1.5 border-b border-white/5 px-3 py-2">
        <span className="h-2.5 w-2.5 rounded-full bg-red-400/70" />
        <span className="h-2.5 w-2.5 rounded-full bg-amber-400/70" />
        <span className="h-2.5 w-2.5 rounded-full bg-green-400/70" />
        <span className="ml-3 truncate rounded bg-white/5 px-2 py-0.5 text-[10px] text-slate-400">Vnicorn Investments</span>
      </div>
      <img src={src} alt={alt} loading="lazy" className="block w-full" width={1600} height={1000} />
    </div>
  );
}

export default function Home() {
  const { user } = useAuth();
  const lang = useLang();
  const L = (x: string) => (lang === "ro" ? RO_L[x] ?? x : x);
  const cta = user ? "/chart" : "/register";
  return (
    <div className="relative min-h-screen overflow-x-hidden bg-[#06080d] text-slate-100">
      {/* background: soft glows + faint grid */}
      <div aria-hidden className="pointer-events-none absolute inset-0">
        <div className="absolute -top-40 left-1/2 h-[600px] w-[1000px] -translate-x-1/2 rounded-full bg-violet-600/25 blur-[120px]" />
        <div className="absolute right-[-200px] top-[500px] h-[500px] w-[500px] rounded-full bg-cyan-500/15 blur-[120px]" />
        <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.035)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.035)_1px,transparent_1px)] bg-[size:56px_56px] [mask-image:radial-gradient(ellipse_at_top,black_30%,transparent_75%)]" />
      </div>

      <header className="sticky top-0 z-30 border-b border-white/5 bg-[#06080d]/70 backdrop-blur-xl">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
          <Logo />
          <nav className="hidden items-center gap-6 text-sm text-slate-400 md:flex">
            <a href="#features" className="hover:text-white">{L("Features")}</a>
            <a href="#how" className="hover:text-white">{L("How it works")}</a>
            <a href="#pricing" className="hover:text-white">{L("Pricing")}</a>
            <a href="#faq" className="hover:text-white">FAQ</a>
            <Link href="/academy" className="hover:text-white">{L("Academy")}</Link>
            <Link href="/track-record" className="hover:text-white">{L("Track record")}</Link>
          </nav>
          <div className="flex items-center gap-2 text-sm">
            <span className="text-xs text-slate-400"><LangSwitch /></span>
            {user ? (
              <Link href="/chart" className="rounded-full bg-white px-4 py-2 font-medium text-black hover:bg-slate-200">{L("Open app")}</Link>
            ) : (
              <>
                <Link href="/login" className="rounded-full px-3 py-2 text-slate-300 hover:text-white">{L("Log in")}</Link>
                <Link href="/register" className="rounded-full bg-white px-4 py-2 font-medium text-black hover:bg-slate-200">{L("Start free")}</Link>
              </>
            )}
          </div>
        </div>
      </header>

      <main className="relative">
        {/* hero */}
        <section className="mx-auto max-w-6xl px-4 pb-10 pt-16 text-center sm:pt-24">
          <span className="vn-fade inline-flex items-center gap-2 rounded-full border border-violet-400/30 bg-violet-500/10 px-3 py-1 text-xs text-violet-200">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-cyan-300" /> {L("New: vnicornAI builds and rates every trade plan")}
          </span>
          <h1 className="vn-fade mx-auto mt-6 max-w-4xl text-4xl font-bold leading-[1.05] tracking-tight sm:text-6xl lg:text-7xl" style={{ animationDelay: "80ms" }}>
            {L("Spot the next")}{" "}
            <span className="bg-gradient-to-r from-violet-300 via-indigo-200 to-cyan-300 bg-clip-text text-transparent">{L("market leaders")}</span>{" "}
            {L("before everyone else.")}
          </h1>
          <p className="vn-fade mx-auto mt-6 max-w-2xl text-lg text-slate-400" style={{ animationDelay: "160ms" }}>
            {L("Vnicorn scans the market every evening and hands you a clear plan: the best setups with entry, stop, trim and target, the market cycle, and alerts on every stock you follow.")}
          </p>
          <div className="vn-fade mt-9 flex flex-wrap justify-center gap-3" style={{ animationDelay: "240ms" }}>
            <Link href={cta} className="rounded-full bg-gradient-to-r from-violet-500 to-cyan-500 px-6 py-3 font-semibold text-white shadow-lg shadow-violet-500/25 transition hover:scale-[1.02]">
              {user ? L("Open the app") : L("Start free, no card needed")}
            </Link>
            <a href="#features" className="rounded-full border border-white/15 px-6 py-3 text-slate-200 hover:bg-white/5">{L("See what's inside")}</a>
          </div>

          <div className="vn-fade relative mx-auto mt-16 max-w-5xl [perspective:1800px]" style={{ animationDelay: "320ms" }}>
            <div className="absolute -inset-6 rounded-3xl bg-gradient-to-r from-violet-500/30 to-cyan-500/30 blur-2xl" />
            <Frame src="/screenshots/chart.webp" alt="Vnicorn chart with indicators and SEPA analysis" className="relative [transform:rotateX(8deg)] transition duration-700 hover:[transform:rotateX(0deg)]" />
          </div>
        </section>

        {/* stats */}
        <section className="mx-auto grid max-w-5xl grid-cols-2 gap-px overflow-hidden rounded-2xl border border-white/10 bg-white/10 md:grid-cols-4">
          {STATS.map((s) => (
            <div key={s.label} className="bg-[#0a0d14] p-6 text-center">
              <div className="bg-gradient-to-b from-white to-slate-400 bg-clip-text text-3xl font-bold text-transparent">{s.value}</div>
              <div className="mt-1 text-xs text-slate-400">{L(s.label)}</div>
            </div>
          ))}
        </section>

        {/* bento */}
        <section id="features" className="mx-auto max-w-6xl scroll-mt-20 px-4 pt-28">
          <p className="text-center text-sm font-medium uppercase tracking-[0.2em] text-cyan-300">{L("Everything in one place")}</p>
          <h2 className="mx-auto mt-3 max-w-3xl text-center text-3xl font-bold tracking-tight sm:text-5xl">{L("A professional trading desk, without the noise.")}</h2>
          <div className="mt-14 grid gap-5 lg:grid-cols-3">
            {BENTO.map((b) => (
              <article key={b.title} className={`group flex flex-col overflow-hidden rounded-2xl border border-white/10 bg-gradient-to-b from-white/[0.06] to-white/[0.01] p-6 ${b.span}`}>
                <h3 className="text-xl font-semibold">{L(b.title)}</h3>
                <p className="mt-2 text-sm leading-relaxed text-slate-400">{L(b.text)}</p>
                <div className="mt-6 overflow-hidden rounded-xl border border-white/10 transition duration-500 group-hover:-translate-y-1 group-hover:shadow-2xl group-hover:shadow-violet-500/10">
                  <img src={b.img} alt={b.title} loading="lazy" className="block w-full" width={1600} height={1000} />
                </div>
              </article>
            ))}
          </div>
          <div className="mt-5 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map(([t, d]) => (
              <div key={t} className="rounded-2xl border border-white/10 bg-white/[0.03] p-5 transition hover:border-violet-400/40 hover:bg-white/[0.05]">
                <div className="mb-3 h-8 w-8 rounded-lg bg-gradient-to-br from-violet-500 to-cyan-500 p-[1px]">
                  <div className="grid h-full w-full place-items-center rounded-[7px] bg-[#0a0d14] text-sm">✦</div>
                </div>
                <h3 className="font-semibold">{L(t)}</h3>
                <p className="mt-1.5 text-sm text-slate-400">{L(d)}</p>
              </div>
            ))}
          </div>
        </section>

        {/* how it works */}
        <section id="how" className="mx-auto max-w-6xl scroll-mt-20 px-4 pt-28">
          <h2 className="text-center text-3xl font-bold tracking-tight sm:text-5xl">{L("Three steps. Every trading day.")}</h2>
          <div className="mt-12 grid gap-5 md:grid-cols-3">
            {STEPS.map(([t, d], i) => (
              <div key={t} className="relative rounded-2xl border border-white/10 bg-white/[0.03] p-6">
                <span className="bg-gradient-to-br from-violet-300 to-cyan-300 bg-clip-text text-5xl font-bold text-transparent">0{i + 1}</span>
                <h3 className="mt-3 text-lg font-semibold">{L(t)}</h3>
                <p className="mt-1.5 text-sm text-slate-400">{L(d)}</p>
              </div>
            ))}
          </div>
          <div className="mt-10 grid items-center gap-8 lg:grid-cols-2">
            <Frame src="/screenshots/feed.webp" alt="Daily summary and market feed" />
            <Frame src="/screenshots/backtest.webp" alt="Your trades from ideas, with results in R" />
          </div>
        </section>

        {/* pricing */}
        <section id="pricing" className="mx-auto max-w-6xl scroll-mt-20 px-4 pt-28">
          <h2 className="text-center text-3xl font-bold tracking-tight sm:text-5xl">{L("Simple pricing")}</h2>
          <p className="mt-3 text-center text-slate-400">{L("Start free. Upgrade when the ideas earn their keep.")}</p>
          <div className="mt-12 grid gap-5 md:grid-cols-3">
            {PLANS.map((p) => (
              <div
                key={p.name}
                className={`relative rounded-2xl border p-7 ${p.highlight ? "border-violet-400/50 bg-gradient-to-b from-violet-500/15 to-transparent shadow-xl shadow-violet-500/10" : "border-white/10 bg-white/[0.03]"}`}
              >
                {p.highlight && <span className="absolute -top-3 left-7 rounded-full bg-gradient-to-r from-violet-500 to-cyan-500 px-3 py-0.5 text-xs font-semibold">{L("Most popular")}</span>}
                <h3 className="font-semibold">{p.name}</h3>
                <p className="mt-3">
                  <span className="text-4xl font-bold">€{p.price}</span>
                  <span className="text-slate-400">{L("/month")}</span>
                </p>
                <ul className="mt-6 space-y-2.5 text-sm text-slate-300">
                  {p.items.map((i) => (
                    <li key={i} className="flex gap-2">
                      <span className="text-cyan-300">✓</span>
                      {L(i)}
                    </li>
                  ))}
                </ul>
                <Link href={cta} className={`mt-7 block rounded-full py-2.5 text-center text-sm font-medium ${p.highlight ? "bg-white text-black hover:bg-slate-200" : "border border-white/15 hover:bg-white/5"}`}>
                  {p.price === "0" ? L("Start free") : `${L("Choose")} ${p.name}`}
                </Link>
              </div>
            ))}
          </div>
          <p className="mt-4 text-center text-xs text-slate-500">{L("Prices in EUR. Pay yearly and get 2 months free. 14 days of Premium free for new accounts. Cancel anytime.")}</p>
        </section>

        {/* faq */}
        <section id="faq" className="mx-auto max-w-3xl scroll-mt-20 px-4 pt-28">
          <h2 className="text-center text-3xl font-bold tracking-tight sm:text-4xl">{L("Questions")}</h2>
          <div className="mt-10 divide-y divide-white/10 rounded-2xl border border-white/10 bg-white/[0.03]">
            {FAQ.map(([q, a]) => (
              <details key={q} className="group p-5">
                <summary className="flex cursor-pointer list-none items-center justify-between font-medium">
                  {L(q)}
                  <span className="text-slate-400 transition group-open:rotate-45">+</span>
                </summary>
                <p className="mt-3 text-sm leading-relaxed text-slate-400">{L(a)}</p>
              </details>
            ))}
          </div>
        </section>

        {/* final cta */}
        <section className="mx-auto max-w-6xl px-4 py-28">
          <div className="relative overflow-hidden rounded-3xl border border-white/10 bg-gradient-to-br from-violet-600/30 via-indigo-600/20 to-cyan-500/20 p-10 text-center sm:p-16">
            <h2 className="text-3xl font-bold tracking-tight sm:text-5xl">{L("Your edge, every evening.")}</h2>
            <p className="mx-auto mt-4 max-w-xl text-slate-300">{L("Join free and get tonight's market summary and trade ideas.")}</p>
            <Link href={cta} className="mt-8 inline-block rounded-full bg-white px-7 py-3 font-semibold text-black hover:bg-slate-200">
              {user ? L("Open the app") : L("Create my free account")}
            </Link>
          </div>
        </section>
      </main>

      <footer className="relative border-t border-white/5">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 px-4 py-8 text-xs text-slate-500 sm:flex-row">
          <Logo />
          <p className="max-w-xl text-center sm:text-right">
            © {new Date().getFullYear()} Vnicorn Investments. An educational simulation platform: no real orders, not investment advice. Trading involves risk, including the loss of capital.
            <span className="mt-2 flex justify-center gap-4 sm:justify-end">
              <Link href="/terms" className="hover:text-slate-300">Terms</Link>
              <Link href="/privacy" className="hover:text-slate-300">Privacy</Link>
              <Link href="/disclaimer" className="hover:text-slate-300">Risk disclaimer</Link>
              <Link href="/track-record" className="hover:text-slate-300">Track record</Link>
            </span>
          </p>
        </div>
      </footer>
    </div>
  );
}
