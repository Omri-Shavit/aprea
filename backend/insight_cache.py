"""Process-local cache for the /api/insights/* endpoints.

Why this exists
---------------
The Insights tab requests six aggregates at once, and each one is computed over
every row in scope - ~50k rows for the unscoped matrix. Without a cache the six
requests each materialise their own copy of those rows concurrently, which
measured at 574 MB peak RSS and 30.5 s wall time on the full dataset: enough to
be killed by a 512 MB container and slow enough to look broken.

Two layers fix that, both keyed on a version that changes whenever the data
changes:

``rows``
    A single shared snapshot of the rows for a scope, held briefly (``ROWS_TTL``).
    The six concurrent cold requests then share one load instead of six.

``results``
    The computed aggregate itself. Once warm, an insight request touches no rows
    at all, so the steady-state cost is a dict lookup.

A single lock serialises cold computation. That is deliberate: it bounds peak
memory to one row snapshot, which matters more than concurrency here because the
work is CPU-bound Python that the GIL would serialise regardless.

Consistency
-----------
The API is read-only: nothing mutates the database while the process is running,
because rows only ever arrive through ``ingest.py`` and a redeploy. A cached
aggregate therefore cannot go stale mid-process, and ``RESULT_TTL`` is a
belt-and-braces bound rather than something the design depends on.

``bump_version()`` remains the invalidation hook. If write endpoints are ever
reintroduced behind authentication, every one of them must call it, and the
per-process counter then stops being sufficient the moment the service runs more
than one instance - a write served by instance A would not invalidate instance
B. That case needs a shared marker (a row-version table, or Redis), not a
shorter TTL.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Callable, Dict, Hashable, Optional, Tuple

# Seconds a shared row snapshot is retained. Long enough to cover one tab's
# burst of six requests, short enough that ~80 MB is not held indefinitely.
ROWS_TTL = 60.0

# Backstop for cross-instance staleness (see module docstring). Within a single
# instance, explicit invalidation makes this irrelevant.
RESULT_TTL = 300.0

# Bounds memory if many distinct scopes are queried. The landscape aggregate can
# be ~1.6 MB, so this caps the cache at a few tens of MB.
MAX_RESULTS = 64

_lock = threading.RLock()
_version = 0
_results: Dict[Hashable, Tuple[int, float, Any]] = {}
_rows: Optional[Tuple[Hashable, int, float, Any]] = None


def bump_version() -> int:
    """Invalidate everything. Call from every path that writes to the DB."""
    global _version, _rows
    with _lock:
        _version += 1
        _results.clear()
        _rows = None
        return _version


def stats() -> dict:
    """Cache state, exposed on /healthz for debugging a slow deployment."""
    with _lock:
        return {
            "version": _version,
            "cached_results": len(_results),
            "rows_snapshot": None if _rows is None else _rows[0],
        }


def _get_rows(scope_key: Hashable, loader: Callable[[], Any]) -> Any:
    """Return the row list for a scope, reusing a recent snapshot if present."""
    global _rows
    now = time.monotonic()
    if _rows is not None:
        key, version, created, rows = _rows
        if key == scope_key and version == _version and now - created < ROWS_TTL:
            return rows
    rows = loader()
    _rows = (scope_key, _version, now, rows)
    return rows


def cached_insight(
    name: str,
    scope_key: Hashable,
    params_key: Hashable,
    loader: Callable[[], Any],
    compute: Callable[[Any], Any],
) -> Any:
    """Return ``compute(loader())`` for this scope, computing at most once.

    Args:
        name: insight function name, so two insights over the same scope do not
            collide.
        scope_key: hashable form of the scope filters; also keys the row snapshot.
        params_key: any non-scope arguments that change the output (e.g. the
            landscape's ``by``).
        loader: fetches the rows. Called at most once per scope per version.
        compute: turns rows into the response payload.
    """
    key = (name, scope_key, params_key)
    now = time.monotonic()

    with _lock:
        hit = _results.get(key)
        if hit is not None:
            version, created, value = hit
            if version == _version and now - created < RESULT_TTL:
                return value
            del _results[key]

        value = compute(_get_rows(scope_key, loader))

        if len(_results) >= MAX_RESULTS:
            # Rare, and every entry is recomputable; clearing is simpler and
            # cheaper to reason about than tracking an eviction order.
            _results.clear()
        _results[key] = (_version, time.monotonic(), value)
        return value
