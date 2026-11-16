"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import ImportCsv from "@/components/portfolio/ImportCsv";
import TradeGrader from "@/components/TradeGrader";
import ClassificationCard from "@/components/portfolio/ClassificationCard";
import HoldingsTable from "@/components/portfolio/HoldingsTable";
import { PROFILE_STYLE, RiskMeter } from "@/components/portfolio/profile";
import TemplateGallery from "@/components/portfolio/TemplateGallery";
import Transactions from "@/components/portfolio/Transactions";
import { api, del, patch, post } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { pct, signedUsd, tone, usd } from "@/lib/format";
import type { Performance, PortfolioDetail, PortfolioSummary } from "@/lib/types";

const PerformanceChart = dynamic(() => import("@/components/portfolio/PerformanceChart"), { ssr: false });
const PERIODS = ["1W", "1M", "3M", "6M", "YTD", "1Y", "ALL"] as const;

function Stat({ label, value, sub, cls = "" }: { label: string; value: string; sub?: string; cls?: string }) {
  return (
    <div>
      <div className="text-[11px] uppercase tracking-wide text-muted">{label}</div>
      <div className={`tabular text-lg font-semibold ${cls}`}>{value}</div>
      {sub && <div className={`tabular text-xs ${cls}`}>{sub}</div>}
    </div>
  );
}

function PerformanceCard({ id, version }: { id: number; version: number }) {
  const [period, setPeriod] = useState<string>("ALL");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [data, setData] = useState<Performance | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (period === "CUSTOM" && !start) return;
    const qs = period === "CUSTOM" ? `period=CUSTOM&start=${start}${end ? `&end=${end}` : ""}` : `period=${period}`;
    setError("");
    api<Performance>(`/api/portfolios/${id}/performance?${qs}`).then(setData).catch((e) => setError(e.message));
  }, [id, period, start, end, version]);

  const beat = data && data.portfolio_return !== null && data.benchmark_return !== null ? data.portfolio_return - data.benchmark_return : null;

  return (
    <section className="rounded-xl border border-line bg-panel p-4">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="font-semibold">Performance</h2>
        <div className="ml-auto flex flex-wrap items-center gap-1">
          {PERIODS.map((p) => (
            <button key={p} onClick={() => setPeriod(p)} className={`rounded px-2 py-1 text-xs ${period === p ? "bg-accent text-white" : "text-muted hover:bg-panel-2 hover:text-text"}`}>
              {p}
            </button>
          ))}
          <button onClick={() => setPeriod("CUSTOM")} className={`rounded px-2 py-1 text-xs ${period === "CUSTOM" ? "bg-accent text-white" : "text-muted hover:bg-panel-2 hover:text-text"}`}>
            Custom
          </button>
        </div>
      </div>
      {period === "CUSTOM" && (
        <div className="mt-3 flex flex-wrap items-center gap-2 text-sm text-muted">
          From
          <input type="date" value={start} onChange={(e) => setStart(e.target.value)} className="rounded border border-line bg-bg px-2 py-1 text-text" />
          to
          <input type="date" value={end} onChange={(e) => setEnd(e.target.value)} className="rounded border border-line bg-bg px-2 py-1 text-text" />
        </div>
      )}
      {error && <p className="mt-3 text-sm text-down">{error}</p>}
      {data && data.series.length > 0 ? (
        <>
          <div className="mt-3 flex flex-wrap gap-x-8 gap-y-2">
            <Stat label="Return" value={pct(data.portfolio_return)} cls={tone(data.portfolio_return)} />
            <Stat label="S&P 500" value={pct(data.benchmark_return)} cls={tone(data.benchmark_return)} />
            <Stat label="vs. market" value={pct(beat)} cls={tone(beat)} />
            <Stat label="Gain in period" value={signedUsd(data.pnl)} cls={tone(data.pnl)} />
            <div className="ml-auto self-end text-xs text-muted">
              {data.start} → {data.end}
            </div>
          </div>
          <div className="mt-2">
            <PerformanceChart data={data} />
          </div>
          <p className="text-[11px] text-muted">Time-weighted return: adding or withdrawing money does not count as gain or loss.</p>
        </>
      ) : (
        !error && <p className="mt-3 text-sm text-muted">Performance appears once the portfolio has transactions.</p>
      )}
    </section>
  );
}

function PortfolioView({ p, onChange, onDeleted }: { p: PortfolioDetail; onChange: (p: PortfolioDetail) => void; onDeleted: () => void }) {
  const [version, setVersion] = useState(0);
  const [modal, setModal] = useState<"none" | "import" | "grade">("none");
  const reload = async () => update(await api<PortfolioDetail>(`/api/portfolios/${p.id}`));
  const update = (np: PortfolioDetail) => {
    onChange(np);
    setVersion((v) => v + 1);
  };

  const rename = async () => {
    const name = prompt("Portfolio name:", p.name);
    if (name?.trim()) update(await patch<PortfolioDetail>(`/api/portfolios/${p.id}`, { name, description: p.description }));
  };
  const remove = async () => {
    if (!confirm(`Delete the portfolio "${p.name}" and all its transactions?`)) return;
    await del(`/api/portfolios/${p.id}`);
    onDeleted();
  };

  return (
    <div className="space-y-5">
      <section className="rounded-xl border border-line bg-panel p-4">
        <div className="flex flex-wrap items-start gap-3">
          <div className="min-w-0">
            <h1 className="text-xl font-semibold">{p.name}</h1>
            {p.description && <p className="text-sm text-muted">{p.description}</p>}
          </div>
          <div className="ml-auto flex flex-wrap gap-1 text-sm">
            <button onClick={() => setModal("grade")} className="rounded-md border border-violet-500/40 bg-violet-500/10 px-3 py-1 text-violet-200 hover:bg-violet-500/20">
              ✦ Grade trades
            </button>
            <button onClick={() => setModal("import")} className="rounded-md border border-line px-3 py-1 text-muted hover:text-text">
              ⬆ Import CSV / PDF
            </button>
            <button onClick={rename} className="rounded px-2 py-1 text-muted hover:bg-panel-2 hover:text-text">
              Rename
            </button>
            <button onClick={remove} className="rounded px-2 py-1 text-muted hover:bg-panel-2 hover:text-down">
              Delete
            </button>
          </div>
        </div>
        <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-5">
          <Stat label="Market value" value={usd(p.value)} />
          <Stat label="Today" value={signedUsd(p.day_change)} sub={pct(p.day_change_pct)} cls={tone(p.day_change)} />
          <Stat label="Unrealized P/L" value={signedUsd(p.unrealized_pnl)} sub={pct(p.unrealized_pnl_pct)} cls={tone(p.unrealized_pnl)} />
          <Stat label="Realized P/L" value={signedUsd(p.realized_pnl)} cls={tone(p.realized_pnl)} />
          <Stat label="Dividends received" value={usd(p.dividends_total)} cls={p.dividends_total > 0 ? "text-up" : ""} />
        </div>
      </section>
      {modal === "import" && <ImportCsv portfolioId={p.id} onClose={() => setModal("none")} onSaved={reload} />}
      {modal === "grade" && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-3" onMouseDown={() => setModal("none")}>
          <div className="flex max-h-[92vh] w-full max-w-6xl flex-col overflow-hidden rounded-xl border border-line bg-bg shadow-2xl" onMouseDown={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between border-b border-line p-4">
              <h2 className="font-semibold">TradeGrader · {p.name}</h2>
              <button onClick={() => setModal("none")} className="rounded px-2 py-1 text-muted hover:bg-panel-2" aria-label="Close">✕</button>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto p-4">
              <TradeGrader source="portfolio" portfolioId={p.id} />
            </div>
          </div>
        </div>
      )}

      <div className="grid gap-5 xl:grid-cols-[1fr_420px]">
        <PerformanceCard id={p.id} version={version} />
        <ClassificationCard c={p.classification} />
      </div>
      <HoldingsTable rows={p.positions} />
      <Transactions portfolioId={p.id} txns={p.transactions} onChange={update} />
      {p.dividends.length > 0 && (
        <details className="rounded-xl border border-line bg-panel p-4">
          <summary className="cursor-pointer font-semibold">
            Dividends <span className="text-sm font-normal text-muted">({p.dividends.length} payments, {usd(p.dividends_total)})</span>
          </summary>
          <table className="mt-3 w-full text-sm">
            <tbody>
              {[...p.dividends].reverse().map((d) => (
                <tr key={d.date + d.symbol} className="border-t border-line">
                  <td className="tabular py-1.5 text-muted">{d.date}</td>
                  <td className="py-1.5 font-medium">{d.symbol}</td>
                  <td className="tabular py-1.5 text-right text-muted">
                    {d.shares.toLocaleString("en-US", { maximumFractionDigits: 4 })} × {usd(d.per_share, 4)}
                  </td>
                  <td className="tabular py-1.5 text-right text-up">{usd(d.amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </details>
      )}
    </div>
  );
}

function Portfolios() {
  const { user } = useAuth();
  const [list, setList] = useState<PortfolioSummary[] | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [detail, setDetail] = useState<PortfolioDetail | null>(null);
  const [mode, setMode] = useState<"view" | "templates">("view");
  const [error, setError] = useState("");
  const max = user?.limits.max_portfolios ?? 1;

  const loadList = useCallback(async () => {
    const l = await api<PortfolioSummary[]>("/api/portfolios");
    setList(l);
    return l;
  }, []);

  useEffect(() => {
    loadList()
      .then((l) => {
        if (l.length) setSelected((s) => s ?? l[0].id);
        else setMode("templates");
      })
      .catch((e) => setError(e.message));
  }, [loadList]);

  useEffect(() => {
    if (selected === null) return setDetail(null);
    const load = () => api<PortfolioDetail>(`/api/portfolios/${selected}`).then(setDetail).catch((e) => setError(e.message));
    load();
    const id = setInterval(load, 60_000);
    return () => clearInterval(id);
  }, [selected]);

  const onDetail = (p: PortfolioDetail) => {
    setDetail(p);
    loadList();
  };

  const createBlank = async () => {
    setError("");
    const name = prompt("Name for the new portfolio:", "My portfolio");
    if (!name?.trim()) return;
    try {
      const p = await post<PortfolioDetail>("/api/portfolios", { name });
      await loadList();
      setSelected(p.id);
      setDetail(p);
      setMode("view");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error");
    }
  };

  // New portfolio straight from a broker file: create it, then open the import.
  const [importFor, setImportFor] = useState<number | null>(null);
  const createFromBroker = async () => {
    setError("");
    const name = prompt("Name for the portfolio (e.g. your broker):", "My broker");
    if (!name?.trim()) return;
    try {
      const p = await post<PortfolioDetail>("/api/portfolios", { name });
      await loadList();
      setSelected(p.id);
      setDetail(p);
      setMode("view");
      setImportFor(p.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error");
    }
  };

  const atLimit = (list?.length ?? 0) >= max;

  return (
    <div className="flex h-full">
      {importFor !== null && (
        <ImportCsv
          portfolioId={importFor}
          onClose={() => setImportFor(null)}
          onSaved={async () => {
            await loadList();
            try {
              setDetail(await api<PortfolioDetail>(`/api/portfolios/${importFor}`));
            } catch {
              /* ignore */
            }
          }}
        />
      )}
      <aside className="hidden w-72 shrink-0 flex-col border-r border-line bg-panel md:flex">
        <div className="flex items-center justify-between border-b border-line p-3">
          <h2 className="font-semibold">Portfolios</h2>
          <span className="tabular text-xs text-muted">
            {list?.length ?? 0}/{max >= 1e6 ? "∞" : max}
          </span>
        </div>
        <div className="grid grid-cols-2 gap-2 border-b border-line p-3">
          <button onClick={createBlank} disabled={atLimit} className="rounded-md bg-panel-2 py-1.5 text-sm hover:bg-line disabled:opacity-40">
            + Blank
          </button>
          <button onClick={() => setMode("templates")} disabled={atLimit} className="rounded-md bg-panel-2 py-1.5 text-sm hover:bg-line disabled:opacity-40">
            + From a model
          </button>
          <button onClick={createFromBroker} disabled={atLimit} className="col-span-2 rounded-md border border-accent/40 bg-accent/10 py-1.5 text-sm text-blue-300 hover:bg-accent/20 disabled:opacity-40">
            ⬆ From broker (CSV, Excel, PDF)
          </button>
        </div>
        {atLimit && max < 1e6 && <p className="border-b border-line px-3 py-2 text-xs text-amber-300">Your plan allows {max} portfolio{max > 1 ? "s" : ""}. Upgrade for more.</p>}
        <ul className="min-h-0 flex-1 overflow-y-auto">
          {list?.map((p) => (
            <li key={p.id}>
              <button
                onClick={() => {
                  setSelected(p.id);
                  setMode("view");
                }}
                className={`w-full border-b border-line px-3 py-3 text-left ${p.id === selected && mode === "view" ? "bg-panel-2" : "hover:bg-panel-2/60"}`}
              >
                <div className="flex items-baseline justify-between gap-2">
                  <span className="truncate font-medium">{p.name}</span>
                  <span className={`tabular text-xs ${tone(p.unrealized_pnl_pct)}`}>{pct(p.unrealized_pnl_pct)}</span>
                </div>
                <div className="tabular text-sm">{usd(p.value)}</div>
                <div className="mt-1.5 flex flex-wrap items-center gap-1">
                  {p.classification.primary ? (
                    <span className={`rounded px-1.5 py-0.5 text-[11px] font-medium ${PROFILE_STYLE[p.classification.primary]}`}>{p.classification.label}</span>
                  ) : (
                    <span className="text-[11px] text-muted">Empty</span>
                  )}
                </div>
                <div className="mt-1.5 flex items-center justify-between">
                  <span className="truncate text-[11px] text-muted">{p.symbols.slice(0, 5).join(" · ")}{p.symbols.length > 5 ? ` +${p.symbols.length - 5}` : ""}</span>
                  {p.classification.risk_level && <RiskMeter level={p.classification.risk_level} compact />}
                </div>
              </button>
            </li>
          ))}
        </ul>
      </aside>

      <section className="min-w-0 flex-1 overflow-y-auto">
        <div className="mx-auto max-w-6xl p-4 sm:p-6">
          <div className="mb-4 flex gap-2 md:hidden">
            <select
              value={mode === "templates" ? "" : selected ?? ""}
              onChange={(e) => {
                if (e.target.value) {
                  setSelected(Number(e.target.value));
                  setMode("view");
                }
              }}
              className="flex-1 rounded border border-line bg-bg px-2 py-1.5 text-sm"
            >
              <option value="">Choose a portfolio…</option>
              {list?.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
            <button onClick={() => setMode("templates")} disabled={atLimit} className="rounded border border-line px-3 text-sm text-muted disabled:opacity-40">
              + New
            </button>
          </div>
          {error && <p className="mb-4 rounded-md bg-down/10 px-3 py-2 text-sm text-down">{error}</p>}
          {mode === "templates" ? (
            <>
              {list?.length === 0 && (
                <div className="mb-6 rounded-xl border border-line bg-panel p-5">
                  <h1 className="text-xl font-semibold">Track your investments</h1>
                  <p className="mt-1 text-sm text-muted">
                    Record your trades to see performance over any period, dividends received and an automatic profile of each portfolio. Start blank or from a model below.
                  </p>
                  <button onClick={createBlank} className="mt-3 rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-blue-500">
                    Create a blank portfolio
                  </button>
                </div>
              )}
              <TemplateGallery
                onCancel={list && list.length ? () => setMode("view") : undefined}
                onCreated={async (p) => {
                  await loadList();
                  setSelected(p.id);
                  setDetail(p);
                  setMode("view");
                }}
              />
            </>
          ) : detail ? (
            <PortfolioView
              p={detail}
              onChange={onDetail}
              onDeleted={async () => {
                const l = await loadList();
                setSelected(l[0]?.id ?? null);
                if (!l.length) setMode("templates");
              }}
            />
          ) : (
            <p className="text-sm text-muted">Loading…</p>
          )}
          <p className="mt-6 text-xs text-muted">Portfolio profiles are estimates based on each stock&apos;s risk, valuation, dividends and sector. For educational purposes only. Not financial advice.</p>
        </div>
      </section>
    </div>
  );
}

export default function PortfoliosPage() {
  return (
    <AppShell>
      <Portfolios />
    </AppShell>
  );
}
