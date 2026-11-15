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
