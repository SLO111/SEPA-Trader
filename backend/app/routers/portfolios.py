from typing import Literal
from datetime import date

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from engine.portfolio import (
    PERIODS,
    TEMPLATES,
    LedgerError,
    Txn,
    classify,
    dividends_received,
    holdings,
    period_start,
    stock_metrics,
    twr_index,
    validate,
    value_series,
)

from .. import market_data
from ..db import get_db
from ..models import Portfolio, PortfolioTxn, User
from ..plans import limits_for
from ..security import current_user

router = APIRouter(prefix="/api", tags=["portfolios"])

BENCHMARK = "SPY"


# ---------------------------------------------------------------- helpers

def _txns(p: Portfolio) -> list[Txn]:
    return [Txn(t.date, t.symbol, t.side, t.shares, t.price, t.fees) for t in p.transactions]


def _bench_close() -> pd.Series | None:
    try:
        return market_data.history(BENCHMARK)["close"]
    except Exception:
        return None


def _positions(txns: list[Txn]) -> tuple[list[dict], float]:
    """Open positions enriched with prices, fundamentals and risk metrics; plus total realized P/L."""
    bench = _bench_close()
    rows, realized = [], 0.0
    market_data.watch(*{t.symbol for t in txns})
    for sym, h in holdings(txns).items():
        realized += h["realized"]
        if h["shares"] <= 0:
            continue
        close = market_data.history(sym)["close"]
        last, prev = float(close.iloc[-1]), float(close.iloc[-2])
        f = market_data.fundamentals(sym)
        value = h["shares"] * last
        rows.append(
            {
                "symbol": sym,
                "name": f.get("name", sym),
                "sector": f.get("sector") or "Other",
                "shares": round(h["shares"], 6),
                "avg_cost": round(h["avg_cost"], 4),
                "price": round(last, 2),
                "value": round(value, 2),
                "cost": round(h["cost"], 2),
                "pnl": round(value - h["cost"], 2),
                "pnl_pct": round((value / h["cost"] - 1) * 100, 2) if h["cost"] else None,
                "day_change": round(h["shares"] * (last - prev), 2),
                "day_change_pct": round((last / prev - 1) * 100, 2),
                "fundamentals": f,
                "metrics": stock_metrics(close, bench, f.get("beta")),
            }
        )
    total = sum(r["value"] for r in rows)
    for r in rows:
        r["weight"] = round(r["value"] / total * 100, 2) if total else 0.0
    rows.sort(key=lambda r: -r["value"])
    return rows, realized


def _summary(p: Portfolio, detail: bool = False) -> dict:
    txns = _txns(p)
    rows, realized = _positions(txns)
    value = sum(r["value"] for r in rows)
    cost = sum(r["cost"] for r in rows)
    day = sum(r["day_change"] for r in rows)
    cls = classify(rows)
    out = {
        "id": p.id,
        "name": p.name,
        "description": p.description,
        "template_id": p.template_id,
        "created_at": p.created_at.isoformat(),
        "positions_count": len(rows),
        "value": round(value, 2),
        "cost": round(cost, 2),
        "unrealized_pnl": round(value - cost, 2),
        "unrealized_pnl_pct": round((value / cost - 1) * 100, 2) if cost else None,
        "realized_pnl": round(realized, 2),
        "day_change": round(day, 2),
        "day_change_pct": round(day / (value - day) * 100, 2) if value - day else None,
        "classification": {k: cls[k] for k in ("primary", "label", "secondary", "risk_level")},
        "symbols": [r["symbol"] for r in rows],
    }
    if detail:
        divs = dividends_received(txns, {s: market_data.dividends(s) for s in {t.symbol for t in txns}})
        out.update(
            {
                "classification": cls,
                "positions": [{k: v for k, v in r.items() if k not in ("fundamentals", "metrics")} | {
                    "beta": r["metrics"]["beta"], "dividend_yield": r["fundamentals"].get("dividend_yield"), "pe": r["fundamentals"].get("pe"),
                } for r in rows],
                "dividends": divs,
                "dividends_total": round(sum(d["amount"] for d in divs), 2),
                "transactions": [
                    {"id": t.id, "date": t.date.isoformat(), "symbol": t.symbol, "side": t.side, "shares": t.shares, "price": t.price, "fees": t.fees}
                    for t in sorted(p.transactions, key=lambda t: (t.date, t.id), reverse=True)
                ],
            }
        )
    return out


def _active_ids(db: Session, user: User) -> set[int]:
    """After a downgrade the oldest portfolios within the plan stay usable; the rest are kept but locked."""
    limit = limits_for(user)["max_portfolios"]
    ids = db.scalars(select(Portfolio.id).where(Portfolio.user_id == user.id).order_by(Portfolio.created_at, Portfolio.id)).all()
    return set(ids[:limit])


def _owned(db: Session, user: User, pid: int, active: bool = True) -> Portfolio:
    p = db.get(Portfolio, pid)
    if p is None or p.user_id != user.id:
        raise HTTPException(404, "Portfolio not found")
    if active and pid not in _active_ids(db, user):
        n = limits_for(user)["max_portfolios"]
        raise HTTPException(403, f"Your plan includes {n} portfolio{'s' if n != 1 else ''}. Upgrade to use this one, or delete another.")
    return p


def _check_limit(db: Session, user: User) -> None:
    limit = limits_for(user)["max_portfolios"]
    n = db.scalar(select(func.count()).select_from(Portfolio).where(Portfolio.user_id == user.id)) or 0
    if n >= limit:
        raise HTTPException(403, f"Your plan allows up to {limit} portfolio(s). Upgrade to create more.")


# ---------------------------------------------------------------- portfolios

class PortfolioIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=300)


@router.get("/portfolios")
def list_portfolios(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Portfolio).where(Portfolio.user_id == user.id).order_by(Portfolio.created_at, Portfolio.id)).all()
    active = _active_ids(db, user)
    return [_summary(p) if p.id in active else {"id": p.id, "name": p.name, "description": p.description, "locked": True,
                                                  "value": 0, "symbols": [], "positions_count": 0} for p in rows]


@router.get("/portfolios/positions")
def positions_for(symbol: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Where you hold a symbol: each active portfolio's position (for selling from the chart)."""
    sym = symbol.upper().strip()
    out = []
    for p in db.scalars(select(Portfolio).where(Portfolio.user_id == user.id, Portfolio.id.in_(_active_ids(db, user)))).all():
        h = holdings(_txns(p)).get(sym)
        if h and h["shares"] > 1e-9:
            try:
                price = market_data.quote(sym)["price"]
            except Exception:
                price = None
            out.append({"portfolio_id": p.id, "portfolio": p.name, "shares": round(h["shares"], 6), "avg_cost": round(h["avg_cost"], 4),
                        "price": price, "pnl": round((price - h["avg_cost"]) * h["shares"], 2) if price else None})
    return out


@router.post("/portfolios")
def create_portfolio(body: PortfolioIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _check_limit(db, user)
    p = Portfolio(user_id=user.id, name=body.name.strip(), description=body.description.strip())
    db.add(p)
    db.commit()
    return _summary(p, detail=True)


@router.get("/portfolios/{pid}")
def get_portfolio(pid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return _summary(_owned(db, user, pid), detail=True)


@router.patch("/portfolios/{pid}")
def update_portfolio(pid: int, body: PortfolioIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = _owned(db, user, pid)
    p.name, p.description = body.name.strip(), body.description.strip()
    db.commit()
    return _summary(p, detail=True)


@router.delete("/portfolios/{pid}", status_code=204)
def delete_portfolio(pid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.delete(_owned(db, user, pid, active=False))  # locked portfolios can still be deleted
    db.commit()


# ---------------------------------------------------------------- transactions

class TxnIn(BaseModel):
    symbol: str = Field(min_length=1, max_length=16, pattern=r"^[A-Za-z0-9.\-^=]+$")
    side: str = Field(pattern=r"^(buy|sell)$")
    shares: float = Field(gt=0, le=1e9)
    price: float | None = Field(default=None, gt=0, le=1e7)
    date: date
    fees: float = Field(default=0.0, ge=0, le=1e6)


@router.post("/portfolios/{pid}/transactions")
def add_transaction(pid: int, body: TxnIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = _owned(db, user, pid)
    if body.date > date.today():
        raise HTTPException(400, "The transaction date cannot be in the future")
    symbol = body.symbol.upper()
    try:
        price = body.price or market_data.close_on(symbol, body.date)
    except Exception:
        raise HTTPException(404, f"No data found for {symbol}")
    if price is None:
        raise HTTPException(400, f"No price available for {symbol} on {body.date}")
    t = PortfolioTxn(date=body.date, symbol=symbol, side=body.side, shares=body.shares, price=round(price, 4), fees=body.fees)
    try:
        validate(_txns(p) + [Txn(t.date, t.symbol, t.side, t.shares, t.price, t.fees)])
    except LedgerError as e:
        raise HTTPException(400, str(e))
    p.transactions.append(t)
    db.commit()
    return _summary(p, detail=True)


@router.delete("/portfolios/{pid}/transactions/{tid}")
def delete_transaction(pid: int, tid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = _owned(db, user, pid)
    t = next((x for x in p.transactions if x.id == tid), None)
    if t is None:
        raise HTTPException(404, "Transaction not found")
    rest = [x for x in p.transactions if x.id != tid]
    try:
        validate([Txn(x.date, x.symbol, x.side, x.shares, x.price, x.fees) for x in rest])
    except LedgerError:
        raise HTTPException(400, "Deleting this buy would leave later sells without shares. Delete those sells first.")
    p.transactions.remove(t)
    db.commit()
    return _summary(p, detail=True)


# ---------------------------------------------------------------- performance

@router.get("/portfolios/{pid}/performance")
def performance(
    pid: int,
    period: str = Query("ALL", pattern=r"^(1D|1W|1M|3M|6M|YTD|1Y|ALL|CUSTOM)$"),
    start: date | None = None,
    end: date | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    p = _owned(db, user, pid)
    txns = _txns(p)
    empty = {"period": period, "series": [], "portfolio_return": None, "benchmark_return": None, "start_value": 0, "end_value": 0, "pnl": 0}
    if not txns:
        return empty
    closes = {s: market_data.history(s)["close"] for s in {t.symbol for t in txns}}
    vs = value_series(txns, closes)
    if vs.empty:
        return empty
    idx = twr_index(vs)
    if period == "CUSTOM":
        if not start:
            raise HTTPException(400, "A start date is required for a custom period")
        s_ts = pd.Timestamp(start)
        e_ts = pd.Timestamp(end) if end else idx.index[-1]
        if e_ts < s_ts:
            raise HTTPException(400, "The end date must be after the start date")
        before = idx.index[idx.index <= s_ts]
        s0 = before[-1] if len(before) else idx.index[0]
        window = idx[(idx.index >= s0) & (idx.index <= e_ts)]
    else:
        s0 = period_start(idx.index, period)
        window = idx[idx.index >= s0]
    if len(window) < 1:
        return empty
    bench = _bench_close()
    b = bench.reindex(window.index).ffill() if bench is not None else None
    series = []
    for ts, v in window.items():
        row = {"time": ts.strftime("%Y-%m-%d"), "portfolio": round((v / window.iloc[0] - 1) * 100, 3)}
        if b is not None and pd.notna(b.iloc[0]) and pd.notna(b.loc[ts]):
            row["benchmark"] = round((b.loc[ts] / b.iloc[0] - 1) * 100, 3)
        series.append(row)
    vwin = vs.loc[window.index]
    start_value, end_value = float(vwin["value"].iloc[0]), float(vwin["value"].iloc[-1])
    flows = float(vwin["flow"].iloc[1:].sum())
    return {
        "period": period,
        "start": window.index[0].strftime("%Y-%m-%d"),
        "end": window.index[-1].strftime("%Y-%m-%d"),
        "series": series,
        "portfolio_return": series[-1]["portfolio"],
        "benchmark_return": series[-1].get("benchmark"),
        "start_value": round(start_value, 2),
        "end_value": round(end_value, 2),
        "pnl": round(end_value - start_value - flows, 2),
    }


# ---------------------------------------------------------------- model portfolios

def _template_symbols(t: dict) -> list[str]:
    if t.get("dynamic") == "rs_leaders":
        from .sepa import cached_scan

        rows = sorted(cached_scan(), key=lambda r: -(r["rs_rating"] or 0))
        return [r["symbol"] for r in rows[:8]]
    return t["symbols"]


def _equal_weight_rows(symbols: list[str]) -> list[dict]:
    bench = _bench_close()
    rows = []
    for s in symbols:
        try:
            close = market_data.history(s)["close"]
        except Exception:
            continue
        f = market_data.fundamentals(s)
        rows.append({"symbol": s, "value": 1.0, "sector": f.get("sector") or "Other", "fundamentals": f, "metrics": stock_metrics(close, bench, f.get("beta"))})
    return rows


@router.get("/portfolio-templates")
def templates(user: User = Depends(current_user)):
    out = []
    for t in TEMPLATES:
        symbols = _template_symbols(t)
        cls = classify(_equal_weight_rows(symbols))
        out.append(
            {
                **{k: v for k, v in t.items() if k != "dynamic"},
                "symbols": symbols,
                "detected": {"label": cls["label"], "risk_level": cls["risk_level"], "dividend_yield": cls.get("weighted", {}).get("dividend_yield")},
            }
        )
    return out


class FromTemplateIn(BaseModel):
    template_id: str
    amount: float = Field(gt=0, le=1e9)
    name: str | None = Field(default=None, max_length=80)


@router.post("/portfolios/from-template")
def from_template(body: FromTemplateIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    t = next((x for x in TEMPLATES if x["id"] == body.template_id), None)
    if t is None:
        raise HTTPException(404, "Template not found")
    _check_limit(db, user)
    symbols = _template_symbols(t)
    if not symbols:
        raise HTTPException(400, "This model has no symbols right now")
    today = date.today()
    per = body.amount / len(symbols)
    p = Portfolio(user_id=user.id, name=(body.name or t["name"]).strip(), description=t["description"], template_id=t["id"])
    for s in symbols:
        price = market_data.close_on(s, today)
        if price:
            p.transactions.append(PortfolioTxn(date=today, symbol=s, side="buy", shares=round(per / price, 4), price=round(price, 4), fees=0.0))
    db.add(p)
    db.commit()
    return _summary(p, detail=True)


@router.get("/market/price/{symbol}")
def price_on(symbol: str, on: date | None = None, user: User = Depends(current_user)):
    try:
        px = market_data.close_on(symbol.upper(), on or date.today())
    except Exception:
        raise HTTPException(404, f"No data found for {symbol.upper()}")
    return {"symbol": symbol.upper(), "date": (on or date.today()).isoformat(), "price": round(px, 2) if px else None}


__all__ = ["router", "PERIODS"]


class ImportIn(BaseModel):
    csv: str = Field(default="", max_length=5_000_000)
    pdf_base64: str = Field(default="", max_length=8_000_000)  # a broker statement as PDF
    dry_run: bool = True


@router.post("/portfolios/{pid}/import")
def import_csv(pid: int, body: ImportIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Import a broker's trade export (CSV or PDF statement). dry_run=true returns a preview; false saves the transactions."""
    import base64

    from engine.broker_csv import parse, parse_pdf

    p = db.get(Portfolio, pid)
    if p is None or p.user_id != user.id:
        raise HTTPException(404, "Portfolio not found")
    if body.pdf_base64:
        try:
            res = parse_pdf(base64.b64decode(body.pdf_base64.split(",")[-1]))
        except ValueError:
            raise HTTPException(400, "The PDF file could not be decoded")
    else:
        res = parse(body.csv)
    existing = [Txn(date=pd.Timestamp(x.date).date(), symbol=x.symbol, side=x.side, shares=x.shares, price=x.price, fees=x.fees)
                for x in db.scalars(select(PortfolioTxn).where(PortfolioTxn.portfolio_id == pid)).all()]
    new = [Txn(date=pd.Timestamp(x["date"]).date(), symbol=x["symbol"], side=x["side"], shares=x["shares"], price=x["price"], fees=x["fees"])
           for x in res["txns"]]
    error = None
    try:
        validate(existing + new)
    except ValueError as e:
        error = str(e)
    if body.dry_run or error:
        return {**res, "error": error, "saved": 0}
    for x in res["txns"]:
        db.add(PortfolioTxn(portfolio_id=pid, date=pd.Timestamp(x["date"]).date(), symbol=x["symbol"], side=x["side"],
                            shares=x["shares"], price=x["price"], fees=x["fees"]))
    db.commit()
    return {**res, "error": None, "saved": len(res["txns"])}


class ImportPreviewIn(BaseModel):
    filename: str = Field(default="import.csv", max_length=200)
    content_base64: str = Field(max_length=14_000_000)  # up to ~10 MB files
    mapping: dict[str, int] | None = None  # manual column mapping: field -> column index
    header_row: int | None = None
    table: int = 0


class ImportApplyIn(BaseModel):
    kind: Literal["trades", "positions"]
    as_of: str
    rows: list[dict] = Field(max_length=20_000)
    close_missing: bool = True


def _own(db: Session, user: User, pid: int) -> Portfolio:
    return _owned(db, user, pid)


@router.post("/portfolios/{pid}/import/preview")
def import_preview(pid: int, body: ImportPreviewIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Any broker file (CSV, Excel, PDF): trades or a statement of positions, with symbols resolved and what would change."""
    import base64

    from .. import import_service

    _own(db, user, pid)
    try:
        data = base64.b64decode(body.content_base64.split(",")[-1])
    except ValueError:
        raise HTTPException(400, "The file could not be decoded")
    try:
        return import_service.preview(db, pid, body.filename, data, body.mapping, body.header_row, body.table)
    except HTTPException:
        raise
    except Exception as e:
        import logging

        logging.getLogger("sepa.import").exception("Import preview failed")
        raise HTTPException(400, f"Could not read this file ({type(e).__name__}). Try another export format or map the columns manually.")


@router.post("/portfolios/{pid}/import/apply")
def import_apply(pid: int, body: ImportApplyIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Save the import: new trades only (no duplicates), or reconcile the portfolio to the statement of positions."""
    from .. import import_service

    _own(db, user, pid)
    try:
        return import_service.apply(db, pid, body.kind, body.as_of, body.rows, body.close_missing)
    except LedgerError as e:
        raise HTTPException(400, str(e))
    except HTTPException:
        raise
    except Exception as e:
        import logging

        logging.getLogger("sepa.import").exception("Import apply failed")
        raise HTTPException(400, f"Could not save the import ({type(e).__name__}).")



class SellNowIn(BaseModel):
    symbol: str = Field(min_length=1, max_length=16)
    shares: float | None = Field(default=None, gt=0)  # missing = the whole position


@router.post("/portfolios/{pid}/sell-now")
def sell_now(pid: int, body: SellNowIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Sell at the market: the latest price, on the latest trading day."""
    p = _owned(db, user, pid)
    sym = body.symbol.upper().strip()
    held = holdings(_txns(p)).get(sym, {"shares": 0.0})["shares"]
    if held <= 1e-9:
        raise HTTPException(400, f"You don't hold {sym} in this portfolio.")
    qty = body.shares or held
    if qty > held + 1e-9:
        raise HTTPException(400, f"You hold only {held:g} {sym}.")
    price, day = _market_price(sym)
    p.transactions.append(PortfolioTxn(date=day, symbol=sym, side="sell", shares=min(qty, held), price=round(price, 4), fees=0.0))
    db.commit()
    return _summary(p, detail=True)


def _market_price(sym: str) -> tuple[float, date]:
    """The latest price (live quote when there is one, else the last close), dated the latest trading day."""
    try:
        df = market_data.history(sym)
    except Exception:
        raise HTTPException(404, f"No data found for {sym}")
    price, day = float(df["close"].iloc[-1]), df.index[-1].date()
    try:
        q = market_data.quote(sym).get("price")
        if q and q > 0:
            price = float(q)
    except Exception:
        pass
    return price, min(day, date.today())


class BuyNowIn(BaseModel):
    symbol: str = Field(min_length=1, max_length=16, pattern=r"^[A-Za-z0-9.\-^=]+$")
    shares: float = Field(gt=0, le=1e9)


@router.post("/portfolios/{pid}/buy-now")
def buy_now(pid: int, body: BuyNowIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Buy at the market (from the chart): the latest price, on the latest trading day."""
    p = _owned(db, user, pid)
    sym = body.symbol.upper().strip()
    price, day = _market_price(sym)
    p.transactions.append(PortfolioTxn(date=day, symbol=sym, side="buy", shares=body.shares, price=round(price, 4), fees=0.0))
    db.commit()
    return _summary(p, detail=True)
