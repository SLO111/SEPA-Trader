import base64
import io

import pytest

from engine import broker_import


def _close(sym, day):
    from app import market_data

    return round(float(market_data.close_on(sym, day)), 2)


def _statement_pdf(rows, as_of="13-Nov-2026") -> bytes:
    """A positions statement laid out like a broker portfolio report: names wrapped over lines, ISIN, currency, qty, FX rate, prices."""
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    y = 800
    for line in ["Portfolio Report", f"Holdings, EUR  As of {as_of}", "Stocks", "Instrument", "Instrument currency Quantity Conversion Rate Open price Current price"]:
        c.drawString(40, y, line)
        y -= 16
    for name_lines, isin, qty, open_px, cur_px in rows:
        for i, part in enumerate(name_lines):
            c.drawString(40, y, part + (f" (ISIN:" if i == len(name_lines) - 1 else ""))
            y -= 14
        c.drawString(40, y, f"{isin})")
        y -= 14
        c.drawString(40, y, f"USD {qty} 0.90735 {open_px:.5f} {cur_px:.5f} -5.00% -10.00 100.00 1.00 %")
        y -= 20
    c.save()
    return buf.getvalue()


@pytest.fixture
def fake_finnhub(monkeypatch):
    isins = {"US67066G1040": "NVDA", "US0378331005": "AAPL", "US5949181045": "MSFT"}

    class Fake:
        def search(self, q):
            return [{"symbol": isins[q], "type": "Common Stock"}] if q in isins else []

    import engine.data.providers as prov
    from app import import_service

    import_service._isin_cache.clear()
    monkeypatch.setattr(prov, "_finnhub", lambda: Fake())


def test_positions_statement_pdf_with_wrapped_names():
    pdf = _statement_pdf([(["NVIDIA Corp."], "US67066G1040", 122, 190.04189, 162.85),
                          (["Space Exploration", "Technologies Corp."], "US84615Q1031", 23, 151.95913, 139.11),
                          (["Marvell T echnologyInc."], "US5738741041", 3, 220.97, 156.76)])
    r = broker_import.extract("Portfolio_2026-01-01_2026-11-13.pdf", pdf)
    assert r["kind"] == "positions" and r["as_of"] == "2026-11-13"
    got = {x["isin"]: (x["name"], x["shares"], x["price"], x["current"]) for x in r["records"]}
    assert got["US67066G1040"][1:] == (122, 190.04189, 162.85)
    assert got["US84615Q1031"][0].startswith("Space Exploration Technologies")
    assert got["US5738741041"][0] == "Marvell Technology Inc."


def test_excel_trades_romanian_headers_after_title_rows():
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Extras de cont"])
    ws.append(["Client: X"])
    ws.append([])
    ws.append(["Data", "Simbol", "Tip tranzactie", "Cantitate", "Preț", "Comision"])
    ws.append(["2025-03-03", "AAPL", "Cumpărare", 10, 180.5, 1])
    ws.append(["2025-04-01", "AAPL", "Vânzare", 4, 190, 1])
    ws.append(["2025-04-02", "", "Dividend", "", "", ""])
    buf = io.BytesIO()
    wb.save(buf)
    r = broker_import.extract("extras.xlsx", buf.getvalue())
    assert r["kind"] == "trades"
    assert [(x["date"], x["raw_symbol"], x["side"], x["shares"], x["price"]) for x in r["records"]] == [
        ("2025-03-03", "AAPL", "buy", 10, 180.5), ("2025-04-01", "AAPL", "sell", 4, 190)]


def test_german_csv_and_signed_quantities():
    de = "Datum;Wertpapier;Art;Stück;Kurs\n03.03.2025;Apple Inc.;Kauf;5;180,50\n10.03.2025;Apple Inc.;Verkauf;5;185,00\n"
    r = broker_import.extract("depot.csv", de.encode("cp1252"))
    assert r["kind"] == "trades" and [x["side"] for x in r["records"]] == ["buy", "sell"] and r["records"][0]["name"] == "Apple Inc."
    signed = "Trade Date,Ticker,Quantity,Price\n2025-01-02,MSFT,3,420\n2025-02-02,MSFT,-3,430\n"
    r2 = broker_import.extract("t.csv", signed.encode())
    assert [x["side"] for x in r2["records"]] == ["buy", "sell"]


def test_unrecognised_columns_then_manual_mapping():
    weird = "c1,c2,c3,c4,c5\n2025-01-02,NVDA,B,2,130\n2025-02-03,NVDA,S,2,140\n"
    r = broker_import.extract("x.csv", weird.encode())
    assert r["kind"] is None and r["tables"]
    m = broker_import.extract("x.csv", weird.encode(), mapping={"date": 0, "symbol": 1, "side": 2, "shares": 3, "price": 4}, header_row=0)
    assert m["kind"] == "trades" and [x["side"] for x in m["records"]] == ["buy", "sell"]


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def test_trades_import_dedupes_on_reimport(client, register, fake_finnhub):
    h, _ = register("imp-trades@test.ro")
    pf = client.post("/api/portfolios", headers=h, json={"name": "Imp"}).json()
    a, b = _close("AAPL", "2025-03-03"), _close("AAPL", "2025-05-01")
    csv = f"Date,Symbol,Side,Quantity,Price\n2025-03-03,AAPL,BUY,10,{a}\n2025-05-01,AAPL,SELL,4,{b}\n".encode()
    prev = client.post(f"/api/portfolios/{pf['id']}/import/preview", headers=h, json={"filename": "t.csv", "content_base64": _b64(csv)}).json()
    assert prev["kind"] == "trades" and all(r["status"] == "ok" for r in prev["rows"])
    ap = client.post(f"/api/portfolios/{pf['id']}/import/apply", headers=h, json={"kind": "trades", "as_of": prev["as_of"], "rows": prev["rows"]}).json()
    assert ap["added"] == 2
    again = client.post(f"/api/portfolios/{pf['id']}/import/preview", headers=h, json={"filename": "t.csv", "content_base64": _b64(csv)}).json()
    assert all(r["status"] == "duplicate" for r in again["rows"])
    ap2 = client.post(f"/api/portfolios/{pf['id']}/import/apply", headers=h,
                      json={"kind": "trades", "as_of": again["as_of"], "rows": [{**r, "include": True} for r in again["rows"]]}).json()
    assert ap2["added"] == 0 and ap2["skipped_duplicates"] == 2


def test_positions_statement_reconciles_portfolio(client, register, fake_finnhub):
    h, _ = register("imp-pos@test.ro")
    pf = client.post("/api/portfolios", headers=h, json={"name": "Saxo"}).json()
    day0, as_of = "2025-06-02", "2025-09-02"
    a0, m0 = _close("AAPL", day0), _close("MSFT", day0)
    seed = f"Date,Symbol,Side,Quantity,Price\n{day0},AAPL,BUY,10,{a0}\n{day0},MSFT,BUY,3,{m0}\n".encode()
    p0 = client.post(f"/api/portfolios/{pf['id']}/import/preview", headers=h, json={"filename": "s.csv", "content_base64": _b64(seed)}).json()
    client.post(f"/api/portfolios/{pf['id']}/import/apply", headers=h, json={"kind": "trades", "as_of": p0["as_of"], "rows": p0["rows"]})

    a1, n1 = _close("AAPL", as_of), _close("NVDA", as_of)
    avg_aapl = round((10 * a0 + 5 * a1) / 15, 4)
    pdf = _statement_pdf([(["Apple Inc."], "US0378331005", 15, avg_aapl, a1), (["NVIDIA Corp."], "US67066G1040", 4, n1, n1)], as_of="02-Sep-2025")
    prev = client.post(f"/api/portfolios/{pf['id']}/import/preview", headers=h, json={"filename": "report.pdf", "content_base64": _b64(pdf)}).json()
    assert prev["kind"] == "positions" and prev["as_of"] == as_of
    assert {r["symbol"] for r in prev["rows"]} == {"AAPL", "NVDA"} and all(r["found_by"] in ("ISIN", "ticker") for r in prev["rows"])
    plan = {(c["symbol"], c["side"]): c for c in prev["plan"]}
    assert plan[("AAPL", "buy")]["shares"] == 5 and abs(plan[("AAPL", "buy")]["price"] - a1) < 0.05  # keeps the statement's average cost
    assert plan[("NVDA", "buy")]["shares"] == 4 and plan[("MSFT", "sell")]["shares"] == 3  # MSFT is not on the statement: closed
    ap = client.post(f"/api/portfolios/{pf['id']}/import/apply", headers=h,
                     json={"kind": "positions", "as_of": prev["as_of"], "rows": prev["rows"], "close_missing": True}).json()
    assert ap["added"] == 3
    # importing the same statement again changes nothing
    again = client.post(f"/api/portfolios/{pf['id']}/import/preview", headers=h, json={"filename": "report.pdf", "content_base64": _b64(pdf)}).json()
    assert again["plan"] == []
    detail = client.get(f"/api/portfolios/{pf['id']}", headers=h).json()
    held = {p["symbol"]: p for p in detail["positions"]}
    assert held["AAPL"]["shares"] == 15 and "MSFT" not in held


def test_name_match_never_guesses_a_different_company():
    from app.import_service import _by_name

    assert _by_name("Space Exploration Technologies Corp. - SpaceX") is None  # not Palantir Technologies
    assert _by_name("NVIDIA Corp.") == "NVDA" and _by_name("Palantir Technologies Inc.") == "PLTR"


def test_share_class_must_match():
    from app.import_service import _by_name

    assert _by_name("Alphabet Inc. Class C") != "GOOGL"


def test_import_with_live_store_and_isin_cache(client, register, monkeypatch, fake_finnhub):
    """Production path: the data store is active (ISIN lookups are cached in it) — this used to fail with a 500."""
    from app import data_store as ds
    from app import import_service
    from app.db import SessionLocal
    from engine.data.providers import SyntheticProvider

    store = ds.DataStore(SyntheticProvider, SessionLocal)
    monkeypatch.setattr(import_service, "get_store", lambda: store)
    h, _ = register("imp-live@test.ro")
    pf = client.post("/api/portfolios", headers=h, json={"name": "Live"}).json()
    as_of = "2025-09-02"
    pdf = _statement_pdf([(["NVIDIA Corp."], "US67066G1040", 4, _close("NVDA", as_of), _close("NVDA", as_of))], as_of="02-Sep-2025")
    r = client.post(f"/api/portfolios/{pf['id']}/import/preview", headers=h, json={"filename": "r.pdf", "content_base64": _b64(pdf)})
    assert r.status_code == 200, r.text
    assert r.json()["rows"][0]["symbol"] == "NVDA" and r.json()["rows"][0]["found_by"] == "ISIN"
    assert store.get_slow("isin", "US67066G1040") == {"symbol": "NVDA"}
    fresh = ds.DataStore(SyntheticProvider, SessionLocal)
    fresh.load_all()
    assert fresh.get_slow("isin", "US67066G1040") == {"symbol": "NVDA"}
    bad = client.post(f"/api/portfolios/{pf['id']}/import/preview", headers=h, json={"filename": "x.xlsx", "content_base64": _b64(b"PK\x03\x04garbage")})
    assert bad.status_code == 200 and bad.json()["kind"] is None  # unreadable file: a message, not a crash
