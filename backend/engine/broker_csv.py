"""Broker CSV import: turns a broker's trade export into portfolio transactions.

Recognised layouts: a generic one (date, symbol, side/action, quantity, price, fees), Interactive Brokers
activity statements (the "Trades" section, sells have a negative quantity), Trading 212 ("Market buy" /
"Limit sell" actions), Revolut ("BUY - MARKET"), and position exports with open and close columns
(e.g. XTB closed positions), which become a buy and a sell.
"""

from __future__ import annotations

import csv
import io
import re
from datetime import datetime

ALIASES = {
    "date": ["date", "date/time", "trade date", "tradedate", "time", "datetime", "execution time", "settle date"],
    "symbol": ["symbol", "ticker", "instrument", "stock", "security"],
    "side": ["side", "action", "type", "buy/sell", "transaction type", "direction", "b/s"],
    "shares": ["quantity", "shares", "qty", "no. of shares", "volume", "units", "amount of shares"],
    "price": ["price", "t. price", "price / share", "execution price", "avg price", "fill price", "price per share"],
    "fees": ["fees", "fee", "commission", "comm/fee", "comm", "commissions", "transaction fee"],
    "open_time": ["open time", "open date", "opening date"],
    "open_price": ["open price", "opening price"],
    "close_time": ["close time", "close date", "closing date"],
    "close_price": ["close price", "closing price"],
}
DATE_FORMATS = ["%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d, %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M",
                "%d.%m.%Y", "%d/%m/%Y", "%m/%d/%Y", "%d/%m/%Y %H:%M", "%m/%d/%Y %H:%M", "%Y%m%d", "%Y/%m/%d"]


def _num(x) -> float | None:
    if x is None:
        return None
    s = str(x).strip().replace(" ", "").replace(" ", "")
    if not s:
        return None
    s = re.sub(r"[^\d,.\-]", "", s)
    if s.count(",") and s.count("."):
        s = s.replace(",", "") if s.rfind(".") > s.rfind(",") else s.replace(".", "").replace(",", ".")
    elif s.count(",") == 1 and len(s.split(",")[1]) != 3:
        s = s.replace(",", ".")
    else:
        s = s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


def _date(x) -> str | None:
    s = str(x or "").strip().replace("Z", "")
    if not s:
        return None
    s = re.sub(r"(\d{2}:\d{2}:\d{2})\.\d+$", r"\1", s)  # drop fractions of a second only
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    m = re.match(r"(\d{4}-\d{2}-\d{2})", s)
    return m.group(1) if m else None


def _symbol(x) -> str:
    s = str(x or "").strip().upper()
    s = s.split(".")[0] if re.match(r"^[A-Z]+\.(US|USA|NYSE|NASDAQ)$", s) else s  # XTB "AAPL.US"
    return s.replace("/", "-").replace(" ", "")


def _map(header: list[str]) -> dict[str, int]:
    norm = [h.strip().lower() for h in header]
    out = {}
    for key, names in ALIASES.items():
        for n in names:
            if n in norm:
                out[key] = norm.index(n)
                break
    return out


def _ibkr_rows(text: str) -> tuple[list[str], list[list[str]]] | None:
    rows = list(csv.reader(io.StringIO(text)))
    header, data = None, []
    for r in rows:
        if len(r) > 2 and r[0] == "Trades" and r[1] == "Header":
            header = r[2:]
        elif header and len(r) > 2 and r[0] == "Trades" and r[1] == "Data" and (len(r) < 4 or r[2] in ("Order", "Trade", "")):
            data.append(r[2:])
    return (header, data) if header else None


def parse(text: str) -> dict:
    text = text.lstrip("﻿")
    fmt = "generic"
    ib = _ibkr_rows(text)
    if ib:
        header, rows = ib
        fmt = "Interactive Brokers"
    else:
        sample = text[:4096]
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        all_rows = [r for r in csv.reader(io.StringIO(text), dialect) if any(c.strip() for c in r)]
        if not all_rows:
            return {"format": fmt, "txns": [], "skipped": [{"row": 0, "reason": "Empty file"}]}
        header, rows = all_rows[0], all_rows[1:]
    col = _map(header)
    txns, skipped = [], []
    positions = {"open_time", "open_price", "close_time", "close_price"} <= set(col)
    if positions:
        fmt = "positions (open/close)"
    for n, r in enumerate(rows, start=2):
        get = lambda k: r[col[k]] if k in col and col[k] < len(r) else None
        sym = _symbol(get("symbol"))
        qty = _num(get("shares"))
        fees = abs(_num(get("fees")) or 0.0)
        if not sym or qty is None or qty == 0:
            skipped.append({"row": n, "reason": "missing symbol or quantity"})
            continue
        if positions:
            od, op, cd, cp = _date(get("open_time")), _num(get("open_price")), _date(get("close_time")), _num(get("close_price"))
            side_txt = str(get("side") or "buy").lower()
            if not (od and op):
                skipped.append({"row": n, "reason": "missing open date or price"})
                continue
            if "sell" in side_txt or "short" in side_txt:
                skipped.append({"row": n, "reason": "short positions can't be added to a portfolio"})
                continue
            txns.append({"date": od, "symbol": sym, "side": "buy", "shares": abs(qty), "price": op, "fees": fees / 2})
            if cd and cp:
                txns.append({"date": cd, "symbol": sym, "side": "sell", "shares": abs(qty), "price": cp, "fees": fees / 2})
            continue
        d, price = _date(get("date")), _num(get("price"))
        if not d or not price or price <= 0:
            skipped.append({"row": n, "reason": "missing date or price"})
            continue
        side_txt = str(get("side") or "").lower()
        if "buy" in side_txt or side_txt in ("b", "bot", "long"):
            side = "buy"
        elif "sell" in side_txt or side_txt in ("s", "sld"):
            side = "sell"
        elif not side_txt or fmt == "Interactive Brokers":
            side = "sell" if qty < 0 else "buy"
        else:
            skipped.append({"row": n, "reason": f"not a trade ({get('side')})"})
            continue
        txns.append({"date": d, "symbol": sym, "side": side, "shares": abs(qty), "price": price, "fees": fees})
    if fmt == "generic" and any("market" in str(r[col["side"]]).lower() for r in rows[:20] if "side" in col and col["side"] < len(r)):
        fmt = "Trading 212 / Revolut"
    txns.sort(key=lambda x: (x["date"], 0 if x["side"] == "buy" else 1))
    return {"format": fmt, "txns": txns, "skipped": skipped}


# ------------------------------------------------------------------ PDF statements

_SIDE = re.compile(r"\b(market buy|limit buy|buy|bought|purchase|market sell|limit sell|sell|sold|sale)\b", re.I)
_DATE = re.compile(
    r"\b(\d{4}-\d{2}-\d{2}|\d{1,2}[./]\d{1,2}[./]\d{4}|\d{1,2} (?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]* \d{4}|"
    r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]* \d{1,2},? \d{4})\b", re.I)
_TICKER = re.compile(r"^[A-Z]{1,5}(?:[.-][A-Z]{1,2})?$")
_NUM = re.compile(r"-?\d[\d,.]*")
_STOP = {"BUY", "SELL", "SOLD", "SALE", "USD", "EUR", "GBP", "RON", "CHF", "LTD", "INC", "PLC", "CORP", "ETF", "NYSE", "NASDAQ", "US", "THE", "AND",
         "LLC", "SA", "AG", "NV", "CO", "FEE", "FEES", "TAX", "QTY", "PRICE", "TOTAL", "DATE", "BOUGHT", "MARKET", "LIMIT", "ORDER", "ID", "AM", "PM", "UTC"}


def _pdf_date(s: str) -> str | None:
    d = _date(s)
    if d:
        return d
    for fmt in ("%d %b %Y", "%d %B %Y", "%b %d %Y", "%B %d %Y", "%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(s.replace(",", ", ").replace(",  ", ", ").title() if "," in s else s.title(), fmt).date().isoformat()
        except ValueError:
            continue
    return None


def parse_text(text: str) -> dict:
    """Find trade lines in free text (e.g. a PDF statement): a date, Buy/Sell, a ticker, then quantity and price."""
    txns, skipped = [], []
    for n, line in enumerate(text.splitlines(), start=1):
        m_side, m_date = _SIDE.search(line), _DATE.search(line)
        if not (m_side and m_date):
            continue
        d = _pdf_date(m_date.group(1))
        rest = (line[: m_date.start()] + " " + line[m_date.end():])
        tokens = re.split(r"[\s|;]+", rest)
        syms = [t.strip(",:()") for t in tokens if _TICKER.match(t.strip(",:()")) and t.strip(",:()") not in _STOP]
        if not d or not syms:
            skipped.append({"row": n, "reason": "trade line without a recognisable date or ticker"})
            continue
        sym = syms[0]
        after = rest[rest.find(sym) + len(sym):] if sym in rest else rest
        nums = [x for x in (_num(t) for t in _NUM.findall(after)) if x is not None and x != 0]
        if len(nums) < 2:
            skipped.append({"row": n, "reason": "quantity or price not found"})
            continue
        qty, price = abs(nums[0]), abs(nums[1])
        side = "sell" if re.search(r"sell|sold|sale", m_side.group(1), re.I) else "buy"
        txns.append({"date": d, "symbol": _symbol(sym), "side": side, "shares": qty, "price": price, "fees": 0.0})
    txns.sort(key=lambda x: (x["date"], 0 if x["side"] == "buy" else 1))
    return {"format": "PDF statement (auto-detected, please check the preview)", "txns": txns, "skipped": skipped}


def parse_pdf(data: bytes) -> dict:
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(data))
        text = "\n".join((p.extract_text() or "") for p in reader.pages[:200])
    except Exception:
        return {"format": "PDF", "txns": [], "skipped": [{"row": 0, "reason": "The PDF could not be read (scanned image or protected file)."}]}
    if not text.strip():
        return {"format": "PDF", "txns": [], "skipped": [{"row": 0, "reason": "The PDF has no text (it may be a scanned image)."}]}
    return parse_text(text)
