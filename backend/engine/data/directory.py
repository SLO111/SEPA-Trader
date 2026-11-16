"""Directory of every US-listed stock and ETF, from the official Nasdaq Trader symbol files (free, no API key,
updated daily): https://www.nasdaqtrader.com/trader.aspx?id=symboldirdefs

  nasdaqlisted.txt  NASDAQ-listed securities
  otherlisted.txt   NYSE, NYSE American, NYSE Arca, Cboe and IEX-listed securities
"""

from __future__ import annotations

NASDAQ_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
OTHER_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"

EXCHANGES = {"A": "NYSE American", "N": "NYSE", "P": "NYSE Arca", "Z": "Cboe BZX", "V": "IEX"}
# Instruments that are not ordinary shares or ETFs (warrants, rights, units, notes...).
SKIP_WORDS = (" warrant", " right", " unit", " units", " subordinated", " notes due", " debenture")


def _rows(text: str) -> list[dict]:
    lines = [ln for ln in text.splitlines() if ln.strip() and not ln.startswith("File Creation Time")]
    if not lines:
        return []
    header = lines[0].split("|")
    return [dict(zip(header, ln.split("|"))) for ln in lines[1:]]


def _keep(name: str, symbol: str) -> bool:
    low = f" {name.lower()}"
    return bool(symbol) and "$" not in symbol and not any(w in low for w in SKIP_WORDS)


def parse(nasdaq_text: str, other_text: str) -> dict[str, dict]:
    """{symbol: {name, exchange, etf}} using Yahoo-style symbols (BRK.B -> BRK-B)."""
    out: dict[str, dict] = {}
    for r in _rows(nasdaq_text):
        sym, name = (r.get("Symbol") or "").strip(), (r.get("Security Name") or "").strip()
        if r.get("Test Issue") == "Y" or not _keep(name, sym):
            continue
        out[sym.replace(".", "-")] = {"name": _clean(name), "exchange": "NASDAQ", "etf": r.get("ETF") == "Y"}
    for r in _rows(other_text):
        sym, name = (r.get("ACT Symbol") or "").strip(), (r.get("Security Name") or "").strip()
        if r.get("Test Issue") == "Y" or not _keep(name, sym):
            continue
        out[sym.replace(".", "-")] = {"name": _clean(name), "exchange": EXCHANGES.get(r.get("Exchange", ""), r.get("Exchange", "")), "etf": r.get("ETF") == "Y"}
    return out


def _clean(name: str) -> str:
    """'Apple Inc. - Common Stock' -> 'Apple Inc.'"""
    for sep in (" - Common Stock", " Common Stock", " - Class A Common Stock", " - Ordinary Shares", " Ordinary Shares"):
        if sep in name:
            return name.split(sep)[0].strip(" -")
    return name


def search(directory: dict[str, dict], query: str, limit: int = 10) -> list[dict]:
    """Exact symbol first, then symbols starting with the query, then names containing it (stocks before ETFs)."""
    q = query.strip().upper()
    if not q:
        return []
    exact, prefix, names = [], [], []
    for sym, meta in directory.items():
        if sym == q:
            exact.append(sym)
        elif sym.startswith(q):
            prefix.append(sym)
        elif q in meta["name"].upper():
            names.append(sym)
    prefix.sort(key=lambda s: (len(s), directory[s]["etf"], s))
    names.sort(key=lambda s: (directory[s]["etf"], not directory[s]["name"].upper().startswith(q), len(directory[s]["name"])))
    hits = (exact + prefix + names)[:limit]
    return [{"symbol": s, "name": directory[s]["name"], "exchange": directory[s]["exchange"], "sector": "ETF" if directory[s]["etf"] else ""} for s in hits]
