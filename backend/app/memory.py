"""How much memory the server has and uses (Render's free instance: 512 MB), so heavy jobs can size themselves."""

from __future__ import annotations

from pathlib import Path

DEFAULT_LIMIT_MB = 512


def limit_mb() -> int:
    """The container's memory limit (cgroup v2 or v1), or 512 MB when it can't be read."""
    for path in ("/sys/fs/cgroup/memory.max", "/sys/fs/cgroup/memory/memory.limit_in_bytes"):
        try:
            raw = Path(path).read_text().strip()
        except OSError:
            continue
        if raw.isdigit():
            mb = int(raw) // (1024 * 1024)
            if 64 <= mb <= 64 * 1024:  # "no limit" shows up as a huge number
                return mb
    return DEFAULT_LIMIT_MB


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
