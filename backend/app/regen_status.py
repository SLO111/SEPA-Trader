"""Progress of the admin "Regenerate signals" job, kept in memory and in the app_settings table, so the Admin page can
show the current step and notice when a server restart interrupted the job."""

from __future__ import annotations

import threading
from datetime import datetime, timezone

KEY = "regen_status"
_lock = threading.Lock()
_state: dict = {"running": False}
_alive = threading.Event()  # set while a job runs in this process


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _persist() -> None:
    try:
        from . import app_settings
        from .db import SessionLocal

        with SessionLocal() as db:
            app_settings.put(db, KEY, dict(_state))
    except Exception:
        pass  # progress display only: never fail the job because of it


def start() -> None:
    with _lock:
        _state.clear()
        _state.update(running=True, started_at=_now(), stage="Starting", stage_at=_now(), finished_at=None,
                      generated=None, scanned=None, error=None, stages=[])
        _alive.set()
    _persist()


def stage(name: str) -> None:
    """Called by the job as it moves on (no-op when no job runs)."""
    if not _alive.is_set():
        return
    with _lock:
        _state.update(stage=name, stage_at=_now())
        _state.setdefault("stages", []).append({"stage": name, "at": _state["stage_at"]})
    _persist()


def finish(generated: int | None = None, scanned: int | None = None, error: str | None = None) -> None:
    with _lock:
        _state.update(running=False, finished_at=_now(), stage="Failed" if error else "Done", generated=generated,
                      scanned=scanned, error=error)
        _alive.clear()
    _persist()


def running_here() -> bool:
    return _alive.is_set()


def status() -> dict:
    """The job's status. A job marked running in the database but not running in this process was interrupted by a
    restart (often low memory on the free server, or a deploy)."""
    if _alive.is_set():
        with _lock:
            return {**_state, "interrupted": False}
    saved = None
    try:
        from . import app_settings
        from .db import SessionLocal

        with SessionLocal() as db:
            saved = app_settings.get(db, KEY)
    except Exception:
        saved = None
    if not saved:
        return {"running": False, "interrupted": False}
    if saved.get("running"):
        return {**saved, "running": False, "interrupted": True}
    return {**saved, "interrupted": False}
