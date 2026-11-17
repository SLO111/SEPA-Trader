"""Broker import for portfolios: resolve symbols, check prices, and keep the portfolio in sync with each import.

* Trades: rows already in the portfolio (same date, symbol, side, quantity and price within 0.5%) are skipped,
  so importing the same file twice adds nothing and a newer file adds only what is new.
* Positions (a statement of open positions): the portfolio is reconciled to the statement on its "as of" date,
  buying or selling the difference so quantities and average costs match, and optionally closing positions that
  are no longer on the statement.
"""

from __future__ import annotations

import difflib
import logging
import re
from datetime import date

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from engine import broker_import
from engine.data.universe import SYMBOLS
from engine.portfolio import Txn, holdings, validate

from . import market_data
from .data_store import get_store
from .models import PortfolioTxn

log = logging.getLogger("sepa.import")
TICKER_RE = re.compile(r"^[A-Z]{1,5}(?:[.-][A-Z]{1,2})?$")
NAME_STOP = {"inc", "incorporated", "corp", "corporation", "ltd", "limited", "plc", "co", "company", "the", "nv", "sa", "ag", "se", "holdings",
             "holding", "common", "stock", "shares", "ordinary", "capital", "adr", "ads", "registered", "reg"}
_isin_cache: dict[str, str | None] = {}


# ------------------------------------------------------------------ symbols

def _clean_ticker(raw: str) -> str:
    s = (raw or "").strip().upper()
    s = s.split(":")[0]  # Saxo "NVDA:xnas"
    s = re.sub(r"\.(US|USA|NYSE|NASDAQ|OQ|N|O)$", "", s)  # XTB "AAPL.US", Reuters "AAPL.O"
    s = s.replace(" ", "").replace("/", "-")
    if re.match(r"^[A-Z]{1,4}\.[A-Z]$", s):  # BRK.B -> BRK-B
        s = s.replace(".", "-")
    return s


def _known(sym: str) -> bool:
    if sym in SYMBOLS:
        return True
    store = get_store()
    if store is not None and (sym in store.directory or sym in store.prices):
        return True
    if store is not None and store.directory:
        return False  # the full US directory is loaded: an unknown ticker isn't listed (no slow download)
    try:
        market_data.history(sym)
        return True
    except Exception:
        return False


def _norm_name(n: str) -> str:
    words = re.sub(r"[^a-z0-9 ]", " ", broker_import.norm(n)).split()
    return " ".join(w for w in words if w not in NAME_STOP)


def _by_isin(isin: str) -> str | None:
    if isin in _isin_cache:
        return _isin_cache[isin]
    store = get_store()
    try:
        hit = store.get_slow("isin", isin) if store is not None else None
    except Exception:
        hit = None
    if hit is not None:
        _isin_cache[isin] = hit.get("symbol")
        return _isin_cache[isin]
    from engine.data.providers import _finnhub

    fh = _finnhub()
    sym = None
    if fh is not None:
        try:
            res = fh.search(isin)
            plain = [r for r in res if "." not in (r.get("symbol") or "") and (r.get("type") or "").lower() in ("common stock", "adr", "etp", "etf", "")]
            pick = (plain or res or [None])[0]
            sym = pick.get("symbol") if pick else None
        except Exception:
            log.warning("ISIN lookup failed for %s", isin, exc_info=True)
    _isin_cache[isin] = sym
    if store is not None and sym:
        try:
            store.put_slow("isin", isin, {"symbol": sym})
        except Exception:
            log.warning("Could not cache the ISIN lookup for %s", isin, exc_info=True)
    return sym


def _by_name(name: str) -> str | None:
    target = _norm_name(name)
    if not target:
        return None
    cands: dict[str, str] = {_norm_name(m.get("name", "")): s for s, m in SYMBOLS.items()}
    store = get_store()
    if store is not None:
        for s, d in store.directory.items():
            cands.setdefault(_norm_name(d.get("name", "")), s)
    cands.pop("", None)
    first = target.split()[0]
    cls = re.search(r"\bclass ([a-z])\b", target)
    if cls:  # share classes must agree (Alphabet class C is GOOG, not GOOGL)
        cands = {k: v for k, v in cands.items() if re.search(rf"\bclass {cls.group(1)}\b", k)}
    # A wrong ticker is worse than none: accept a fuzzy match only when the first word of the name agrees
    # (e.g. "nvidia" / "nvidia corp") or the names are nearly identical.
    for cand in difflib.get_close_matches(target, list(cands), n=5, cutoff=0.8):
        ratio = difflib.SequenceMatcher(None, target, cand).ratio()
        if (cand.split() and cand.split()[0] == first and len(first) >= 3) or ratio >= 0.93:
            return cands[cand]
    starts = [k for k in cands if k.split() and k.split()[0] == first and len(first) >= 4]
    return cands[starts[0]] if len(starts) == 1 else None


def resolve(rec: dict) -> tuple[str | None, str]:
    """Returns (ticker or None, how it was found)."""
    raw = _clean_ticker(rec.get("raw_symbol", ""))
    isin = rec.get("isin") or ""
    if not isin:
        m = broker_import.ISIN_RE.search((rec.get("raw_symbol") or "").upper())
        isin = m.group(1) if m else ""
    if raw and TICKER_RE.match(raw) and not broker_import.ISIN_RE.match(raw) and _known(raw):
        return raw, "ticker"
    if isin:
        sym = _by_isin(isin)
        if sym and _known(_clean_ticker(sym)):
            return _clean_ticker(sym), "ISIN"
    for text in (rec.get("name"), rec.get("raw_symbol")):
        if text and not TICKER_RE.match(_clean_ticker(text) or "-"):
            sym = _by_name(text)
            if sym:
                return sym, "name"
    if raw and TICKER_RE.match(raw):
        return raw, "ticker (unverified)"
    return None, "unresolved"


def _price_ok(sym: str, day: str | None, price: float | None) -> str | None:
    if not price or not day:
        return None
    try:
        ref = market_data.close_on(sym, day)
    except Exception:
        return None
    if ref and not (ref * 0.65 <= price <= ref * 1.35):
        return f"price {price:g} is far from the close on {day} ({ref:.2f}): different currency or ticker?"
    return None


# ------------------------------------------------------------------ preview / apply

def _existing(db: Session, pid: int) -> list[PortfolioTxn]:
    return db.scalars(select(PortfolioTxn).where(PortfolioTxn.portfolio_id == pid)).all()


def _txns(rows) -> list[Txn]:
    return [Txn(date=pd.Timestamp(r.date if hasattr(r, "date") else r["date"]).date(), symbol=(r.symbol if hasattr(r, "symbol") else r["symbol"]),
                side=(r.side if hasattr(r, "side") else r["side"]), shares=float(r.shares if hasattr(r, "shares") else r["shares"]),
                price=float(r.price if hasattr(r, "price") else r["price"]), fees=float(getattr(r, "fees", None) if hasattr(r, "fees") else r.get("fees", 0.0)) or 0.0)
            for r in rows]


def _is_dup(r: dict, existing: list[PortfolioTxn]) -> bool:
    for x in existing:
        if (x.symbol == r["symbol"] and x.side == r["side"] and x.date.isoformat() == r["date"] and abs(x.shares - r["shares"]) < 1e-6
                and abs(x.price - r["price"]) <= max(0.01, r["price"] * 0.005)):
            return True
    return False


def plan_positions(db: Session, pid: int, rows: list[dict], as_of: str, close_missing: bool) -> list[dict]:
    """Transactions that bring the portfolio to the statement's quantities and average costs on `as_of`."""
    current = holdings(_txns(_existing(db, pid)))
    target: dict[str, dict] = {}
    for r in rows:
        if r.get("include", True) and r.get("symbol"):
            t = target.setdefault(r["symbol"], {"shares": 0.0, "cost": 0.0, "current": r.get("current")})
            t["shares"] += float(r["shares"])
            t["cost"] += float(r["shares"]) * float(r["price"])
    changes = []
    for sym, t in target.items():
        have = current.get(sym, {"shares": 0.0, "cost": 0.0})
        diff = round(t["shares"] - have["shares"], 8)
        avg_t = t["cost"] / t["shares"] if t["shares"] else 0.0
        if diff > 1e-9:
            price = (t["cost"] - have["cost"]) / diff if have["shares"] else avg_t
            if not price or price <= 0 or not (avg_t * 0.2 <= price <= avg_t * 5):
                price = avg_t
            changes.append({"symbol": sym, "side": "buy", "shares": diff, "price": round(price, 6), "date": as_of,
                            "note": "new position" if not have["shares"] else f"{have['shares']:g} → {t['shares']:g} shares"})
        elif diff < -1e-9:
            px = t.get("current") or market_data.close_on(sym, as_of) or avg_t
            changes.append({"symbol": sym, "side": "sell", "shares": -diff, "price": round(float(px), 6), "date": as_of,
                            "note": f"{have['shares']:g} → {t['shares']:g} shares"})
    if close_missing:
        for sym, h in current.items():
            if h["shares"] > 1e-9 and sym not in target:
                px = market_data.close_on(sym, as_of) or h["avg_cost"]
                changes.append({"symbol": sym, "side": "sell", "shares": h["shares"], "price": round(float(px), 6), "date": as_of,
                                "note": "not on the statement: closed"})
    return changes


def preview(db: Session, pid: int, filename: str, data: bytes, mapping: dict | None = None, header_row: int | None = None, table: int = 0) -> dict:
    res = broker_import.extract(filename, data, mapping, header_row, table)
    as_of = res.get("as_of") or date.today().isoformat()
    existing = _existing(db, pid)
    rows = []
    for i, rec in enumerate(res["records"]):
        sym, how = resolve(rec)
        r = {"id": i, "symbol": sym, "found_by": how, "name": rec.get("name", ""), "isin": rec.get("isin", ""), "raw_symbol": rec.get("raw_symbol", ""),
             "shares": rec["shares"], "price": rec["price"], "fees": rec.get("fees", 0.0), "current": rec.get("current"),
             "date": rec.get("date", as_of), "side": rec.get("side", "buy"), "status": "ok", "note": "", "include": True}
        if not sym:
            r.update(status="unresolved", note="Type the ticker for this row", include=False)
        elif res["kind"] == "trades" and _is_dup(r, existing):
            r.update(status="duplicate", note="already in this portfolio", include=False)
        else:
            warn = _price_ok(sym, r["date"], rec.get("current") if res["kind"] == "positions" else rec["price"])
            if warn:
                r.update(status="check", note=warn)
        rows.append(r)
    out = {"kind": res["kind"], "as_of": as_of, "format": res["format"], "rows": rows, "skipped": res["skipped"], "tables": res.get("tables", []),
           "mapping": res.get("mapping"), "header_row": res.get("header_row")}
    if res["kind"] == "positions":
        try:
            out["plan"] = plan_positions(db, pid, rows, as_of, True)
        except Exception as e:
            out["plan"], out["error"] = [], str(e)
    return out


def apply(db: Session, pid: int, kind: str, as_of: str, rows: list[dict], close_missing: bool = True) -> dict:
    existing = _existing(db, pid)
    good = [r for r in rows if r.get("include", True) and r.get("symbol") and float(r.get("shares") or 0) > 0 and float(r.get("price") or 0) > 0]
    for r in good:
        r["symbol"] = _clean_ticker(r["symbol"])
    if kind == "positions":
        new = plan_positions(db, pid, good, as_of, close_missing)
        dups = 0
    else:
        new, dups = [], 0
        for r in good:
            r = {**r, "shares": float(r["shares"]), "price": float(r["price"]), "fees": float(r.get("fees") or 0.0)}
            if _is_dup(r, existing):
                dups += 1
                continue
            new.append(r)
    validate(_txns(existing) + _txns(new))  # never oversell
    from .models import TxnOrigin

    for r in new:
        t = PortfolioTxn(portfolio_id=pid, date=pd.Timestamp(r["date"]).date(), symbol=r["symbol"], side=r["side"],
                         shares=float(r["shares"]), price=float(r["price"]), fees=float(r.get("fees") or 0.0))
        db.add(t)
        if kind == "positions" and r["side"] == "buy":
            db.flush()
            db.add(TxnOrigin(txn_id=t.id, origin="statement"))  # average cost on the import day, not the real buy
    db.commit()
    return {"added": len(new), "skipped_duplicates": dups, "changes": new}
