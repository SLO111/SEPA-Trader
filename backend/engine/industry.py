"""Industry group rankings: which groups lead the market (leaders tend to come from the strongest groups)."""

from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path

import numpy as np


@lru_cache(maxsize=1)
def gics_sub_industries() -> dict[str, str]:
    path = Path(__file__).parent / "data" / "sp500_constituents.csv"
    out = {}
    try:
        with open(path, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                out[r["Symbol"].replace(".", "-").upper()] = r.get("GICS Sub-Industry") or ""
    except OSError:
        pass
    return out


def group_of(symbol: str, sector: str = "", industry: str = "") -> str:
    return gics_sub_industries().get(symbol.upper()) or industry or sector or "Other"


def rank_groups(rows: list[dict], scan: list[dict], industries: dict[str, str] | None = None) -> list[dict]:
    """rows: market mover rows (symbol, sector, return_1m, return_3m, price); scan: Move Detector rows (rs_rating).
    Groups ranked by the average RS Rating of their members, then the 3-month return."""
    rs = {r["symbol"]: r.get("rs_rating") for r in scan}
    groups: dict[str, dict] = {}
    for r in rows:
        g = group_of(r["symbol"], r.get("sector", ""), (industries or {}).get(r["symbol"], ""))
        e = groups.setdefault(g, {"group": g, "sector": r.get("sector", ""), "members": []})
        e["members"].append({"symbol": r["symbol"], "rs": rs.get(r["symbol"]), "return_3m": r.get("return_3m"),
                             "return_1m": r.get("return_1m"), "change_pct": r.get("change_pct")})
    out = []
    for g in groups.values():
        m = g["members"]
        rsv = [x["rs"] for x in m if x["rs"] is not None]
        r3 = [x["return_3m"] for x in m if x["return_3m"] is not None]
        r1 = [x["return_1m"] for x in m if x["return_1m"] is not None]
        m.sort(key=lambda x: -(x["rs"] or 0))
        out.append({**g, "size": len(m), "avg_rs": round(float(np.mean(rsv)), 1) if rsv else None,
                    "return_3m": round(float(np.mean(r3)), 2) if r3 else None, "return_1m": round(float(np.mean(r1)), 2) if r1 else None,
                    "leaders_pct": round(100 * sum((x or 0) >= 80 for x in rsv) / len(rsv)) if rsv else 0})
    out.sort(key=lambda g: (-(g["avg_rs"] or 0), -(g["return_3m"] or 0)))
    for i, g in enumerate(out, 1):
        g["rank"] = i
    return out


def symbol_ranks(groups: list[dict]) -> dict[str, dict]:
    total = len(groups)
    return {m["symbol"]: {"group": g["group"], "rank": g["rank"], "of": total} for g in groups for m in g["members"]}
