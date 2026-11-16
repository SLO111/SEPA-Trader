"""Universal broker import: any broker's export (CSV, Excel, PDF), either a list of trades or a statement
of open positions, turned into clean rows the portfolio can use.

Pipeline
  1. read the file into tables of text cells (CSV/TXT, Excel .xlsx/.xls, PDF in layout mode) and plain text;
  2. find the header row automatically (multilingual column names) in each table, or use a manual mapping;
  3. classify: TRADES (a date per row + side or signed quantity + price) or POSITIONS (quantity + average price);
  4. fall back to reading the text when no table is found (trade lines, or "name (ISIN) currency qty … price" lines);
  5. the caller resolves symbols (ticker / exchange code / ISIN / company name) and checks prices.
"""

from __future__ import annotations

import csv
import io
import re
import unicodedata
from datetime import date, datetime

from .broker_csv import _date, _ibkr_rows, _num, _pdf_date, parse_text

# ------------------------------------------------------------------ column names (normalised: lower case, no accents)
FIELDS: dict[str, list[str]] = {
    "date": ["date", "data", "datum", "fecha", "trade date", "transaction date", "execution date", "date/time", "datetime", "time", "execution time",
             "settlement date", "booking date", "data tranzactiei", "data executiei", "data operatiunii", "handelstag", "buchungsdatum", "ausfuhrungsdatum",
             "schlusstag", "date d'execution", "date de transaction", "fecha operacion", "fecha de ejecucion", "data operazione", "transactiedatum",
             "data transakcji", "open time", "open date", "trade time", "order date", "tradedate", "date executed"],
    "symbol": ["symbol", "ticker", "simbol", "instrument symbol", "symbol code", "code", "cod", "ticker symbol", "stock symbol", "kurzel", "mnemo",
               "instrument code", "epic"],
    "name": ["instrument", "name", "nume", "security", "stock", "description", "descriere", "denumire", "wertpapier", "bezeichnung", "titre", "libelle",
             "valor", "producto", "titolo", "fonds", "product", "produs", "asset", "company", "companie", "security name", "instrument name", "nazwa"],
    "isin": ["isin", "isin code", "cod isin", "isin/wkn"],
    "side": ["side", "type", "tip", "action", "actiune", "buy/sell", "b/s", "direction", "directie", "operation", "operatiune", "sens", "transaction type",
             "tip tranzactie", "tip ordin", "kauf/verkauf", "art", "transaktionsart", "geschaftsart", "achat/vente", "type d'operation", "compra/venta",
             "tipo", "operazione", "segno", "transactietype", "kupno/sprzedaz", "trade type", "order side", "buy / sell"],
    "shares": ["quantity", "qty", "shares", "units", "amount", "cantitate", "nr actiuni", "numar actiuni", "volume", "volum", "anzahl", "stuck", "stueck",
               "nominal", "quantite", "cantidad", "titulos", "quantita", "aantal", "ilosc", "no. of shares", "number of shares", "open quantity",
               "position", "pozitie", "units held", "holding", "shares held", "lots"],
    "price": ["price", "pret", "t. price", "execution price", "trade price", "fill price", "avg price", "average price", "open price", "cost price",
              "pret mediu", "pret deschidere", "pret executie", "pret unitar", "kurs", "ausfuhrungskurs", "einstandskurs", "kaufkurs", "prix", "cours",
              "prix moyen", "precio", "precio medio", "prezzo", "prezzo medio", "koers", "cena", "price / share", "price per share", "unit price",
              "avg cost", "average cost", "cost per share", "avg. price", "avg open price", "price (avg)", "purchase price", "entry price"],
    "current": ["current price", "pret curent", "market price", "last price", "last", "aktueller kurs", "cours actuel", "precio actual", "prezzo attuale",
                "mark price", "close price", "current", "quote"],
    "fees": ["fees", "fee", "commission", "commissions", "comision", "comisioane", "comm", "comm/fee", "gebuhr", "gebuhren", "provision", "frais",
             "comisiones", "commissioni", "kosten", "prowizja", "costs", "transaction costs"],
    "currency": ["currency", "moneda", "valuta", "wahrung", "devise", "divisa", "instrument currency", "ccy"],
    "close_date": ["close time", "close date", "closing date", "data inchidere"],
}
CURRENCIES = {"USD", "EUR", "GBP", "CHF", "RON", "CAD", "AUD", "JPY", "HKD", "SEK", "NOK", "DKK", "PLN", "HUF", "CZK", "GBX", "SGD"}
ISIN_RE = re.compile(r"\b([A-Z]{2}[A-Z0-9]{9}\d)\b")
BUY_WORDS = ("buy", "bought", "purchase", "cumpar", "kauf", "achat", "compra", "acquisto", "aankoop", "kupno", "long", "bot", "b")
SELL_WORDS = ("sell", "sold", "sale", "vanzare", "vand", "verkauf", "vente", "venta", "vendita", "verkoop", "sprzedaz", "short", "sld", "s")


def norm(s) -> str:
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", s.replace("_", " ")).strip(" :*#")


def _cell(v) -> str:
    if v is None:
        return ""
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d %H:%M:%S") if (v.hour or v.minute) else v.strftime("%Y-%m-%d")
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


# ------------------------------------------------------------------ 1. read

def read_file(filename: str, data: bytes) -> tuple[list[list[list[str]]], str, str]:
    """Returns (tables, plain text, file kind)."""
    name = (filename or "").lower()
    if name.endswith(".pdf") or data[:4] == b"%PDF":
        return _read_pdf(data) + ("pdf",)
    if name.endswith((".xlsx", ".xlsm")) or data[:2] == b"PK":
        return _read_xlsx(data), "", "excel"
    if name.endswith(".xls") or data[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        return _read_xls(data), "", "excel"
    text = _decode(data)
    return [_read_csv(text)], text, "csv"


def _decode(data: bytes) -> str:
    for enc in ("utf-8-sig", "utf-16", "cp1252", "latin-1"):
        try:
            t = data.decode(enc)
            if enc == "utf-16" and "\x00" in t:
                continue
            return t
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", "ignore")


def _read_csv(text: str) -> list[list[str]]:
    ib = _ibkr_rows(text)
    if ib:
        return [ib[0]] + ib[1]
    try:
        dialect = csv.Sniffer().sniff(text[:8192], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    return [[c.strip() for c in r] for r in csv.reader(io.StringIO(text), dialect) if any(c.strip() for c in r)]


def _read_xlsx(data: bytes) -> list[list[list[str]]]:
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    tables = []
    for ws in wb.worksheets:
        rows = [[_cell(v) for v in r] for r in ws.iter_rows(values_only=True)]
        rows = [r for r in rows if any(c for c in r)]
        if rows:
            tables.append(rows)
    return tables


def _read_xls(data: bytes) -> list[list[list[str]]]:
    import xlrd

    book = xlrd.open_workbook(file_contents=data)
    tables = []
    for sh in book.sheets():
        rows = []
        for i in range(sh.nrows):
            row = []
            for c in sh.row(i):
                if c.ctype == xlrd.XL_CELL_DATE:
                    row.append(_cell(xlrd.xldate.xldate_as_datetime(c.value, book.datemode)))
                else:
                    row.append(_cell(c.value))
            if any(row):
                rows.append(row)
        if rows:
            tables.append(rows)
    return tables


def _read_pdf(data: bytes) -> tuple[list[list[list[str]]], str]:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    pages = reader.pages[:300]
    text = "\n".join((p.extract_text() or "") for p in pages)
    rows = []
    for p in pages:
        try:
            lay = p.extract_text(extraction_mode="layout") or ""
        except Exception:
            lay = ""
        for line in lay.splitlines():
            cells = [c.strip() for c in re.split(r"\s{2,}", line.strip()) if c.strip()]
            if len(cells) >= 3:
                rows.append(cells)
    return [rows] if rows else [], text


# ------------------------------------------------------------------ 2. header detection

def _field_of(h: str) -> str | None:
    h = norm(h)
    if not h:
        return None
    for f, names in FIELDS.items():
        if h in names:
            return f
    best = None
    for f, names in FIELDS.items():
        for n in names:
            if len(n) >= 4 and (h.startswith(n + " ") or h.endswith(" " + n) or f" {n} " in f" {h} " or (n in h and len(h) <= len(n) + 12)):
                if best is None or len(n) > best[1]:
                    best = (f, len(n))
    return best[0] if best else None


def detect_header(rows: list[list[str]]) -> tuple[int, dict[str, int]] | None:
    best = None
    for i, r in enumerate(rows[:40]):
        mapping: dict[str, int] = {}
        for j, cell in enumerate(r):
            f = _field_of(cell)
            if f and f not in mapping:
                mapping[f] = j
        has_id = any(k in mapping for k in ("symbol", "name", "isin"))
        score = len(mapping) + (2 if has_id and "shares" in mapping and "price" in mapping else 0)
        if has_id and "shares" in mapping and ("price" in mapping or "current" in mapping) and (best is None or score > best[0]):
            best = (score, i, mapping)
    return (best[1], best[2]) if best else None


# ------------------------------------------------------------------ 3. rows → records

def _side(v: str, qty: float | None) -> str | None:
    s = norm(v)
    if s:
        words = re.split(r"[^a-z]+", s)
        if any(w in SELL_WORDS for w in words) or any(s.startswith(w) for w in SELL_WORDS if len(w) > 2):
            return "sell"
        if any(w in BUY_WORDS for w in words) or any(s.startswith(w) for w in BUY_WORDS if len(w) > 2):
            return "buy"
        return None  # dividends, deposits, fees…
    if qty is not None:
        return "sell" if qty < 0 else "buy"
    return None


def records_from_table(rows: list[list[str]], header: int, mapping: dict[str, int]) -> tuple[str, list[dict], list[dict]]:
    """Returns (kind, records, skipped)."""
    get = lambda r, k: r[mapping[k]] if k in mapping and mapping[k] < len(r) else ""
    body = rows[header + 1:]
    dated = sum(1 for r in body[:50] if _date(get(r, "date")))
    kind = "trades" if "date" in mapping and dated >= max(1, len(body[:50]) // 3) else "positions"
    out, skipped = [], []
    for n, r in enumerate(body, start=header + 2):
        if all(not c for c in r):
            continue
        qty = _num(get(r, "shares"))
        price = _num(get(r, "price")) or _num(get(r, "current"))
        sym, name, isin = get(r, "symbol"), get(r, "name"), get(r, "isin")
        blob = " ".join([sym, name, isin])
        m = ISIN_RE.search(blob.upper())
        isin = isin or (m.group(1) if m else "")
        if not (sym or name or isin):
            continue
        if qty is None or qty == 0 or price is None or price <= 0:
            if norm(name).startswith(("total", "subtotal", "summe", "gesamt")) or norm(sym).startswith("total"):
                continue
            skipped.append({"row": n, "reason": "no quantity or price"})
            continue
        rec = {"raw_symbol": sym, "name": name, "isin": isin, "shares": abs(qty), "price": price,
               "fees": abs(_num(get(r, "fees")) or 0.0), "currency": get(r, "currency").upper()[:3],
               "current": _num(get(r, "current"))}
        if kind == "trades":
            d = _date(get(r, "date"))
            side = _side(get(r, "side"), qty)
            if not d:
                skipped.append({"row": n, "reason": "no date"})
                continue
            if side is None:
                skipped.append({"row": n, "reason": f"not a trade ({get(r, 'side')})"})
                continue
            rec.update(date=d, side=side)
            # closed-position exports (open + close on one row) become a buy and a sell
            cd, cp = _date(get(r, "close_date")), _num(get(r, "current"))
            if cd and cp and "close_date" in mapping:
                out.append(rec)
                out.append({**rec, "date": cd, "side": "sell", "price": cp, "fees": 0.0})
                continue
        out.append(rec)
    return kind, out, skipped


# ------------------------------------------------------------------ 4. text fallback (PDF statements)

def _join_wrapped(text: str) -> str:
    """Re-attach lines broken inside a parenthesis or right after 'ISIN:'."""
    out, buf = [], ""
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        buf = f"{buf} {s}" if buf else s
        if buf.count("(") > buf.count(")") or buf.rstrip().endswith(("ISIN:", "(ISIN", "ISIN")):
            continue
        out.append(buf)
        buf = ""
    if buf:
        out.append(buf)
    return "\n".join(out)


def clean_name(name: str) -> str:
    """Undo PDF text glitches: 'T echnology' -> 'Technology', 'TechnologyInc.' -> 'Technology Inc.'."""
    n = re.sub(r"\b([A-Z]) ([a-z]{2,})", r"\1\2", name)
    n = re.sub(r"([a-z])(Inc\.?|Corp\.?|Ltd\.?|Group|Holdings|Plc|Co\.)(\b|$)", r"\1 \2", n)
    return re.sub(r"\s+", " ", n).strip(" -,")


def positions_from_text(text: str) -> list[dict]:
    """'Company name (ISIN: XX…) USD 10 0.90735 318.652 292.52 …' style lines: name + ISIN, then quantity and prices."""
    joined = _join_wrapped(text)
    lines = joined.splitlines()
    out = []
    for i, line in enumerate(lines):
        m = ISIN_RE.search(line)
        if not m:
            continue
        name = re.sub(r"\(?\s*ISIN:?\s*$", "", line[: m.start()]).strip(" (")
        j = i - 1
        if not name and i:
            name, j = lines[i - 1], i - 2
        # a company name broken over several lines: take the text-only line(s) just above
        while j >= 0 and len(name) < 80 and not re.search(r"\d", lines[j]) and not ISIN_RE.search(lines[j]) and 2 < len(lines[j]) < 50 \
                and not re.search(r"instrument|currency|quantity|price|stocks|total|holdings|page", lines[j], re.I):
            name = f"{lines[j]} {name}"
            j -= 1
        rest = line[m.end():].strip(" )")
        if not re.search(r"\d", rest) and i + 1 < len(lines):
            rest = lines[i + 1]
        toks = rest.split()
        cur = ""
        if toks and toks[0].upper() in CURRENCIES:
            cur = toks.pop(0).upper()
        nums = [_num(t) for t in toks if re.match(r"^-?[\d.,]+%?$", t) and not t.endswith("%")]
        nums = [x for x in nums if x is not None]
        if len(nums) < 2:
            continue
        qty = nums[0]
        rest_n = nums[1:]
        # skip an FX conversion rate (e.g. 0.90735) between the quantity and the price
        if len(rest_n) >= 3 and 0 < rest_n[0] < 10 and len(str(rest_n[0]).split(".")[-1]) >= 4:
            rest_n = rest_n[1:]
        price = rest_n[0]
        current = rest_n[1] if len(rest_n) > 1 else None
        if qty <= 0 or price <= 0:
            continue
        out.append({"raw_symbol": "", "name": clean_name(name), "isin": m.group(1),
                    "shares": qty, "price": price, "current": current, "fees": 0.0, "currency": cur})
    return out


def as_of_date(text: str, filename: str = "") -> str | None:
    t = text[:6000]
    for pat in (r"as of\s*[:\-]?\s*([0-9A-Za-z ,./-]{6,20})", r"per\s+([0-9]{1,2}[./-][0-9]{1,2}[./-][0-9]{2,4})", r"la data de\s+([0-9A-Za-z ,./-]{6,20})",
                r"stand[:\s]+([0-9]{1,2}\.[0-9]{1,2}\.[0-9]{4})", r"au\s+([0-9]{1,2}/[0-9]{1,2}/[0-9]{4})"):
        m = re.search(pat, t, re.I)
        if m:
            d = _any_date(m.group(1))
            if d:
                return d
    m = re.search(r"period[^\n]*?-\s*([0-9]{1,2}-[A-Za-z]{3}-[0-9]{4}|[0-9]{4}-[0-9]{2}-[0-9]{2}|[0-9]{1,2}[./][0-9]{1,2}[./][0-9]{4})", t, re.I)
    if m and _any_date(m.group(1)):
        return _any_date(m.group(1))
    found = sorted(d for d in (_any_date(x) for x in re.findall(r"\d{4}-\d{2}-\d{2}", filename or "")) if d)
    return found[-1] if found else None


def _any_date(s: str) -> str | None:
    s = s.strip().strip(".,")
    for fmt in ("%d-%b-%Y", "%d %b %Y", "%d %B %Y", "%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(s.title(), fmt).date().isoformat()
        except ValueError:
            continue
    return _date(s) or _pdf_date(s)


# ------------------------------------------------------------------ main entry

def extract(filename: str, data: bytes, mapping: dict[str, int] | None = None, header_row: int | None = None, table: int = 0) -> dict:
    """Parse any broker file. Returns kind (trades|positions), records, skipped, as_of, format and the tables' columns
    (for a manual mapping in the UI when nothing was recognised)."""
    try:
        tables, text, ftype = read_file(filename, data)
    except Exception as e:
        return {"kind": None, "records": [], "skipped": [{"row": 0, "reason": f"The file could not be read ({type(e).__name__})."}],
                "as_of": None, "format": "unreadable", "tables": []}
    previews = [{"index": i, "rows": t[:12]} for i, t in enumerate(tables)]
    as_of = as_of_date(text or "\n".join(" ".join(r) for t in tables for r in t[:15]), filename)

    if mapping:
        rows = tables[table] if table < len(tables) else []
        kind, recs, skipped = records_from_table(rows, header_row or 0, mapping)
        return {"kind": kind, "records": recs, "skipped": skipped, "as_of": as_of, "format": f"{ftype} · manual mapping", "tables": previews}

    best = None
    for t in tables:
        h = detect_header(t)
        if h:
            kind, recs, skipped = records_from_table(t, *h)
            if recs and (best is None or len(recs) > len(best[1])):
                best = (kind, recs, skipped, h)
    if best:
        return {"kind": best[0], "records": best[1], "skipped": best[2], "as_of": as_of, "format": f"{ftype} · columns detected", "tables": previews,
                "header_row": best[3][0], "mapping": best[3][1]}

    if text:
        pos = positions_from_text(text)
        trades = parse_text(text)["txns"]
        if len(pos) >= len(trades) and pos:
            return {"kind": "positions", "records": pos, "skipped": [], "as_of": as_of, "format": f"{ftype} · positions statement", "tables": previews}
        if trades:
            recs = [{"raw_symbol": t["symbol"], "name": "", "isin": "", "shares": t["shares"], "price": t["price"], "fees": t["fees"],
                     "date": t["date"], "side": t["side"], "currency": "", "current": None} for t in trades]
            return {"kind": "trades", "records": recs, "skipped": [], "as_of": as_of, "format": f"{ftype} · trade lines", "tables": previews}
    return {"kind": None, "records": [], "skipped": [{"row": 0, "reason": "No trades or positions recognised. Map the columns manually."}],
            "as_of": as_of, "format": ftype, "tables": previews}
