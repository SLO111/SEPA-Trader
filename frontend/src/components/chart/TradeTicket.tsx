"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { api, post } from "@/lib/api";
import { usd } from "@/lib/format";

type Levels = {
  price: number; atr: number; resistance: number[]; support: number[];
  vcp?: { pivot: number | null; stop: number | null } | null;
  ai_plan?: { entry: number; stop: number; trim: number; target: number; rr: number; prob: number; pick: boolean } | null;
};
type Pf = { id: number; name: string; value: number; locked?: boolean };

const r2 = (x: number) => (Number.isFinite(x) ? x.toFixed(2) : "");
const ACCOUNT_KEY = "vn_ticket_account";

/**
 * Order ticket from the chart.
 * Destination: a simulated trade (followed in Backtest → Chart trades) or a real buy in one of your portfolios, at the market price.
 * Free: Buy, quantity, Stop loss, Take profit. Pro / Premium: entry, trim, R/R, position sizing, ATR / VCP / resistance shortcuts, vnicornAI's plan.
 */
export default function TradeTicket({ symbol, price, side, pro, onClose }: { symbol: string; price: number; side: "long" | "short"; pro: boolean; onClose: () => void }) {
  const long = side === "long";
  const [dest, setDest] = useState<"sim" | number>("sim");
  const [portfolios, setPortfolios] = useState<Pf[]>([]);
  const [lv, setLv] = useState<Levels | null>(null);
  const [entry, setEntry] = useState(price.toFixed(2));
  const [stop, setStop] = useState((long ? price * 0.93 : price * 1.07).toFixed(2));
  const [trim, setTrim] = useState("");
  const [target, setTarget] = useState((long ? price * 1.2 : price * 0.8).toFixed(2));
  const [shares, setShares] = useState("10");
  const [track, setTrack] = useState(true);
  const [account, setAccount] = useState(() => {
    try {
      return localStorage.getItem(ACCOUNT_KEY) || "10000";
    } catch {
      return "10000";
    }
  });
  const [riskPct, setRiskPct] = useState("1");
  const [error, setError] = useState("");
  const [done, setDone] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (long) api<Pf[]>("/api/portfolios").then((l) => setPortfolios(l.filter((p) => !p.locked))).catch(() => {});
    api<Levels>(`/api/market/levels/${encodeURIComponent(symbol)}?side=${side}`).then(setLv).catch(() => {});
  }, [symbol, side, long]);

  const toPortfolio = dest !== "sim";
  const e = pro && !toPortfolio ? Number(entry) : price; // into a portfolio you always buy at the market
  const s = Number(stop), t = Number(target), tr = Number(trim);
  const calc = useMemo(() => {
    const risk = Math.abs(e - s);
    const ok = e > 0 && s > 0 && t > 0 && (long ? s < e && t > e : s > e && t < e) && (!tr || (long ? tr > e && tr < t : tr < e && tr > t));
    const acct = Number(account) || 0;
    const riskCash = acct * (Number(riskPct) || 0) / 100;
    const sizeShares = risk > 0 ? Math.floor(riskCash / risk) : 0;
    return {
      ok, risk, riskPct: e ? (risk / e) * 100 : 0, rr: risk ? Math.abs(t - e) / risk : 0,
      toStop: e ? ((s / e) - 1) * 100 : 0, toTarget: e ? ((t / e) - 1) * 100 : 0, toTrim: e && tr ? ((tr / e) - 1) * 100 : null,
      sizeShares, sizeValue: sizeShares * e, sizeWeight: acct ? (sizeShares * e) / acct * 100 : 0,
    };
  }, [e, s, t, tr, long, account, riskPct]);

  const qty = Number(shares);
  const canSubmit = toPortfolio ? qty > 0 && (!track || calc.ok) : calc.ok;
  const sign = long ? 1 : -1;
  const setStopAt = (x: number | null | undefined) => x && setStop(r2(x));
  const setR = (mult: number) => calc.risk > 0 && setTarget(r2(e + sign * mult * calc.risk));

  const submit = async () => {
    setError("");
    setBusy(true);
    try {
      if (toPortfolio) {
        await post(`/api/portfolios/${dest}/buy-now`, { symbol, shares: qty });
        if (track && calc.ok) {
          await post("/api/paper-trades/chart", { symbol, side, entry: e, stop: s, target: t, ...(tr ? { trim: tr } : {}) });
        }
        setDone(`Bought ${qty} ${symbol} at the market in “${portfolios.find((p) => p.id === dest)?.name}”.` + (track && calc.ok ? " Stop and target are followed in Backtest → Chart trades." : ""));
      } else {
        await post("/api/paper-trades/chart", { symbol, side, entry: e, stop: s, target: t, ...(pro && tr ? { trim: tr } : {}) });
        setDone("Added. It closes by itself at the target or the stop" + (pro && tr ? " (half is sold at the trim)." : "."));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const field = "w-full rounded-md border border-line bg-bg px-3 py-2 text-sm tabular outline-none focus:border-accent";
  const chip = "rounded bg-panel-2 px-1.5 py-0.5 text-[10px] text-muted hover:bg-line hover:text-text disabled:opacity-30";
  const pctTxt = (x: number | null) => (x === null ? "" : `${x >= 0 ? "+" : ""}${x.toFixed(1)}%`);

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-3" onMouseDown={onClose}>
      <div className={`max-h-[94vh] w-full overflow-y-auto rounded-xl border border-line bg-panel shadow-2xl ${pro ? "max-w-md" : "max-w-sm"}`} onMouseDown={(ev) => ev.stopPropagation()}>
        <div className={`flex items-center justify-between rounded-t-xl px-4 py-3 ${long ? "bg-up/15" : "bg-down/15"}`}>
          <h2 className="font-semibold">
            <span className={long ? "text-up" : "text-down"}>{long ? "Buy" : "Short"}</span> {symbol}
            <span className="ml-2 text-sm font-normal text-muted">{usd(price)}</span>
          </h2>
          <button onClick={onClose} className="rounded px-2 py-1 text-muted hover:bg-panel-2" aria-label="Close">✕</button>
        </div>
        {done ? (
          <div className="space-y-3 p-4 text-sm">
            <p className="text-up">{done}</p>
            <div className="flex flex-wrap gap-2">
              {toPortfolio && <Link href="/portfolios" className="rounded-md bg-accent px-4 py-2 font-medium text-white">Open Portfolio</Link>}
              {(!toPortfolio || track) && <Link href="/backtest?tab=chart" className="rounded-md border border-line px-4 py-2 font-medium">Backtest → Chart trades</Link>}
            </div>
          </div>
        ) : (
          <div className="space-y-3 p-4">
            {long && (
              <label className="block text-xs text-muted">
                Where
                <select value={String(dest)} onChange={(ev) => setDest(ev.target.value === "sim" ? "sim" : Number(ev.target.value))} className={`${field} mt-1`}>
                  <option value="sim">Backtest: simulated trade</option>
                  {portfolios.map((p) => <option key={p.id} value={p.id}>Portfolio: {p.name} (real buy at market)</option>)}
                </select>
              </label>
            )}
            {toPortfolio && (
              <label className="block text-xs text-muted">
                Shares
                <div className="mt-1 flex gap-2">
                  <input value={shares} onChange={(ev) => setShares(ev.target.value)} inputMode="decimal" className={field} />
                  {pro && calc.sizeShares > 0 && (
                    <button onClick={() => setShares(String(calc.sizeShares))} className="shrink-0 rounded-md bg-panel-2 px-2 text-xs hover:bg-line" title="From the position-size calculator below">
                      Use {calc.sizeShares}
                    </button>
                  )}
                </div>
                <span className="mt-1 block text-[11px]">≈ {usd((qty || 0) * price)} at the market price</span>
              </label>
            )}

            {pro && lv?.ai_plan && (
              <button
                onClick={() => {
                  const p = lv.ai_plan!;
                  if (!toPortfolio) setEntry(r2(p.entry));
                  setStop(r2(p.stop));
                  setTrim(r2(p.trim));
                  setTarget(r2(p.target));
                }}
                className="w-full rounded-md border border-violet-500/40 bg-violet-500/10 py-1.5 text-xs font-medium text-violet-200 hover:bg-violet-500/20"
              >
                ✦ Use vnicornAI&apos;s plan · R/R {lv.ai_plan.rr} · {Math.round(lv.ai_plan.prob * 100)}% odds{lv.ai_plan.pick ? " · pick" : ""}
              </button>
            )}

            <div className="grid grid-cols-2 gap-3">
              {pro && !toPortfolio ? (
                <label className="text-xs text-muted">Entry<input value={entry} onChange={(ev) => setEntry(ev.target.value)} inputMode="decimal" className={`${field} mt-1`} /></label>
              ) : (
                <div className="text-xs text-muted">Entry<div className={`${field} mt-1 text-muted`}>Market · {usd(price)}</div></div>
              )}
              <label className="text-xs text-muted">
                Stop loss <span className="tabular">{calc.ok || s ? pctTxt(calc.toStop) : ""}</span>
                <input value={stop} onChange={(ev) => setStop(ev.target.value)} inputMode="decimal" className={`${field} mt-1 text-down`} />
                {pro && lv && (
                  <span className="mt-1 flex flex-wrap gap-1">
                    <button className={chip} onClick={() => setStopAt(e - sign * lv.atr)}>1× ATR</button>
                    <button className={chip} onClick={() => setStopAt(e - sign * 2 * lv.atr)}>2× ATR</button>
                    {long && lv.vcp?.stop && <button className={chip} onClick={() => setStopAt(lv.vcp!.stop)}>VCP</button>}
                    {(long ? lv.support[0] : lv.resistance[0]) && (
                      <button className={chip} onClick={() => setStopAt((long ? lv.support[0] : lv.resistance[0]) * (long ? 0.99 : 1.01))}>{long ? "Support" : "Resist."}</button>
                    )}
                  </span>
                )}
              </label>
              {pro && (
                <label className="text-xs text-muted">
                  Trim (optional) <span className="tabular">{pctTxt(calc.toTrim)}</span>
                  <input value={trim} onChange={(ev) => setTrim(ev.target.value)} inputMode="decimal" placeholder="sell half here" className={`${field} mt-1`} />
                  <span className="mt-1 flex flex-wrap gap-1">
                    <button className={chip} disabled={!calc.risk} onClick={() => setTrim(r2(e + sign * 1.5 * calc.risk))}>1.5R</button>
                    <button className={chip} disabled={!calc.risk} onClick={() => setTrim(r2((e + t) / 2))}>Halfway</button>
                  </span>
                </label>
              )}
              <label className="text-xs text-muted">
                Take profit <span className="tabular">{pctTxt(calc.toTarget)}</span>
                <input value={target} onChange={(ev) => setTarget(ev.target.value)} inputMode="decimal" className={`${field} mt-1 text-up`} />
                {pro && (
                  <span className="mt-1 flex flex-wrap gap-1">
                    <button className={chip} disabled={!calc.risk} onClick={() => setR(2)}>2R</button>
                    <button className={chip} disabled={!calc.risk} onClick={() => setR(3)}>3R</button>
                    {lv && (long ? lv.resistance[0] : lv.support[0]) && (
                      <button className={chip} onClick={() => setTarget(r2(long ? lv.resistance[0] : lv.support[0]))}>{long ? "Resistance" : "Support"}</button>
                    )}
                  </span>
                )}
              </label>
            </div>

            <div className="grid grid-cols-3 gap-2 rounded-lg bg-panel-2/50 p-2 text-center text-xs">
              <div><div className="text-muted">Risk</div><div className="tabular font-semibold text-down">{calc.riskPct.toFixed(1)}%</div></div>
              <div><div className="text-muted">Reward / risk</div><div className={`tabular font-semibold ${calc.rr >= 2 ? "text-up" : calc.rr >= 1 ? "" : "text-down"}`}>{calc.rr.toFixed(1)}</div></div>
              <div><div className="text-muted">{pro ? "Trim at" : "Reward"}</div><div className="tabular font-semibold text-up">{pro ? (tr ? usd(tr) : "—") : pctTxt(calc.toTarget)}</div></div>
            </div>
            {calc.rr > 0 && calc.rr < 2 && <p className="text-[11px] text-amber-300">Tip: top traders look for at least 2:1. The reward is small for the risk.</p>}

            {pro && (
              <div className="rounded-lg border border-line p-2">
                <div className="mb-1.5 text-[11px] uppercase tracking-wide text-muted">Position size</div>
                <div className="grid grid-cols-2 gap-2">
                  <label className="text-[11px] text-muted">Account ($)
                    <input value={account} onChange={(ev) => { setAccount(ev.target.value); try { localStorage.setItem(ACCOUNT_KEY, ev.target.value); } catch { /* ignore */ } }}
                      inputMode="decimal" className={`${field} mt-0.5 py-1`} />
                  </label>
                  <label className="text-[11px] text-muted">Risk per trade (%)
                    <input value={riskPct} onChange={(ev) => setRiskPct(ev.target.value)} inputMode="decimal" className={`${field} mt-0.5 py-1`} />
                  </label>
                </div>
                <p className="tabular mt-1.5 text-xs">
                  <b>{calc.sizeShares}</b> shares · {usd(calc.sizeValue)} · {calc.sizeWeight.toFixed(1)}% of the account. Hitting the stop costs {usd(calc.sizeShares * calc.risk)}.
                </p>
                {calc.sizeShares === 0 && calc.risk > 0 && (
                  <p className="mt-1 text-[11px] text-amber-300">The risk per share ({usd(calc.risk)}) is above your risk budget: tighten the stop, raise the risk % or the account size.</p>
                )}
              </div>
            )}

            {toPortfolio && (
              <label className="flex items-center gap-2 text-xs text-muted">
                <input type="checkbox" checked={track} onChange={(ev) => setTrack(ev.target.checked)} />
                Also follow the stop &amp; take profit in Backtest
              </label>
            )}
            {!calc.ok && (!toPortfolio || track) && (
              <p className="text-xs text-down">{long ? "For a buy: stop below the entry, take profit above it" : "For a short: stop above the entry, take profit below it"}{pro ? ", trim in between." : "."}</p>
            )}
            {error && <p className="text-xs text-down">{error}</p>}
            <button disabled={!canSubmit || busy} onClick={submit} className={`w-full rounded-md py-2 text-sm font-semibold text-white disabled:opacity-40 ${long ? "bg-up hover:bg-green-500" : "bg-down hover:bg-red-500"}`}>
              {busy ? "Sending…" : toPortfolio ? `Buy ${qty || ""} ${symbol} at market` : `${long ? "Buy" : "Short"} ${symbol}`}
            </button>
            <p className="text-[11px] text-muted">
              {toPortfolio
                ? "Recorded in your portfolio at the latest price, dated the latest trading day."
                : "A simulated trade, followed in Backtest → Chart trades and graded in TradeGrader."}
              {!pro && <> <Link href="/billing" className="text-amber-300 hover:underline">Pro</Link> adds trim, position sizing, ATR / VCP stops and vnicornAI&apos;s plan.</>}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
