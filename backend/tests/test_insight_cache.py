"""The insight cache must never serve results from superseded data.

A stale aggregate in a scientific tool is worse than a slow one, so these cover
invalidation and scope isolation rather than the speed-up itself.
"""

from __future__ import annotations

import insight_cache


def setup_function():
    insight_cache.bump_version()


def _counting_loader(rows, calls):
    def loader():
        calls.append(1)
        return rows
    return loader


def test_result_is_computed_once_per_scope():
    calls, computes = [], []

    def compute(rows):
        computes.append(1)
        return sum(rows)

    for _ in range(3):
        got = insight_cache.cached_insight(
            "s", ("t", "WEE1"), None, _counting_loader([1, 2, 3], calls), compute
        )
        assert got == 6
    assert len(computes) == 1, "compute ran more than once for one scope"
    assert len(calls) == 1, "rows were loaded more than once for one scope"


def test_two_insights_share_one_row_load():
    """The six-endpoints-at-once case: one load feeds every insight."""
    calls = []
    loader = _counting_loader([1, 2, 3], calls)

    a = insight_cache.cached_insight("sum", ("t", None), None, loader, sum)
    b = insight_cache.cached_insight("max", ("t", None), None, loader, max)

    assert (a, b) == (6, 3)
    assert len(calls) == 1, "each insight loaded its own copy of the rows"


def test_write_invalidates():
    data = [1, 2, 3]
    calls = []

    def loader():
        calls.append(1)
        return data

    first = insight_cache.cached_insight("s", (), None, loader, sum)
    assert first == 6

    data.append(4)
    # Without invalidation the cache would still answer 6.
    assert insight_cache.cached_insight("s", (), None, loader, sum) == 6

    insight_cache.bump_version()
    assert insight_cache.cached_insight("s", (), None, loader, sum) == 10
    assert len(calls) == 2, "invalidation did not force a fresh load"


def test_scopes_do_not_collide():
    wee1 = insight_cache.cached_insight(
        "s", ("target", "WEE1"), None, lambda: [1], sum)
    atr = insight_cache.cached_insight(
        "s", ("target", "ATR"), None, lambda: [99], sum)
    assert (wee1, atr) == (1, 99)


def test_params_key_separates_variants():
    """The landscape's by=compound and by=target must not share an entry.

    Both variants cover the same scope, so they share one row load; it is the
    computation that differs, which is what ``params_key`` has to separate.
    """
    calls = []
    loader = _counting_loader([1, 2, 3], calls)

    by_compound = insight_cache.cached_insight("landscape", (), "compound", loader, sum)
    by_target = insight_cache.cached_insight("landscape", (), "target", loader, max)

    assert (by_compound, by_target) == (6, 3), "one variant served the other's result"
    assert len(calls) == 1, "variants of one scope should share a row load"


def test_overflow_clears_rather_than_growing_without_bound():
    for i in range(insight_cache.MAX_RESULTS + 5):
        insight_cache.cached_insight("s", ("k", i), None, lambda: [i], sum)
    assert len(insight_cache._results) <= insight_cache.MAX_RESULTS

    # Still correct after the clear.
    assert insight_cache.cached_insight("s", ("k", 0), None, lambda: [0], sum) == 0
