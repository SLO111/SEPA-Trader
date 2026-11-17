"""Universe of known symbols (for search and demo data). To be extended from the data provider later."""

SYMBOLS: dict[str, dict] = {
    "AAPL": {"name": "Apple Inc.", "sector": "Technology", "exchange": "NASDAQ"},
    "MSFT": {"name": "Microsoft Corp.", "sector": "Technology", "exchange": "NASDAQ"},
    "NVDA": {"name": "NVIDIA Corp.", "sector": "Technology", "exchange": "NASDAQ"},
    "GOOGL": {"name": "Alphabet Inc.", "sector": "Communication Services", "exchange": "NASDAQ"},
    "AMZN": {"name": "Amazon.com Inc.", "sector": "Consumer Discretionary", "exchange": "NASDAQ"},
    "META": {"name": "Meta Platforms Inc.", "sector": "Communication Services", "exchange": "NASDAQ"},
    "TSLA": {"name": "Tesla Inc.", "sector": "Consumer Discretionary", "exchange": "NASDAQ"},
    "AVGO": {"name": "Broadcom Inc.", "sector": "Technology", "exchange": "NASDAQ"},
    "AMD": {"name": "Advanced Micro Devices", "sector": "Technology", "exchange": "NASDAQ"},
    "NFLX": {"name": "Netflix Inc.", "sector": "Communication Services", "exchange": "NASDAQ"},
    "CRM": {"name": "Salesforce Inc.", "sector": "Technology", "exchange": "NYSE"},
    "PLTR": {"name": "Palantir Technologies", "sector": "Technology", "exchange": "NASDAQ"},
    "CRWD": {"name": "CrowdStrike Holdings", "sector": "Technology", "exchange": "NASDAQ"},
    "SHOP": {"name": "Shopify Inc.", "sector": "Technology", "exchange": "NYSE"},
    "SMCI": {"name": "Super Micro Computer", "sector": "Technology", "exchange": "NASDAQ"},
    "JPM": {"name": "JPMorgan Chase & Co.", "sector": "Financials", "exchange": "NYSE"},
    "V": {"name": "Visa Inc.", "sector": "Financials", "exchange": "NYSE"},
    "BRK-B": {"name": "Berkshire Hathaway B", "sector": "Financials", "exchange": "NYSE"},
    "JNJ": {"name": "Johnson & Johnson", "sector": "Health Care", "exchange": "NYSE"},
    "LLY": {"name": "Eli Lilly and Co.", "sector": "Health Care", "exchange": "NYSE"},
    "UNH": {"name": "UnitedHealth Group", "sector": "Health Care", "exchange": "NYSE"},
    "PG": {"name": "Procter & Gamble", "sector": "Consumer Staples", "exchange": "NYSE"},
    "KO": {"name": "Coca-Cola Co.", "sector": "Consumer Staples", "exchange": "NYSE"},
    "PEP": {"name": "PepsiCo Inc.", "sector": "Consumer Staples", "exchange": "NASDAQ"},
    "WMT": {"name": "Walmart Inc.", "sector": "Consumer Staples", "exchange": "NYSE"},
    "COST": {"name": "Costco Wholesale", "sector": "Consumer Staples", "exchange": "NASDAQ"},
    "XOM": {"name": "Exxon Mobil Corp.", "sector": "Energy", "exchange": "NYSE"},
    "CVX": {"name": "Chevron Corp.", "sector": "Energy", "exchange": "NYSE"},
    "T": {"name": "AT&T Inc.", "sector": "Communication Services", "exchange": "NYSE"},
    "VZ": {"name": "Verizon Communications", "sector": "Communication Services", "exchange": "NYSE"},
    "MO": {"name": "Altria Group", "sector": "Consumer Staples", "exchange": "NYSE"},
    "O": {"name": "Realty Income Corp.", "sector": "Real Estate", "exchange": "NYSE"},
    "NEE": {"name": "NextEra Energy", "sector": "Utilities", "exchange": "NYSE"},
    "DUK": {"name": "Duke Energy", "sector": "Utilities", "exchange": "NYSE"},
    "CAT": {"name": "Caterpillar Inc.", "sector": "Industrials", "exchange": "NYSE"},
    "GE": {"name": "GE Aerospace", "sector": "Industrials", "exchange": "NYSE"},
    "SPY": {"name": "SPDR S&P 500 ETF", "sector": "ETF", "exchange": "NYSE Arca"},
    "QQQ": {"name": "Invesco QQQ Trust", "sector": "ETF", "exchange": "NASDAQ"},
    "DIA": {"name": "SPDR Dow Jones Industrial Average ETF", "sector": "ETF", "exchange": "NYSE Arca"},
    "IWM": {"name": "iShares Russell 2000 ETF", "sector": "ETF", "exchange": "NYSE Arca"},
    "TLT": {"name": "iShares 20+ Year Treasury Bond ETF", "sector": "ETF", "exchange": "NASDAQ"},
    "HYG": {"name": "iShares iBoxx High Yield Corporate Bond ETF", "sector": "ETF", "exchange": "NYSE Arca"},
    "LQD": {"name": "iShares iBoxx Investment Grade Corporate Bond ETF", "sector": "ETF", "exchange": "NYSE Arca"},
    "^VIX": {"name": "CBOE Volatility Index", "sector": "Index", "exchange": "CBOE"},
}

NON_STOCK_SECTORS = {"ETF", "Index"}


def stock_symbols() -> list[str]:
    """Individual stocks only (no ETFs or indices): the universe for scans, screens and breadth."""
    return [s for s, m in SYMBOLS.items() if m["sector"] not in NON_STOCK_SECTORS]


def search(query: str, limit: int = 10) -> list[dict]:
    q = query.strip().upper()
    if not q:
        return []
    hits = [
        {"symbol": s, **meta}
        for s, meta in SYMBOLS.items()
        if s.startswith(q) or q in meta["name"].upper()
    ]
    hits.sort(key=lambda h: (not h["symbol"].startswith(q), h["symbol"]))
    return hits[:limit]


# S&P 500 constituents (symbol, name, GICS sector), maintained as open data on GitHub.
SP500_CSV = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv"
SECTOR_NAMES = {"Information Technology": "Technology"}


# Nasdaq-100 members that are not in the S&P 500 (foreign listings and recent additions). Added with UNIVERSE=sp500+.
# Symbols already in the S&P 500 list are simply skipped; a delisted symbol just gets no prices.
NASDAQ100_EXTRA: dict[str, dict] = {
    "ASML": {"name": "ASML Holding", "sector": "Technology", "exchange": "NASDAQ"},
    "ARM": {"name": "Arm Holdings", "sector": "Technology", "exchange": "NASDAQ"},
    "AZN": {"name": "AstraZeneca", "sector": "Health Care", "exchange": "NASDAQ"},
    "MELI": {"name": "MercadoLibre", "sector": "Consumer Discretionary", "exchange": "NASDAQ"},
    "PDD": {"name": "PDD Holdings", "sector": "Consumer Discretionary", "exchange": "NASDAQ"},
    "SHOP": {"name": "Shopify Inc.", "sector": "Technology", "exchange": "NASDAQ"},
    "TEAM": {"name": "Atlassian", "sector": "Technology", "exchange": "NASDAQ"},
    "ZS": {"name": "Zscaler", "sector": "Technology", "exchange": "NASDAQ"},
    "MRVL": {"name": "Marvell Technology", "sector": "Technology", "exchange": "NASDAQ"},
    "GFS": {"name": "GlobalFoundries", "sector": "Technology", "exchange": "NASDAQ"},
    "MSTR": {"name": "Strategy (MicroStrategy)", "sector": "Technology", "exchange": "NASDAQ"},
    "CCEP": {"name": "Coca-Cola Europacific Partners", "sector": "Consumer Staples", "exchange": "NASDAQ"},
    "TRI": {"name": "Thomson Reuters", "sector": "Industrials", "exchange": "NASDAQ"},
    "FER": {"name": "Ferrovial", "sector": "Industrials", "exchange": "NASDAQ"},
    "ALNY": {"name": "Alnylam Pharmaceuticals", "sector": "Health Care", "exchange": "NASDAQ"},
    "INSM": {"name": "Insmed", "sector": "Health Care", "exchange": "NASDAQ"},
    "MDB": {"name": "MongoDB", "sector": "Technology", "exchange": "NASDAQ"},
    "BIIB": {"name": "Biogen", "sector": "Health Care", "exchange": "NASDAQ"},
}


def parse_constituents(csv_text: str) -> dict[str, dict]:
    """Parse the S&P 500 constituents CSV into {symbol: {name, sector, exchange}} (Yahoo-style symbols)."""
    import csv
    import io

    out: dict[str, dict] = {}
    for row in csv.DictReader(io.StringIO(csv_text)):
        sym = (row.get("Symbol") or "").strip().upper().replace(".", "-")  # BRK.B -> BRK-B
        if not sym:
            continue
        sector = (row.get("GICS Sector") or row.get("Sector") or "Other").strip()
        out[sym] = {"name": (row.get("Security") or row.get("Name") or sym).strip(), "sector": SECTOR_NAMES.get(sector, sector), "exchange": ""}
    return out


def extend(entries: dict[str, dict]) -> int:
    """Add symbols to the universe in place (modules keep their reference to SYMBOLS). Returns how many were new."""
    new = [s for s in entries if s not in SYMBOLS]
    for s, meta in entries.items():
        if s in SYMBOLS:
            SYMBOLS[s] = {**SYMBOLS[s], "sector": SYMBOLS[s]["sector"] if SYMBOLS[s]["sector"] in NON_STOCK_SECTORS else meta["sector"]}
        else:
            SYMBOLS[s] = meta
    return len(new)


# Russell 1000 (large + mid caps) from the iShares IWB holdings file. With UNIVERSE=sp500+r1000 the largest
# `UNIVERSE_EXTRA` members that are not already in the universe are added (mid-cap growth names, new listings).
R1000_CSV = (
    "https://www.ishares.com/us/products/239707/ishares-russell-1000-etf/1467271812596.ajax"
    "?fileType=csv&fileName=IWB_holdings&dataType=fund"
)
ISHARES_SECTORS = {"Information Technology": "Technology", "Communication": "Communication Services"}
ISHARES_TICKERS = {"BRKB": "BRK-B", "BFB": "BF-B", "BFA": "BF-A", "LENB": "LEN-B", "HEIA": "HEI-A"}


def _num(text: str) -> float:
    try:
        return float((text or "").replace(",", "").strip() or 0)
    except ValueError:
        return 0.0


def parse_ishares_holdings(text: str) -> dict[str, dict]:
    """Parse an iShares holdings CSV (a few preamble lines, then a 'Ticker,...' table, then disclaimers).
    Equities only, Yahoo-style symbols, ordered by fund weight (largest first)."""
    import csv
    import io

    lines = text.lstrip("﻿").splitlines()
    start = next((i for i, ln in enumerate(lines) if ln.strip().strip('"').startswith("Ticker")), None)
    if start is None:
        return {}
    rows = []
    for row in csv.DictReader(io.StringIO("\n".join(lines[start:]))):
        if (row.get("Asset Class") or "").strip() != "Equity":
            continue
        raw = (row.get("Ticker") or "").strip().upper()
        sym = ISHARES_TICKERS.get(raw, raw.replace(".", "-").replace(" ", "-"))
        if not sym or not all(ch.isalpha() or ch == "-" for ch in sym):
            continue
        sector = (row.get("Sector") or "Other").strip()
        exch = (row.get("Exchange") or "").lower()
        rows.append((_num(row.get("Weight (%)", "")), sym, {
            "name": (row.get("Name") or sym).strip().title(),
            "sector": ISHARES_SECTORS.get(sector, sector),
            "exchange": "NASDAQ" if "nasdaq" in exch else "NYSE" if "new york" in exch else "",
        }))
    rows.sort(key=lambda r: -r[0])
    return {sym: meta for _, sym, meta in rows}


# Stocks from the ready-made theme lists that may sit outside the indexes (always scanned with the sp500 universes).
THEME_META: dict[str, dict] = {
    "TSM": {"name": "Taiwan Semiconductor", "sector": "Technology", "exchange": "NYSE"},
    "SNDK": {"name": "Sandisk", "sector": "Technology", "exchange": "NASDAQ"},
    "PSTG": {"name": "Pure Storage", "sector": "Technology", "exchange": "NYSE"},
    "CRWV": {"name": "CoreWeave", "sector": "Technology", "exchange": "NASDAQ"},
    "NBIS": {"name": "Nebius Group", "sector": "Technology", "exchange": "NASDAQ"},
    "VRT": {"name": "Vertiv Holdings", "sector": "Industrials", "exchange": "NYSE"},
    "SNOW": {"name": "Snowflake", "sector": "Technology", "exchange": "NYSE"},
    "NET": {"name": "Cloudflare", "sector": "Technology", "exchange": "NYSE"},
    "SOFI": {"name": "SoFi Technologies", "sector": "Financials", "exchange": "NASDAQ"},
    "HOOD": {"name": "Robinhood Markets", "sector": "Financials", "exchange": "NASDAQ"},
    "AFRM": {"name": "Affirm Holdings", "sector": "Financials", "exchange": "NASDAQ"},
    "IONQ": {"name": "IonQ", "sector": "Technology", "exchange": "NYSE"},
    "RGTI": {"name": "Rigetti Computing", "sector": "Technology", "exchange": "NASDAQ"},
    "QBTS": {"name": "D-Wave Quantum", "sector": "Technology", "exchange": "NYSE"},
    "QUBT": {"name": "Quantum Computing Inc.", "sector": "Technology", "exchange": "NASDAQ"},
    "CCJ": {"name": "Cameco", "sector": "Energy", "exchange": "NYSE"},
    "OKLO": {"name": "Oklo", "sector": "Utilities", "exchange": "NYSE"},
    "SMR": {"name": "NuScale Power", "sector": "Industrials", "exchange": "NYSE"},
    "NNE": {"name": "Nano Nuclear Energy", "sector": "Industrials", "exchange": "NASDAQ"},
    "LEU": {"name": "Centrus Energy", "sector": "Energy", "exchange": "NYSE"},
    "BWXT": {"name": "BWX Technologies", "sector": "Industrials", "exchange": "NYSE"},
    "MARA": {"name": "MARA Holdings", "sector": "Technology", "exchange": "NASDAQ"},
    "RIOT": {"name": "Riot Platforms", "sector": "Technology", "exchange": "NASDAQ"},
    "RIVN": {"name": "Rivian Automotive", "sector": "Consumer Discretionary", "exchange": "NASDAQ"},
    "LCID": {"name": "Lucid Group", "sector": "Consumer Discretionary", "exchange": "NASDAQ"},
    "TM": {"name": "Toyota Motor", "sector": "Consumer Discretionary", "exchange": "NYSE"},
    "NVO": {"name": "Novo Nordisk", "sector": "Health Care", "exchange": "NYSE"},
}
ETF_PRESETS = {"index-etfs", "sector-etfs"}
NON_STOCK_THEME = {"IBIT"}


def theme_symbols() -> dict[str, dict]:
    """Every stock in the ready-made theme lists (ETFs left out), with a name and sector."""
    from .presets import PRESETS

    out: dict[str, dict] = {}
    for p in PRESETS:
        if p["id"] in ETF_PRESETS:
            continue
        for s in p["symbols"]:
            if s in NON_STOCK_THEME or s in out:
                continue
            known = SYMBOLS.get(s)
            if known and known["sector"] in NON_STOCK_SECTORS:
                continue
            out[s] = THEME_META.get(s) or known or {"name": s, "sector": "Other", "exchange": ""}
    return out


def merge_universe(sp500: dict[str, dict], plus: bool, r1000: dict[str, dict] | None = None, extra: int = 0) -> dict[str, dict]:
    """The universe's entries: S&P 500 (its metadata wins), Nasdaq-100 extras with '+', the theme lists, and the
    largest `extra` Russell 1000 members not already included."""
    entries: dict[str, dict] = {**theme_symbols()}
    if plus:
        entries.update(NASDAQ100_EXTRA)
    entries.update(sp500)
    if r1000 and extra > 0:
        added = 0
        for s, meta in r1000.items():  # ordered by weight
            if added >= extra:
                break
            if s not in entries:
                entries[s] = meta
                added += 1
    return entries


# Fallback for the mid caps: the Nasdaq stock screener (every US-listed stock with market cap, sector and industry).
NASDAQ_SCREENER = "https://api.nasdaq.com/api/screener/stocks?tableonly=true&limit=10000&download=true"
NASDAQ_SECTORS = {"Finance": "Financials", "Basic Materials": "Materials", "Telecommunications": "Communication Services"}
_NOT_COMMON = ("warrant", "unit", " right", "preferred", "notes due", "debenture", "%")
_NAME_TAILS = (" Class A Common Stock", " Class B Common Stock", " Class C Capital Stock", " Common Stock", " Common Shares",
               " Ordinary Shares", " American Depositary Shares")


def parse_nasdaq_screener(payload: dict, min_price: float = 5.0) -> dict[str, dict]:
    """Common stocks from the Nasdaq screener JSON, priced at least `min_price`, largest market cap first."""
    rows = ((payload or {}).get("data") or {}).get("rows") or []
    out = []
    for r in rows:
        raw = (r.get("symbol") or "").strip().upper()
        name = (r.get("name") or "").strip()
        if not raw or "^" in raw or any(t in name.lower() for t in _NOT_COMMON):
            continue
        sym = raw.replace("/", "-").replace(".", "-")
        if not all(ch.isalpha() or ch == "-" for ch in sym):
            continue
        cap, price = _num(r.get("marketCap", "")), _num((r.get("lastsale") or "").replace("$", ""))
        if cap <= 0 or price < min_price:
            continue
        for tail in _NAME_TAILS:
            if name.endswith(tail):
                name = name[: -len(tail)]
                break
        sector = (r.get("sector") or "").strip() or "Other"
        out.append((cap, sym, {"name": name.strip() or sym, "sector": NASDAQ_SECTORS.get(sector, sector), "exchange": "",
                               "industry": (r.get("industry") or "").strip()}))
    out.sort(key=lambda x: -x[0])
    return {s: m for _, s, m in out}
