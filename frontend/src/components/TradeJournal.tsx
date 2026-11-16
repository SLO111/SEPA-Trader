"use client";

import { useEffect, useRef, useState } from "react";
import { api, put } from "@/lib/api";

type Note = { ref: string; setup: string; emotion: string; notes: string; image?: string | null; has_image: boolean };
let OPTIONS: Promise<{ setups: string[]; emotions: string[] }> | null = null;

/** Shrinks a picture to a JPEG of at most `maxW` pixels wide (keeps notes light). */
export async function shrinkImage(src: string, maxW = 1100, quality = 0.72): Promise<string> {
  const img = new Image();
  img.src = src;
  await img.decode();
  const scale = Math.min(1, maxW / img.width);
  const c = document.createElement("canvas");
  c.width = Math.round(img.width * scale);
  c.height = Math.round(img.height * scale);
  c.getContext("2d")!.drawImage(img, 0, 0, c.width, c.height);
  return c.toDataURL("image/jpeg", quality);
}

/** Journal for one trade: setup, emotion, what you learned, and a chart screenshot. */
export default function TradeJournal({ tradeRef, onSaved }: { tradeRef: string; onSaved?: () => void }) {
  const [opts, setOpts] = useState<{ setups: string[]; emotions: string[] } | null>(null);
  const [n, setN] = useState<Note | null>(null);
  const [msg, setMsg] = useState("");
  const file = useRef<HTMLInputElement>(null);

  useEffect(() => {
    OPTIONS ??= api<{ setups: string[]; emotions: string[] }>("/api/notes/options");
    OPTIONS.then(setOpts).catch(() => {});
    api<Note>(`/api/notes/${encodeURIComponent(tradeRef)}`)
      .then(setN)
      .catch(() => setN({ ref: tradeRef, setup: "", emotion: "", notes: "", has_image: false }));
  }, [tradeRef]);

  const save = async (patch: Partial<Note>) => {
    if (!n) return;
    const next = { ...n, ...patch };
    setN(next);
    try {
      const r = await put<Note>(`/api/notes/${encodeURIComponent(tradeRef)}`, patch);
      setN(r);
      setMsg("Saved");
      onSaved?.();
      setTimeout(() => setMsg(""), 1500);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Could not save");
    }
  };
  const upload = async (f: File) => {
    const url = await new Promise<string>((res) => {
      const r = new FileReader();
      r.onload = () => res(String(r.result));
      r.readAsDataURL(f);
    });
    save({ image: await shrinkImage(url) });
  };

  if (!n) return <p className="text-xs text-muted">Loading journal…</p>;
  const sel = "rounded-md border border-line bg-bg px-2 py-1 text-xs";
  return (
    <div className="rounded-lg border border-line bg-panel p-3" onClick={(e) => e.stopPropagation()}>
      <div className="mb-2 flex flex-wrap items-center gap-2 text-xs">
        <span className="font-semibold">📝 Journal</span>
        <select value={n.setup} onChange={(e) => save({ setup: e.target.value })} className={sel}>
          <option value="">Setup…</option>
          {opts?.setups.map((s) => <option key={s}>{s}</option>)}
        </select>
        <select value={n.emotion} onChange={(e) => save({ emotion: e.target.value })} className={sel}>
          <option value="">How I felt…</option>
          {opts?.emotions.map((s) => <option key={s}>{s}</option>)}
        </select>
        <button onClick={() => file.current?.click()} className="rounded-md bg-panel-2 px-2 py-1 hover:bg-line">{n.image ? "Replace screenshot" : "+ Screenshot"}</button>
        <input ref={file} type="file" accept="image/*" className="hidden" onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])} />
        {msg && <span className="text-muted">{msg}</span>}
      </div>
      <textarea
        defaultValue={n.notes}
        onBlur={(e) => e.target.value !== n.notes && save({ notes: e.target.value })}
        placeholder="Why did you take it? What went well, what would you do differently?"
        rows={3}
        className="w-full rounded-md border border-line bg-bg px-2 py-1.5 text-sm outline-none focus:border-accent"
      />
      {n.image && (
        <div className="mt-2">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={n.image} alt="Chart at the time of the trade" className="max-h-72 rounded border border-line" />
          <button onClick={() => save({ image: "" })} className="mt-1 text-[11px] text-muted hover:text-down">Remove screenshot</button>
        </div>
      )}
    </div>
  );
}
