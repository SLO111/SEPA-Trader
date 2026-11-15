"use client";

import { useEffect, useState } from "react";
import { api, post } from "@/lib/api";
import type { PortfolioDetail, PortfolioTemplate } from "@/lib/types";
import { PROFILE_STYLE, RiskMeter } from "./profile";

export default function TemplateGallery({ onCreated, onCancel }: { onCreated: (p: PortfolioDetail) => void; onCancel?: () => void }) {
  const [templates, setTemplates] = useState<PortfolioTemplate[] | null>(null);
  const [amount, setAmount] = useState("10000");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api<PortfolioTemplate[]>("/api/portfolio-templates").then(setTemplates).catch((e) => setError(e.message));
  }, []);

  const create = async (t: PortfolioTemplate) => {
    setError("");
    setBusy(t.id);
    try {
      onCreated(await post<PortfolioDetail>("/api/portfolios/from-template", { template_id: t.id, amount: Number(amount) }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error");
    } finally {
      setBusy(null);
    }
  };

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-end gap-3">
        <div>
          <h2 className="text-lg font-semibold">Model portfolios</h2>
          <p className="text-sm text-muted">Start from a ready-made mix. Each one buys the stocks in equal amounts at today&apos;s price.</p>
        </div>
        <label className="ml-auto text-sm text-muted">
          Amount to invest
          <div className="mt-1 flex items-center rounded border border-line bg-bg px-2 focus-within:border-accent">
            <span>$</span>
            <input type="number" min="1" value={amount} onChange={(e) => setAmount(e.target.value)} className="tabular w-28 bg-transparent px-1 py-1.5 text-text outline-none" />
          </div>
        </label>
        {onCancel && (
          <button onClick={onCancel} className="rounded-md px-3 py-2 text-sm text-muted hover:text-text">
            Cancel
          </button>
        )}
      </div>
      {error && <p className="mb-4 rounded-md bg-down/10 px-3 py-2 text-sm text-down">{error}</p>}
      {!templates && !error && <p className="text-sm text-muted">Loading models…</p>}
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {templates?.map((t) => (
          <div key={t.id} className="flex flex-col rounded-xl border border-line bg-panel p-4">
            <div className="flex items-start justify-between gap-2">
              <h3 className="font-semibold">{t.name}</h3>
              <span className={`whitespace-nowrap rounded px-1.5 py-0.5 text-[11px] font-medium ${PROFILE_STYLE[t.profile]}`}>{t.detected.label.split(" + ")[0]}</span>
            </div>
            <p className="mt-1 flex-1 text-sm text-muted">{t.description}</p>
            <div className="mt-3 flex flex-wrap gap-1">
              {t.symbols.map((s) => (
                <span key={s} className="rounded bg-line/60 px-1.5 py-0.5 text-[11px]">
                  {s}
                </span>
              ))}
            </div>
            <div className="mt-3 flex items-center justify-between">
              <RiskMeter level={t.detected.risk_level} />
              <button
                onClick={() => create(t)}
                disabled={busy !== null || !Number(amount)}
                className="rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-60"
              >
                {busy === t.id ? "Creating…" : "Use this model"}
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
