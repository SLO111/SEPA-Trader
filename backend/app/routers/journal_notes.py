"""Trade journal notes (setup, emotion, lesson, screenshot) attached to TradeGrader trades, plus CSV exports."""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import TradeNote, User
from ..plans import limits_for
from ..security import current_user

router = APIRouter(prefix="/api", tags=["journal"])

SETUPS = ["Breakout", "VCP pivot", "Pullback to MA", "Pocket pivot", "Gap up", "Base breakout", "Earnings play", "Short: breakdown", "Other"]
EMOTIONS = ["Calm / to plan", "Confident", "FOMO", "Fear", "Greedy", "Revenge", "Impatient", "Bored"]
MAX_IMAGE = 400_000  # characters of base64 (~300 KB)


def note_out(n: TradeNote, image: bool = True) -> dict:
    return {"ref": n.ref, "setup": n.setup, "emotion": n.emotion, "notes": n.notes, "has_image": bool(n.image),
            **({"image": n.image} if image else {}), "updated_at": n.updated_at.isoformat()}


@router.get("/notes/options")
def note_options(user: User = Depends(current_user)):
    return {"setups": SETUPS, "emotions": EMOTIONS}


@router.get("/notes")
def list_notes(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """All your notes, without images (load one with GET /notes/{ref})."""
    return [note_out(n, image=False) for n in db.scalars(select(TradeNote).where(TradeNote.user_id == user.id)).all()]


@router.get("/notes/{ref}")
def get_note(ref: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    n = db.scalar(select(TradeNote).where(TradeNote.user_id == user.id, TradeNote.ref == ref))
    if n is None:
        raise HTTPException(404, "No note for this trade yet")
    return note_out(n)


class NoteIn(BaseModel):
    setup: str | None = Field(default=None, max_length=40)
    emotion: str | None = Field(default=None, max_length=40)
    notes: str | None = Field(default=None, max_length=5000)
    image: str | None = None  # data:image/...;base64; "" removes it


@router.put("/notes/{ref}")
def save_note(ref: str, body: NoteIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if len(ref) > 40 or not (ref.startswith("paper:") or ref.startswith("pf:")):
        raise HTTPException(400, "Unknown trade reference")
    if body.image and (not body.image.startswith("data:image/") or len(body.image) > MAX_IMAGE):
        raise HTTPException(400, "The screenshot must be an image under about 300 KB")
    n = db.scalar(select(TradeNote).where(TradeNote.user_id == user.id, TradeNote.ref == ref))
    if n is None:
        n = TradeNote(user_id=user.id, ref=ref)
        db.add(n)
    for k in ("setup", "emotion", "notes"):
        v = getattr(body, k)
        if v is not None:
            setattr(n, k, v.strip())
    if body.image is not None:
        n.image = body.image or None
    n.updated_at = datetime.now(timezone.utc)
    db.commit()
    return note_out(n)


@router.delete("/notes/{ref}", status_code=204)
def delete_note(ref: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    n = db.scalar(select(TradeNote).where(TradeNote.user_id == user.id, TradeNote.ref == ref))
    if n:
        db.delete(n)
        db.commit()


# ------------------------------------------------------------------ CSV export (Premium)

def csv_response(rows: list[dict], filename: str) -> Response:
    buf = io.StringIO()
    cols: list[str] = []
    for r in rows:
        for k in r:
            if k not in cols and not isinstance(r[k], (dict, list)):
                cols.append(k)
    w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow({k: r.get(k) for k in cols})
    return Response(buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/export/{kind}")
def export(kind: str, portfolio_id: int | None = None, source: str = "all", preset: str | None = None, format: str = "csv",
           user: User = Depends(current_user), db: Session = Depends(get_db)):
    """CSV export: transactions | holdings (portfolio_id), paper-trades | grader (source), screener (preset)."""
    if not limits_for(user)["csv_export"]:
        raise HTTPException(403, "CSV export is part of Premium.")
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if kind in ("transactions", "holdings"):
        from .portfolios import _owned, _summary

        if portfolio_id is None:
            raise HTTPException(400, "portfolio_id is required")
        p = _owned(db, user, portfolio_id)
        d = _summary(p, detail=True)
        rows = d["transactions"] if kind == "transactions" else d["positions"]
        if format in ("xlsx", "pdf"):
            from engine import branded_export as be

            if kind == "transactions":
                rows = [{**r, "amount": round((-1 if r["side"] == "buy" else 1) * r["shares"] * r["price"] - (r.get("fees") or 0), 2),
                         "side": r["side"].capitalize()} for r in sorted(rows, key=lambda r: r["date"])]
                cols, totals = be.TXN_COLUMNS, {"symbol": f"{len(rows)} transactions", "fees": round(sum(r.get("fees") or 0 for r in rows), 2)}
                title = f"Transactions · {p.name}"
            else:
                cols = be.HOLDING_COLUMNS
                totals = {"value": d["value"], "pnl": d["unrealized_pnl"], "pnl_pct": d["unrealized_pnl_pct"], "weight": 100.0}
                title = f"Holdings · {p.name}"
            sub = f"{len(rows)} rows · portfolio value ${d['value']:,.2f}"
            fn = f"Vnicorn-{p.name}-{kind}-{day}".replace(" ", "_")
            if format == "xlsx":
                return Response(be.to_xlsx(title, sub, cols, rows, totals), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                headers={"Content-Disposition": f'attachment; filename="{fn}.xlsx"'})
            return Response(be.to_pdf(title, sub, cols, rows, totals), media_type="application/pdf",
                            headers={"Content-Disposition": f'attachment; filename="{fn}.pdf"'})
        return csv_response(rows, f"{p.name}-{kind}-{day}.csv")
    if kind == "paper-trades":
        from .ideas import paper_trades

        src = source if source in ("all", "ideas", "md", "chart") else "all"
        return csv_response(paper_trades(source=src, user=user, db=db)["trades"], f"tracked-trades-{day}.csv")
    if kind == "grader":
        from .ideas import _graded

        return csv_response(_graded(user, db, source, portfolio_id), f"tradegrader-{day}.csv")
    if kind == "screener":
        from .markets import screener

        rows = screener(preset=preset, sector=None, min_cap_b=None, max_pe=None, min_yield=None, min_rs=None, min_growth=None,
                        template_only=False, above_ma50=False, user=user)["results"]
        return csv_response(rows, f"screener-{day}.csv")
    raise HTTPException(400, "Unknown export")
