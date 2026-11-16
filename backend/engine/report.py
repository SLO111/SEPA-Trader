"""Automated company summary (rule-based takeaways) and the PDF report."""

from __future__ import annotations

import io
from datetime import date

import pandas as pd

from .indicators import sma


def period_returns(close: pd.Series) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    last = float(close.iloc[-1])
    for label, n in (("1W", 5), ("1M", 21), ("3M", 63), ("6M", 126), ("1Y", 252), ("3Y", 756)):
        out[label] = round((last / float(close.iloc[-1 - n]) - 1) * 100, 2) if len(close) > n else None
    jan1 = close[close.index < pd.Timestamp(year=close.index[-1].year, month=1, day=1)]
    out["YTD"] = round((last / float(jan1.iloc[-1]) - 1) * 100, 2) if len(jan1) else None
    return out


def takeaways(co: dict, sepa: dict | None, returns: dict, peers_pe: list[float]) -> list[dict]:
    """Plain-English observations, each tagged positive / negative / neutral."""
    out: list[dict] = []

    def add(tone: str, text: str):
        out.append({"tone": tone, "text": text})

    if sepa:
        tt = sepa["trend_template"]
        if tt["all_passed"]:
            add("positive", "Passes all 8 Trend Template criteria: the stock is in a confirmed long-term uptrend.")
        elif tt["passed_count"] <= 3:
            add("negative", f"Passes only {tt['passed_count']} of 8 Trend Template criteria: the long-term trend is weak.")
        else:
            add("neutral", f"Passes {tt['passed_count']} of 8 Trend Template criteria.")
        rs = sepa.get("rs_rating")
        if rs is not None:
            add("positive" if rs >= 80 else "negative" if rs < 40 else "neutral", f"RS Rating {rs}: outperforms {max(rs - 1, 0)}% of the stocks we track.")
        v = sepa.get("vcp") or {}
        if v.get("detected"):
            add("positive", f"Volatility Contraction Pattern detected, pivot {v['pivot']:.2f} ({v['distance_pct']}% from the current price).")
        md = sepa.get("move_detector")
        if md and md["bull"]["score"] is not None:
            b, r = md["bull"]["score"], md["bear"]["score"]
            if b >= 60:
                add("positive", f"Move Detector Bull Score {b:.0f}/100: set up for a potential move higher.")
            if r >= 60:
                add("negative", f"Move Detector Bear Score {r:.0f}/100: elevated risk of a move lower.")
    if returns.get("1Y") is not None:
        add("positive" if returns["1Y"] > 15 else "negative" if returns["1Y"] < -10 else "neutral", f"Price change over 1 year: {returns['1Y']:+.1f}%.")

    pr = co.get("profitability", {})
    if pr.get("revenue_growth") is not None:
        g = pr["revenue_growth"]
        add("positive" if g >= 15 else "negative" if g < 0 else "neutral", f"Revenue growth {g:+.1f}% year over year.")
    if pr.get("net_margin") is not None:
        m = pr["net_margin"]
        add("positive" if m >= 20 else "negative" if m < 0 else "neutral", f"Net profit margin {m:.1f}%." + (" The company is not profitable." if m < 0 else ""))
    pe = co.get("valuation", {}).get("pe")
    peers = [p for p in peers_pe if p]
    if pe and peers:
        med = float(pd.Series(peers).median())
        rel = pe / med - 1
        add("neutral" if abs(rel) < 0.2 else "negative" if rel > 0 else "positive",
            f"P/E {pe:.1f} vs. a sector median of {med:.1f}: {'about in line' if abs(rel) < 0.2 else 'a premium' if rel > 0 else 'a discount'}.")
    h = co.get("health", {})
    if h.get("debt_to_equity") is not None:
        de = h["debt_to_equity"]
        add("negative" if de > 2 else "positive" if de < 0.5 else "neutral", f"Debt-to-equity {de:.2f}.")
    d = co.get("dividends", {})
    if d.get("yield"):
        add("positive" if d["yield"] >= 2.5 else "neutral", f"Dividend yield {d['yield']:.2f}%" + (f", payout ratio {d['payout_ratio']:.0f}%." if d.get("payout_ratio") else "."))
    a = co.get("analysts")
    if a and a.get("rating"):
        txt = f"Analyst consensus: {a['rating']} ({a['total']} analysts)"
        if a.get("upside_pct") is not None:
            txt += f", mean price target {a['target_mean']:.2f} ({a['upside_pct']:+.1f}%)."
        add("positive" if a["rating"] in ("Buy", "Strong Buy") else "negative" if "Sell" in a["rating"] else "neutral", txt)
    return out


def verdict(items: list[dict]) -> str:
    pos = sum(i["tone"] == "positive" for i in items)
    neg = sum(i["tone"] == "negative" for i in items)
    if pos >= neg + 3:
        return "Mostly positive signals"
    if neg >= pos + 3:
        return "Mostly negative signals"
    return "Mixed signals"


# ------------------------------------------------------------------ PDF

def _money(v) -> str:
    if v is None:
        return "-"
    a = abs(v)
    s = f"{a / 1e12:.2f}T" if a >= 1e12 else f"{a / 1e9:.2f}B" if a >= 1e9 else f"{a / 1e6:.1f}M" if a >= 1e6 else f"{a:,.0f}"
    return ("-" if v < 0 else "") + "$" + s


def _f(v, suffix="", d=2) -> str:
    return "-" if v is None else f"{v:,.{d}f}{suffix}"


def _ascii(s: str) -> str:
    return (s or "").replace("−", "-").replace("–", "-").replace("—", "-").replace("×", "x").replace("≤", "<=").replace("≥", ">=").encode("latin-1", "replace").decode("latin-1")


def build_pdf(co: dict, quote: dict, history: pd.DataFrame, sepa: dict | None, items: list[dict], returns: dict, peers: list[dict]) -> bytes:
    from reportlab.graphics.charts.lineplots import LinePlot
    from reportlab.graphics.shapes import Drawing, String
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=14 * mm, bottomMargin=14 * mm,
                            title=f"{co['symbol']} report", author="Vnicorn Investments")
    ss = getSampleStyleSheet()
    H1 = ParagraphStyle("h1", parent=ss["Title"], alignment=0, fontSize=20, spaceAfter=2)
    H2 = ParagraphStyle("h2", parent=ss["Heading2"], fontSize=12.5, spaceBefore=10, spaceAfter=4, textColor=colors.HexColor("#1d4ed8"))
    P = ParagraphStyle("p", parent=ss["BodyText"], fontSize=9, leading=12.5)
    SMALL = ParagraphStyle("s", parent=P, fontSize=7.5, textColor=colors.HexColor("#64748b"))
    GREEN, RED, GREY = colors.HexColor("#15803d"), colors.HexColor("#b91c1c"), colors.HexColor("#475569")
    grid = TableStyle([
        ("FONT", (0, 0), (-1, -1), "Helvetica", 8.5), ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8.5),
        ("TEXTCOLOR", (0, 0), (-1, 0), GREY), ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ])
    kv = TableStyle([
        ("FONT", (0, 0), (-1, -1), "Helvetica", 8.5), ("TEXTCOLOR", (0, 0), (0, -1), GREY), ("TEXTCOLOR", (2, 0), (2, -1), GREY),
        ("TEXTCOLOR", (4, 0), (4, -1), GREY), ("FONT", (1, 0), (1, -1), "Helvetica-Bold", 8.5), ("FONT", (3, 0), (3, -1), "Helvetica-Bold", 8.5),
        ("FONT", (5, 0), (5, -1), "Helvetica-Bold", 8.5), ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
    ])
    st: list = []
    chg = quote.get("change_pct") or 0
    st.append(Paragraph(_ascii(f"{co['name']} ({co['symbol']})"), H1))
    st.append(Paragraph(_ascii(f"{co.get('exchange', '')} &middot; {co.get('sector', '')}{' &middot; ' + co['industry'] if co.get('industry') and co['industry'] != co.get('sector') else ''}"), SMALL))
    st.append(Spacer(1, 4))
    st.append(Paragraph(f"<font size=16><b>${quote['price']:,.2f}</b></font> &nbsp; <font color='{'#15803d' if chg >= 0 else '#b91c1c'}'>{chg:+.2f}% today</font> &nbsp; <font size=8 color='#64748b'>as of {quote['date']}</font>", P))
    if co.get("demo"):
        st.append(Spacer(1, 4))
        st.append(Paragraph("<font color='#b45309'><b>Demo data.</b> Prices and fundamentals in this report are generated for demonstration and are not real.</font>", P))

    st.append(Paragraph("Summary: " + verdict(items), H2))
    for i in items:
        color = {"positive": "#15803d", "negative": "#b91c1c"}.get(i["tone"], "#475569")
        mark = {"positive": "+", "negative": "-"}.get(i["tone"], "o")
        st.append(Paragraph(f"<font color='{color}'><b>{mark}</b></font>&nbsp; {_ascii(i['text'])}", P))

    # price chart, last year, with 50/200-day SMAs
    h = history.iloc[-252:]
    c = history["close"]
    lines = [h["close"], sma(c, 50).loc[h.index], sma(c, 200).loc[h.index]]
    d = Drawing(178 * mm, 62 * mm)
    lp = LinePlot()
    lp.x, lp.y, lp.width, lp.height = 10 * mm, 8 * mm, 162 * mm, 50 * mm
    lp.data = [[(i, float(v)) for i, v in enumerate(s) if pd.notna(v)] for s in lines]
    for k, col in enumerate([colors.HexColor("#1d4ed8"), colors.HexColor("#f59e0b"), colors.HexColor("#a855f7")]):
        lp.lines[k].strokeColor = col
        lp.lines[k].strokeWidth = 1.4 if k == 0 else 0.9
    lp.xValueAxis.visible = False
    lp.yValueAxis.labels.fontSize = 7
    lp.yValueAxis.labels.fontName = "Helvetica"
    lp.yValueAxis.strokeColor = colors.HexColor("#cbd5e1")
    d.add(lp)
    d.add(String(10 * mm, 59 * mm, "Price, last 12 months", fontName="Helvetica", fontSize=8, fillColor=GREY))
    d.add(String(52 * mm, 59 * mm, "Close", fontName="Helvetica", fontSize=8, fillColor=colors.HexColor("#1d4ed8")))
    d.add(String(64 * mm, 59 * mm, "SMA 50", fontName="Helvetica", fontSize=8, fillColor=colors.HexColor("#f59e0b")))
    d.add(String(79 * mm, 59 * mm, "SMA 200", fontName="Helvetica", fontSize=8, fillColor=colors.HexColor("#a855f7")))
    st.append(Spacer(1, 6))
    st.append(d)

    s, v, pr, hl, dv = co.get("stats", {}), co.get("valuation", {}), co.get("profitability", {}), co.get("health", {}), co.get("dividends", {})
    st.append(Paragraph("Key statistics", H2))
    stats = [
        ["Market cap", _money((s.get("market_cap_b") or 0) * 1e9 if s.get("market_cap_b") else None), "P/E", _f(v.get("pe"), d=1), "Gross margin", _f(pr.get("gross_margin"), "%", 1)],
        ["52-week range", f"{_f(s.get('week52_low'))} - {_f(s.get('week52_high'))}", "Forward P/E", _f(v.get("forward_pe"), d=1), "Net margin", _f(pr.get("net_margin"), "%", 1)],
        ["Beta", _f(s.get("beta")), "PEG", _f(v.get("peg")), "ROE", _f(pr.get("roe"), "%", 1)],
        ["EPS (TTM)", _f(s.get("eps_ttm")), "Price/Sales", _f(v.get("ps"), d=1), "Revenue growth", _f(pr.get("revenue_growth"), "%", 1)],
        ["Dividend yield", _f(dv.get("yield"), "%"), "Price/Book", _f(v.get("pb"), d=1), "Debt/Equity", _f(hl.get("debt_to_equity"))],
    ]
    t = Table(stats, colWidths=[27 * mm, 31 * mm, 24 * mm, 26 * mm, 30 * mm, 26 * mm])
    t.setStyle(kv)
    st.append(t)
    perf = [["1W", "1M", "3M", "6M", "YTD", "1Y", "3Y"], [_f(returns.get(k), "%", 1) for k in ["1W", "1M", "3M", "6M", "YTD", "1Y", "3Y"]]]
    t = Table(perf, colWidths=[25 * mm] * 7)
    t.setStyle(grid)
    st.append(Spacer(1, 6))
    st.append(t)

    if sepa:
        tt = sepa["trend_template"]
        st.append(Paragraph(f"SEPA analysis: Trend Template {tt['passed_count']}/8, RS Rating {sepa.get('rs_rating') or '-'}", H2))
        rows = [["Criterion", "Status"]] + [[_ascii(c["label"]), "Pass" if c["passed"] else "Fail"] for c in tt["criteria"]]
        t = Table(rows, colWidths=[140 * mm, 26 * mm])
        t.setStyle(grid)
        for k, c in enumerate(tt["criteria"], start=1):
            t.setStyle(TableStyle([("TEXTCOLOR", (1, k), (1, k), GREEN if c["passed"] else RED)]))
        st.append(t)
        vcp = sepa.get("vcp") or {}
        if vcp.get("pivot"):
            st.append(Spacer(1, 4))
            st.append(Paragraph(_ascii(f"VCP {'detected' if vcp['detected'] else 'not confirmed'}: contractions {' -> '.join(str(x['depth_pct']) + '%' for x in vcp['contractions'])}; pivot {vcp['pivot']:.2f}, stop {vcp['stop']:.2f}, risk {vcp['risk_pct']}%."), P))

    annual = co.get("financials", {}).get("annual", [])
    if annual:
        st.append(Paragraph("Financials (annual)", H2))
        keys = [("Revenue", "revenue"), ("Gross profit", "gross_profit"), ("Operating income", "operating_income"), ("Net income", "net_income"),
                ("EPS", "eps"), ("Free cash flow", "free_cash_flow"), ("Cash", "cash"), ("Total debt", "debt")]
        rows = [[""] + [a["period"] for a in annual]]
        for label, k in keys:
            rows.append([label] + [(_f(a.get(k)) if k == "eps" else _money(a.get(k))) for a in annual])
        t = Table(rows, colWidths=[40 * mm] + [31 * mm] * len(annual))
        t.setStyle(grid)
        st.append(t)

    hist = co.get("earnings", {}).get("history", [])
    if hist:
        st.append(Paragraph("Earnings history" + (f" (next report: {co['earnings']['next_date']})" if co["earnings"].get("next_date") else ""), H2))
        rows = [["Quarter", "EPS estimate", "EPS actual", "Surprise"]] + [[e["date"], _f(e["eps_estimate"]), _f(e["eps_actual"]), _f(e["surprise_pct"], "%", 1)] for e in hist[:8]]
        t = Table(rows, colWidths=[40 * mm, 40 * mm, 40 * mm, 40 * mm])
        t.setStyle(grid)
        st.append(t)

    a = co.get("analysts")
    if a and a.get("total"):
        st.append(Paragraph("Analyst ratings", H2))
        cnt = a["counts"]
        rows = [["Consensus", "Strong buy", "Buy", "Hold", "Sell", "Strong sell", "Mean target", "Upside"],
                [a["rating"] or "-", cnt.get("strong_buy", 0), cnt.get("buy", 0), cnt.get("hold", 0), cnt.get("sell", 0), cnt.get("strong_sell", 0),
                 _f(a.get("target_mean")), _f(a.get("upside_pct"), "%", 1)]]
        t = Table(rows, colWidths=[24 * mm, 20 * mm, 16 * mm, 16 * mm, 16 * mm, 22 * mm, 26 * mm, 26 * mm])
        t.setStyle(grid)
        st.append(t)

    if peers:
        st.append(Paragraph("Peers", H2))
        rows = [["Symbol", "Name", "Price", "Change", "Market cap", "P/E"]] + [
            [p["symbol"], _ascii(p["name"])[:32], _f(p.get("price")), _f(p.get("change_pct"), "%"), _money((p.get("market_cap_b") or 0) * 1e9 if p.get("market_cap_b") else None), _f(p.get("pe"), d=1)]
            for p in peers]
        t = Table(rows, colWidths=[20 * mm, 62 * mm, 22 * mm, 20 * mm, 24 * mm, 18 * mm])
        t.setStyle(grid)
        t.setStyle(TableStyle([("ALIGN", (1, 0), (1, -1), "LEFT")]))
        st.append(t)

    if co.get("profile", {}).get("description"):
        st.append(Paragraph("Company profile", H2))
        st.append(Paragraph(_ascii(co["profile"]["description"][:1800]), P))

    st.append(Spacer(1, 10))
    st.append(Paragraph(f"Generated by Vnicorn Investments on {date.today().isoformat()}. The summary is produced automatically from market data and technical rules. "
                        "For educational purposes only. Not financial advice.", SMALL))
    doc.build(st)
    return buf.getvalue()
