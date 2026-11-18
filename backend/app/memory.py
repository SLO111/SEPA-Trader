"""How much memory the server has and uses (Render's free instance: 512 MB), so heavy jobs can size themselves."""

from __future__ import annotations

from pathlib import Path

DEFAULT_LIMIT_MB = 512


def limit_mb() -> int:
    """Memory the server may use: MEMORY_LIMIT_MB if set, else the container's limit (cgroup v2 / v1), else the machine's
    total memory (a Docker container on your own server has no limit), else 512 MB."""
    import os

    env = os.environ.get("MEMORY_LIMIT_MB", "").strip()
    if env.isdigit() and int(env) >= 64:
        return int(env)
    total = _total_mb()
    for path in ("/sys/fs/cgroup/memory.max", "/sys/fs/cgroup/memory/memory.limit_in_bytes"):
        try:
            raw = Path(path).read_text().strip()
        except OSError:
            continue
        if raw.isdigit():
            mb = int(raw) // (1024 * 1024)
            if 64 <= mb <= (total or 64 * 1024):  # "no limit" shows up as a huge number
                return mb
    if os.environ.get("RENDER"):  # Render sets RENDER=true; its free instance has 512 MB whatever the host machine has
        return DEFAULT_LIMIT_MB
    return total or DEFAULT_LIMIT_MB


def _total_mb() -> int | None:
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal:"):
                return int(line.split()[1]) // 1024
    except OSError:
        pass
    return None


def rss_mb() -> int:
    """Memory this process uses now (resident set size)."""
    try:
        for line in Path("/proc/self/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) // 1024
    except OSError:
        pass
    import resource

    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024


def free_mb() -> int:
    return limit_mb() - rss_mb()


_breakdown_cache: tuple[float, dict] | None = None


def _approx_mb(obj) -> float:
    """Rough size in MB: exact for DataFrames, the pickled size for other data (Python objects take ~2-3x that)."""
    import pickle

    import pandas as pd

    if isinstance(obj, pd.DataFrame):
        return float(obj.memory_usage(deep=True).sum()) / 1e6
    if isinstance(obj, dict) and obj and all(isinstance(v, pd.DataFrame) for v in list(obj.values())[:5]):
        return sum(_approx_mb(v) for v in obj.values() if isinstance(v, pd.DataFrame))
    try:
        return len(pickle.dumps(obj, protocol=5)) * 2.5 / 1e6
    except Exception:
        return 0.0


def breakdown() -> dict:
    """What takes the memory, roughly (MB), refreshed at most once a minute."""
    import time

    global _breakdown_cache
    if _breakdown_cache and time.monotonic() - _breakdown_cache[0] < 60:
        return _breakdown_cache[1]
    from . import market_data
    from .data_store import get_store

    out: dict[str, float] = {}
    store = get_store()
    if store is not None:
        out["stock prices"] = _approx_mb(store.prices)
        out["fundamentals / earnings / ATH"] = sum(_approx_mb(v) for v in store.slow.values())
        out["symbol directory (search)"] = _approx_mb(store.directory)
    try:
        out["shared screens cache"] = sum(_approx_mb(v) for _, v in list(market_data._fast_cache.values()))
    except Exception:
        pass
    try:
        from .routers import sepa

        out["Move Detector scan"] = sum(_approx_mb(rows) for _, rows in list(sepa._scan_cache.values()))
    except Exception:
        pass
    data = sum(out.values())
    out["Python, libraries and the rest"] = max(0.0, rss_mb() - data)
    result = {k: round(v) for k, v in sorted(out.items(), key=lambda kv: -kv[1])}
    _breakdown_cache = (time.monotonic(), result)
    return result
