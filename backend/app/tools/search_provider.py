"""Web search providers — the real retrieval behind the Scout's web_search/web_fetch.

A `SearchProvider` turns a query into ranked hits (title, url, snippet) and a url into
readable text. `TavilyProvider` calls Tavily's LLM-oriented search/extract API over httpx
(already a dependency — no new package). `CannedProvider` returns DETERMINISTIC synthetic
hits so the offline hunt stays reproducible with no key.

The active provider is chosen by config: a real `search_api_key` selects the configured
vendor; an empty key falls back to Canned. Swapping the live vendor is a body change here and
nothing else — the tool contract (`tools/base.py`) and the Supervisor's gate-and-emit wrapper
are unchanged either way.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Protocol

import httpx

from app.config import settings


@dataclass
class SearchHit:
    title: str
    url: str
    snippet: str
    score: float = 0.0

    def as_dict(self) -> dict:
        return {"title": self.title, "url": self.url, "snippet": self.snippet, "score": self.score}


@dataclass
class SearchResults:
    query: str
    hits: list[SearchHit] = field(default_factory=list)
    latency_ms: int = 0

    def as_dict(self) -> dict:
        return {"query": self.query, "hits": [h.as_dict() for h in self.hits]}


class SearchProvider(Protocol):
    name: str

    async def search(self, query: str, *, max_results: int = 5) -> SearchResults: ...

    async def fetch(self, url: str) -> str: ...


def _slug(text: str, limit: int = 48) -> str:
    out = "".join(c if c.isalnum() else "-" for c in text.lower())
    return out.strip("-")[:limit] or "q"


class CannedProvider:
    """Deterministic offline provider — same query in, same hits out, no network, no clock."""

    name = "canned"

    async def search(self, query: str, *, max_results: int = 5) -> SearchResults:
        slug = _slug(query)
        hits = [
            SearchHit(
                title=f"{query} — source {i + 1}",
                url=f"https://example.com/{slug}/{i + 1}",
                snippet=f"A relevant passage about {query} (source {i + 1}).",
                score=round(1.0 - i * 0.1, 2),
            )
            for i in range(min(3, max(1, max_results)))
        ]
        return SearchResults(query=query, hits=hits, latency_ms=2100)

    async def fetch(self, url: str) -> str:
        return f"[offline] readable text extracted from {url}."


class TavilyProvider:
    """Tavily search + extract over httpx. The key is sent server-side only, never to the browser."""

    name = "tavily"
    _SEARCH_URL = "https://api.tavily.com/search"
    _EXTRACT_URL = "https://api.tavily.com/extract"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def search(self, query: str, *, max_results: int = 5) -> SearchResults:
        start = time.monotonic()
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                self._SEARCH_URL,
                json={
                    "api_key": self._api_key,
                    "query": query,
                    "max_results": max_results,
                    "search_depth": "advanced",
                },
            )
            resp.raise_for_status()
            data = resp.json()
        hits = [
            SearchHit(
                title=str(r.get("title", "")),
                url=str(r.get("url", "")),
                snippet=str(r.get("content", "")),
                score=float(r.get("score", 0.0) or 0.0),
            )
            for r in data.get("results", [])
        ]
        return SearchResults(
            query=query, hits=hits, latency_ms=int((time.monotonic() - start) * 1000)
        )

    async def fetch(self, url: str) -> str:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                self._EXTRACT_URL,
                json={"api_key": self._api_key, "urls": [url]},
            )
            resp.raise_for_status()
            data = resp.json()
        results = data.get("results", [])
        return str(results[0].get("raw_content", "")) if results else ""


def make_search_provider() -> SearchProvider:
    """Pick the provider from config: a real key selects the vendor; empty falls back to Canned."""
    if settings.search_api_key and settings.search_provider == "tavily":
        return TavilyProvider(settings.search_api_key)
    return CannedProvider()


# Process-wide default (mirrors how pricing.py reads settings at import). Tests can pass their own.
SEARCH_PROVIDER: SearchProvider = make_search_provider()
