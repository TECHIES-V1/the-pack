"""A tiny async TTL + single-flight cache.

In-process (the engine is single-worker today — swap for Redis when we go multi-worker). Two wins:
* **TTL cache** — an identical query/URL within the window skips the upstreams entirely.
* **Single-flight** — concurrent identical calls (e.g. two scouts issuing the same query) collapse
  onto ONE in-flight computation instead of each firing the full fan-out.

Empty results aren't cached (a transient all-providers-failed shouldn't stick for the whole TTL).
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable


class TTLCache[T]:
    def __init__(self, ttl_s: float, maxsize: int = 512) -> None:
        self._ttl = ttl_s
        self._max = maxsize
        self._store: dict[str, tuple[float, T]] = {}
        self._inflight: dict[str, asyncio.Future[T]] = {}

    def _fresh(self, key: str) -> T | None:
        item = self._store.get(key)
        if item and item[0] > time.monotonic():
            return item[1]
        if item:
            self._store.pop(key, None)
        return None

    async def get_or_compute(
        self,
        key: str,
        factory: Callable[[], Awaitable[T]],
        *,
        cache_if: Callable[[T], bool] = bool,
    ) -> T:
        hit = self._fresh(key)
        if hit is not None:
            return hit
        inflight = self._inflight.get(key)
        if inflight is not None:
            return await inflight  # single-flight: ride the in-progress computation

        fut: asyncio.Future[T] = asyncio.get_event_loop().create_future()
        self._inflight[key] = fut
        try:
            value = await factory()
            if cache_if(value):
                self._store[key] = (time.monotonic() + self._ttl, value)
                self._evict()
            fut.set_result(value)
            return value
        except Exception as exc:
            fut.set_exception(exc)
            raise
        finally:
            self._inflight.pop(key, None)

    def _evict(self) -> None:
        if len(self._store) <= self._max:
            return
        overflow = len(self._store) - self._max
        for k in sorted(self._store, key=lambda k: self._store[k][0])[:overflow]:
            self._store.pop(k, None)
