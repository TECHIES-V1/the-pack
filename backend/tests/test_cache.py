"""TTLCache: caching, single-flight collapse, empty-skip, and expiry."""

from __future__ import annotations

import asyncio

from app.tools.cache import TTLCache


async def test_caches_and_serves_hits():
    cache: TTLCache[int] = TTLCache(ttl_s=60)
    calls = 0

    async def factory():
        nonlocal calls
        calls += 1
        return 42

    assert await cache.get_or_compute("k", factory) == 42
    assert await cache.get_or_compute("k", factory) == 42
    assert calls == 1  # second call served from cache


async def test_single_flight_collapses_concurrent_calls():
    cache: TTLCache[int] = TTLCache(ttl_s=60)
    calls = 0

    async def slow():
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.05)
        return 7

    results = await asyncio.gather(*(cache.get_or_compute("k", slow) for _ in range(5)))
    assert results == [7, 7, 7, 7, 7]
    assert calls == 1  # five concurrent callers, one computation


async def test_empty_results_are_not_cached():
    cache: TTLCache[list] = TTLCache(ttl_s=60)
    calls = 0

    async def empty():
        nonlocal calls
        calls += 1
        return []

    await cache.get_or_compute("k", empty)
    await cache.get_or_compute("k", empty)
    assert calls == 2  # falsy result skipped the cache, so it recomputed


async def test_expiry_recomputes():
    cache: TTLCache[int] = TTLCache(ttl_s=0.05)
    calls = 0

    async def factory():
        nonlocal calls
        calls += 1
        return calls

    assert await cache.get_or_compute("k", factory) == 1
    await asyncio.sleep(0.08)
    assert await cache.get_or_compute("k", factory) == 2  # expired → recomputed
