"use client";

import { useEffect, useState } from "react";
import { api, post, put } from "@/lib/api";
import type { NotifySettings } from "@/lib/types";

export default function NotificationsCard() {
  const [s, setS] = useState<NotifySettings | null>(null);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api<NotifySettings>("/api/notifications/settings").then(setS).catch(() => {});
  }, []);
  if (!s) return null;

  const save = async () => {
    setBusy(true);
    setMsg("");
    try {
      setS(await put<NotifySettings>("/api/notifications/settings", s));
      setMsg("Saved.");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Error");
    } finally {
      setBusy(false);
    }
  };

  const test = async () => {
    setMsg("");
    const r = await post<{ email: boolean | null; telegram: boolean | null }>("/api/notifications/test", {});
    const parts = [
      r.email === null ? null : `Email: ${r.email ? "sent" : "failed"}`,
      r.telegram === null ? null : `Telegram: ${r.telegram ? "sent" : "failed"}`,
    ].filter(Boolean);
    setMsg(parts.length ? parts.join(" · ") : "Enable a channel first.");
  };

  return (
    <section className="rounded-xl border border-line bg-panel p-4">
      <h2 className="mb-3 font-semibold">Notifications</h2>
      <div className="space-y-4 text-sm">
        <label className={`flex items-start gap-2 ${s.email_available ? "" : "opacity-50"}`}>
          <input type="checkbox" disabled={!s.email_available} checked={s.email_enabled} onChange={(e) => setS({ ...s, email_enabled: e.target.checked })} className="mt-0.5 accent-blue-500" />
          <span>
            Email to <b>{s.email}</b>
            {!s.email_available && <span className="block text-xs text-muted">Email isn&apos;t configured on the server yet.</span>}
          </span>
        </label>
        <div className={s.telegram_available ? "" : "opacity-50"}>
          <label className="flex items-start gap-2">
            <input
              type="checkbox"
              disabled={!s.telegram_available}
              checked={s.telegram_enabled}
              onChange={(e) => setS({ ...s, telegram_enabled: e.target.checked })}
              className="mt-0.5 accent-blue-500"
            />
            <span>
              Telegram
              {!s.telegram_available && <span className="block text-xs text-muted">Telegram isn&apos;t configured on the server yet.</span>}
            </span>
          </label>
          {s.telegram_available && (
            <div className="mt-2 pl-6">
              <input
                value={s.telegram_chat_id}
                onChange={(e) => setS({ ...s, telegram_chat_id: e.target.value.replace(/[^0-9-]/g, "") })}
                placeholder="Your Telegram chat ID"
                className="w-full rounded border border-line bg-bg px-2 py-1.5 outline-none focus:border-accent"
              />
              <p className="mt-1 text-xs text-muted">Send /start to our bot, then message @userinfobot to get your chat ID.</p>
            </div>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button onClick={save} disabled={busy} className="rounded-md bg-panel-2 px-3 py-1.5 hover:bg-line disabled:opacity-60">
            Save
          </button>
          <button onClick={test} className="rounded-md px-3 py-1.5 text-muted hover:text-text">
            Send test
          </button>
          {msg && <span className="text-xs text-muted">{msg}</span>}
        </div>
      </div>
    </section>
  );
}
