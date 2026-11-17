"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

/** In Backtest → Copied trades: which traders you copy, and whether they stopped sharing new trades. */
export default function CopyStatus() {
  const [f, setF] = useState<{ user_id: number; display_name: string; paused?: boolean }[]>([]);
  useEffect(() => {
    api<{ following: typeof f }>("/api/community/profile").then((r) => setF(r.following)).catch(() => {});
  }, []);
  if (!f.length) return null;
  return (
    <div className="mb-3 space-y-1.5">
      {f.map((x) =>
        x.paused ? (
          <p key={x.user_id} className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-sm text-amber-200">
            ⏸ <b>{x.display_name}</b> stopped sharing trades. Your copied trades stay and close normally; no new ones will be added.
          </p>
        ) : (
          <p key={x.user_id} className="rounded-lg border border-line bg-panel px-3 py-2 text-sm text-muted">
            Copying <b className="text-text">{x.display_name}</b>: their new chart trades appear here.
          </p>
        ),
      )}
    </div>
  );
}
