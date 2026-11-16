import numpy as np
import pandas as pd

from engine import broker_csv, chart_commentary, pulse, technicals
from engine.data.providers import SyntheticProvider
from engine.trade_grader import aggregate, analytics, grade_trade, round_trips


def frame(closes, spread=0.5, vol=1e6):
    idx = pd.bdate_range("2025-01-01", periods=len(closes))
    c = pd.Series(closes, index=idx, dtype=float)
    return pd.DataFrame({"open": c.shift().fillna(c), "high": c + spread, "low": c - spread, "close": c, "volume": vol}, index=idx)


def base_then(path_after):
    flat = list(100 + np.sin(np.arange(80) / 3) * 0.3)
    return frame(flat + list(path_after))


def d(df, i):
    return df.index[i].strftime("%Y-%m-%d")


# ---------------- TradeGrader
def test_bought_perfect_sold_perfect():
    df = base_then(np.linspace(100.3, 130, 30).tolist() + np.linspace(130, 120, 20).tolist())
    g = grade_trade({"symbol": "X", "side": "long", "entry_date": d(df, 80), "entry_price": 100.4, "exit_date": d(df, 109), "exit_price": 129.6}, df)
    assert g["entry_class"] == "Perfect" and g["exit_class"] == "Perfect" and g["grade"] in ("A", "B")


def test_bought_early_and_sold_early():
    df = base_then(np.linspace(100, 92, 8).tolist() + np.linspace(92, 115, 15).tolist() + np.linspace(115, 140, 20).tolist())
    g = grade_trade({"symbol": "X", "side": "long", "entry_date": d(df, 80), "entry_price": 100.2, "exit_date": d(df, 102), "exit_price": 115}, df)
    assert g["entry_class"] == "Early" and g["exit_class"] == "Early" and g["left_on_table_pct"] > 9


def test_bought_late_and_sold_late():
    df = base_then(np.linspace(100, 125, 12).tolist() + np.linspace(125, 145, 10).tolist() + np.linspace(145, 126, 15).tolist() + [125] * 15)
    g = grade_trade({"symbol": "X", "side": "long", "entry_date": d(df, 91), "entry_price": 125, "exit_date": d(df, 116), "exit_price": 127}, df)
    assert g["entry_class"] == "Late" and g["exit_class"] == "Late"
    a = aggregate([g])
    assert a["bought"][2]["label"] == "Late" and a["bought"][2]["pct"] == 100 and a["top_mistake"] in ("Bought late", "Sold late")


def test_open_trade_and_bad_price():
    df = base_then(np.linspace(100, 110, 20).tolist())
    g = grade_trade({"symbol": "X", "side": "long", "entry_date": d(df, 85), "entry_price": float(df["close"].iloc[85]), "exit_date": None, "exit_price": None}, df)
    assert g["open"] and g["grade"] is None and g["entry_class"]
    bad = grade_trade({"symbol": "X", "side": "long", "entry_date": d(df, 85), "entry_price": 500, "exit_date": None, "exit_price": None}, df)
    assert bad["grade"] is None and "far from" in bad["notes"][0]


def test_round_trips_fifo():
    tx = [{"date": "2025-01-02", "symbol": "a", "side": "buy", "shares": 10, "price": 10},
          {"date": "2025-01-05", "symbol": "A", "side": "buy", "shares": 10, "price": 12},
          {"date": "2025-02-01", "symbol": "A", "side": "sell", "shares": 15, "price": 15}]
    rt = round_trips(tx)
    closed = [r for r in rt if r["exit_date"]]
    assert [(r["entry_price"], r["shares"]) for r in closed] == [(10, 10), (12, 5)]
    assert [r for r in rt if not r["exit_date"]][0]["shares"] == 5


def test_analytics():
    trades = [{"exit_date": "2025-01-10", "pnl_pct": 10, "mfe_pct": 20}, {"exit_date": "2025-01-20", "pnl_pct": -5},
              {"exit_date": "2025-02-10", "pnl_pct": 6, "mfe_pct": 6}, {"exit_date": "2025-02-11", "pnl_pct": -3}]
    a = analytics(trades)
    assert a["trades"] == 4 and a["win_rate"] == 50 and a["avg_win_pct"] == 8 and a["avg_loss_pct"] == -4
    assert a["win_loss_ratio"] == 2 and a["expectancy_pct"] == 2 and a["capture_pct"] == 75
    assert [m["month"] for m in a["months"]] == ["2025-01", "2025-02"] and a["equity"][-1]["value"] == 8


# ---------------- broker CSV
def test_csv_generic_and_t212():
    r = broker_csv.parse("Date,Symbol,Side,Quantity,Price,Fees\n2025-03-01,AAPL,BUY,10,180.5,1\n2025-03-09,AAPL,SELL,10,190,1\nbad,,,,\n")
    assert [x["side"] for x in r["txns"]] == ["buy", "sell"] and r["txns"][0]["price"] == 180.5 and len(r["skipped"]) == 1
    t = broker_csv.parse("Action,Time,Ticker,No. of shares,Price / share\nMarket buy,2025-04-01 15:30:00,MSFT,2.5,400.10\nDeposit,2025-04-01 10:00:00,,,\n")
    assert t["txns"] == [{"date": "2025-04-01", "symbol": "MSFT", "side": "buy", "shares": 2.5, "price": 400.1, "fees": 0.0}]


def test_csv_ibkr_and_positions_and_european_numbers():
    ib = ("Statement,Header,Field Name\nTrades,Header,DataDiscriminator,Asset Category,Currency,Symbol,Date/Time,Quantity,T. Price,Comm/Fee\n"
          'Trades,Data,Order,Stocks,USD,NVDA,"2025-05-01, 10:00:00",5,120,-1\nTrades,Data,Order,Stocks,USD,NVDA,"2025-05-20, 10:00:00",-5,140,-1\n')
    r = broker_csv.parse(ib)
    assert r["format"] == "Interactive Brokers" and [x["side"] for x in r["txns"]] == ["buy", "sell"] and r["txns"][1]["shares"] == 5
    x = broker_csv.parse("Symbol;Type;Volume;Open time;Open price;Close time;Close price\nAAPL.US;BUY;3;01.06.2025 15:30:00;1.200,50;10.06.2025 16:00:00;1.250,00\n")
    assert [(t["side"], t["price"]) for t in x["txns"]] == [("buy", 1200.5), ("sell", 1250.0)] and x["txns"][0]["symbol"] == "AAPL"


# ---------------- Pulse, commentary, technicals
def test_pulse_signals():
    closes = [100] * 60 + [100, 101, 102, 104]
    df = frame(closes, spread=1.0)
    df.loc[df.index[-1], "volume"] = 3e6
    df.loc[df.index[-1], ["high", "close"]] = [104.2, 104]
    s = pulse.signals(df, last=3).iloc[-1]
    assert "Close near high" in s.conf and any("volume" in x for x in s.conf) and any("days up" in x for x in s.conf)
    down = frame([100] * 60 + [100, 99, 97, 93], spread=1.0)
    down.loc[down.index[-1], "volume"] = 3e6
    down.loc[down.index[-1], ["low", "close"]] = [92.8, 93]
    w = pulse.signals(down, last=3).iloc[-1]
    assert "Close near low" in w.warn and any("volume" in x for x in w.warn) and "Lower low" in w.warn
    falling = frame(list(np.linspace(150, 100, 80)), spread=1.0)
    falling["close"] = falling["low"] + 0.2  # every close near the low
    summ = pulse.summary(falling)
    assert summ["warn"] > summ["conf"] and summ["tone"] == "warning"


def test_commentary_and_technicals():
    p = SyntheticProvider()
    df, b = p.history("NVDA", "1d", 3), p.history("SPY", "1d", 3)
    a = chart_commentary.analyze(df, b, None, "NVDA")
    titles = [s["title"] for s in a["sections"]]
    assert "Trend & cycle" in titles and "Levels & risk" in titles and a["verdict"]
    t = technicals.rating(df)
    assert t["summary"]["buy"] + t["summary"]["sell"] + t["summary"]["neutral"] == 26
    assert len(t["oscillators"]["items"]) == 11 and len(t["moving_averages"]["items"]) == 15


# ---------------- API
def test_md_trades_grader_analytics_import(client, register):
    from app.db import SessionLocal
    from app.models import User

    h, _ = register("grader@test.ro")
    with SessionLocal() as db:
        db.query(User).filter_by(email="grader@test.ro").one().plan = "premium"
        db.commit()
    r = client.post("/api/paper-trades/scan", headers=h, json={"symbol": "AAPL", "side": "long"})
    assert r.status_code == 200, r.text
    t = r.json()
    assert t["stop"] < t["entry"] < t["target"] and t["plan_source"] in ("vnicornAI", "rules")
    assert client.post("/api/paper-trades/scan", headers=h, json={"symbol": "AAPL", "side": "long"}).status_code == 409
    assert client.get("/api/paper-trades?source=md", headers=h).json()["summary"]["trades"] == 1
    assert client.get("/api/paper-trades?source=ideas", headers=h).json()["summary"]["trades"] == 0

    pf = client.post("/api/portfolios", headers=h, json={"name": "Broker"}).json()
    csv = "Date,Symbol,Side,Quantity,Price\n2025-06-02,MSFT,BUY,10,{p1}\n2025-07-01,MSFT,SELL,10,{p2}\n"
    import app.market_data as md

    hist = md.history("MSFT")
    p1 = float(hist.loc[hist.index >= "2025-06-02", "close"].iloc[0])
    p2 = float(hist.loc[hist.index >= "2025-07-01", "close"].iloc[0])
    body = csv.format(p1=p1, p2=p2)
    prev = client.post(f"/api/portfolios/{pf['id']}/import", headers=h, json={"csv": body, "dry_run": True}).json()
    assert prev["saved"] == 0 and len(prev["txns"]) == 2 and prev["error"] is None
    assert client.post(f"/api/portfolios/{pf['id']}/import", headers=h, json={"csv": body, "dry_run": False}).json()["saved"] == 2

    g = client.get(f"/api/grader?source=portfolio&portfolio_id={pf['id']}", headers=h).json()
    assert g["summary"]["closed"] == 1 and g["trades"][0]["exit_class"] in ("Perfect", "Early", "Late", "Fair")
    md_g = client.get("/api/grader?source=md", headers=h).json()
    assert len(md_g["trades"]) == 1 and md_g["trades"][0]["entry_class"] == "Pending"  # taken today: too soon to judge
    a = client.get(f"/api/analytics?source=portfolio&portfolio_id={pf['id']}", headers=h).json()
    assert a["trades"] == 1
    assert client.get(f"/api/grader/chart?symbol=MSFT&start=2025-06-02&end=2025-07-01", headers=h).json()

    an = client.get("/api/market/analysis/AAPL", headers=h).json()
    assert an["sections"] and an["verdict"]
    tech = client.get("/api/stock/AAPL/technicals?interval=1wk", headers=h).json()
    assert tech["summary"]["label"]
    info = client.get("/api/market/info/AAPL", headers=h).json()
    assert info["pulse"] and "conf" in info["pulse"]
    scan = client.get("/api/sepa/scan", headers=h).json()["results"]
    assert any(r.get("pulse") for r in scan)


def test_pdf_statement_text_and_file():
    text = ("Account statement November 2025\n"
            "2025-03-03  Market buy  AAPL  Apple Inc.  10  180.50  USD 1,805.00\n"
            "03.04.2025 SELL NVDA 5 120,25 EUR\n"
            "Mar 5, 2025 Bought MSFT 2 401.10\n"
            "Deposit 2025-03-01 1000.00\n")
    r = broker_csv.parse_text(text)
    got = [(t["date"], t["symbol"], t["side"], t["shares"], t["price"]) for t in r["txns"]]
    assert ("2025-03-03", "AAPL", "buy", 10.0, 180.5) in got
    assert ("2025-04-03", "NVDA", "sell", 5.0, 120.25) in got
    assert ("2025-03-05", "MSFT", "buy", 2.0, 401.1) in got and len(got) == 3

    # a real PDF built with ReportLab, read back with pypdf
    import io

    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(50, 800, "2025-06-02 BUY META 4 650.00")
    c.drawString(50, 780, "2025-06-20 SELL META 4 700.00")
    c.save()
    p = broker_csv.parse_pdf(buf.getvalue())
    assert [(t["side"], t["price"]) for t in p["txns"]] == [("buy", 650.0), ("sell", 700.0)]
    assert broker_csv.parse_pdf(b"not a pdf")["txns"] == []


def test_csv_dotted_dates_without_time():
    r = broker_csv.parse("Date;Symbol;Side;Quantity;Price\n03.04.2025;AAPL;BUY;1;200,5\n2025-04-05T10:00:00.123;AAPL;SELL;1;210\n")
    assert [t["date"] for t in r["txns"]] == ["2025-04-03", "2025-04-05"]
