from app.db import SessionLocal
from app.models import User
from engine.data.providers import SyntheticProvider
from engine.report import period_returns, takeaways, verdict


def _plan(email, plan):
    with SessionLocal() as db:
        u = db.query(User).filter_by(email=email).one()
        u.plan = plan
        db.commit()


def test_demo_company_is_consistent_and_honest():
    co = SyntheticProvider().company("KO")
    assert co["demo"] is True and co["sector"] == "Consumer Staples"
    a = co["financials"]["annual"]
    assert len(a) == 4 and a[0]["period"] > a[-1]["period"]
    assert all(abs(r["total_assets"] - r["total_liabilities"] - r["equity"]) < 2 for r in a)
    assert abs(a[0]["free_cash_flow"] - (a[0]["operating_cash_flow"] + a[0]["capex"])) < 2
    # no invented news, named holders or insiders in demo mode
    assert co["news"] == [] and co["ownership"]["top_holders"] == [] and co["ownership"]["insider_transactions"] == []
    assert sum(co["analysts"]["counts"].values()) == co["analysts"]["total"] > 0


def test_period_returns_and_takeaways():
    close = SyntheticProvider().history("MSFT")["close"]
    r = period_returns(close)
    assert set(r) == {"1W", "1M", "3M", "6M", "1Y", "3Y", "YTD"}
    assert abs(r["1M"] - (close.iloc[-1] / close.iloc[-22] - 1) * 100) < 0.01
    co = {"profitability": {"revenue_growth": 25, "net_margin": 30}, "valuation": {"pe": 40}, "health": {"debt_to_equity": 0.3},
          "dividends": {}, "analysts": {"rating": "Buy", "total": 30, "target_mean": 120, "upside_pct": 20}}
    items = takeaways(co, None, {"1Y": 40}, [20, 22, 25])
    tones = [i["tone"] for i in items]
    assert tones.count("positive") >= 4 and any("premium" in i["text"] for i in items)
    assert verdict(items) == "Mostly positive signals"


def test_stock_endpoint_and_pdf_gating(client, register):
    h, _ = register("stock-user@test.ro")
    r = client.get("/api/stock/nvda", headers=h)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["company"]["symbol"] == "NVDA" and d["quote"]["price"] > 0
    assert d["sepa"]["move_detector"] is None  # free plan
    assert d["peers"] and all(p["symbol"] != "NVDA" for p in d["peers"])
    assert d["takeaways"] and d["verdict"]
    assert client.get("/api/stock/ZZZZ", headers=h).status_code == 404
    assert client.get("/api/stock/NVDA/report.pdf", headers=h).status_code == 403

    _plan("stock-user@test.ro", "premium")
    pdf = client.get("/api/stock/NVDA/report.pdf", headers=h)
    assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf"
    assert pdf.content[:5] == b"%PDF-" and len(pdf.content) > 5000
    assert "NVDA-report-" in pdf.headers["content-disposition"]
