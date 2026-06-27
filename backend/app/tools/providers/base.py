"""Shared building blocks for the multi-source research providers.

A *sub-provider* turns a query into a list of `SearchHit`s for one upstream API (Tavily, Exa,
NewsAPI, OpenAlex, …). A *reader* turns a URL into readable text (Jina, Firecrawl, …). The
`MultiProvider` in `search_provider.py` fans a query out to every enabled sub-provider and walks
the reader chain for deep reads.

Every network call goes through `_get_json` / `_post_json` / `_get_text`, which swallow ALL errors
(timeouts, non-2xx, bad JSON) and return `None`. That isolation is the whole point: with ~16
upstreams on free tiers, one slow or rate-limited API must never sink the others.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

DEFAULT_TIMEOUT = 8.0


@dataclass
class SearchHit:
    title: str
    url: str
    snippet: str
    score: float = 0.0
    provider: str = ""  # which upstream brought it back (provenance / source diversity)

    def as_dict(self) -> dict:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "score": self.score,
            "provider": self.provider,
        }


@dataclass
class SearchResults:
    query: str
    hits: list[SearchHit] = field(default_factory=list)
    latency_ms: int = 0

    def as_dict(self) -> dict:
        return {"query": self.query, "hits": [h.as_dict() for h in self.hits]}


class SubProvider(Protocol):
    name: str

    async def search(self, query: str, *, max_results: int) -> list[SearchHit]: ...


class Reader(Protocol):
    name: str

    async def read(self, url: str) -> str | None: ...


async def _get_json(
    url: str,
    *,
    params: dict | None = None,
    headers: dict | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> Any | None:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            return resp.json()
    except Exception:  # noqa: BLE001 — one dead upstream must never sink the search
        return None


async def _post_json(
    url: str,
    *,
    json: dict | None = None,
    headers: dict | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> Any | None:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json=json, headers=headers)
            resp.raise_for_status()
            return resp.json()
    except Exception:  # noqa: BLE001
        return None


async def _get_text(url: str, *, headers: dict | None = None, timeout: float = 12.0) -> str | None:
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            return resp.text
    except Exception:  # noqa: BLE001
        return None


def _clip(text: str, limit: int = 400) -> str:
    text = " ".join((text or "").split())
    return text[:limit]
