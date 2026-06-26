"""The research retrieval layer behind the Scout's web_search/web_fetch.

A `SearchProvider` turns a query into ranked hits and a url into readable text. Two shapes ship:

* `CannedProvider` — DETERMINISTIC synthetic hits, no network, so the offline hunt stays
  reproducible with no keys (and tests stay hermetic).
* `MultiProvider` — fans every query out to ALL configured upstreams (web search, news, academic,
  community, knowledge graph — see `app/tools/providers/`), merges + dedupes the hits, and walks a
  reader chain (Jina → Firecrawl → Tavily → Apify) for deep page reads. Each upstream is failure-
  isolated: a timeout or rate-limit on one returns nothing and the rest still answer.

`make_search_provider()` builds the MultiProvider from whichever keys are present; if NO real key is
configured it returns Canned, so the engine still runs end to end offline (Doc 04 §07).
"""

from __future__ import annotations

import asyncio
import time
from typing import Protocol

from app.config import settings
from app.tools.providers.academic import CoreSearch, OpenAlexSearch
from app.tools.providers.base import Reader, SearchHit, SearchResults, SubProvider
from app.tools.providers.community import GitHubSearch, HackerNewsSearch
from app.tools.providers.kg import DBpediaSearch, GoogleKgSearch, WikidataSearch
from app.tools.providers.news import GNewsSearch, NewsApiSearch, NewsDataSearch
from app.tools.providers.readers import (
    ApifyReader,
    FirecrawlReader,
    JinaReader,
    TavilyExtractReader,
)
from app.tools.providers.web import ExaSearch, SerpApiSearch, TavilySearch, YouSearch

__all__ = [
    "SearchHit",
    "SearchResults",
    "SearchProvider",
    "CannedProvider",
    "MultiProvider",
    "make_search_provider",
]


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
                provider="canned",
            )
            for i in range(min(3, max(1, max_results)))
        ]
        return SearchResults(query=query, hits=hits, latency_ms=2100)

    async def fetch(self, url: str) -> str:
        return f"[offline] readable text extracted from {url}."


# A fan-out returns within this budget: take what the fast providers gave, cancel the stragglers — so
# one slow/hung upstream can't make every search wait out its full timeout.
_SEARCH_BUDGET_S = 7.0

# Cap concurrent calls to the SAME upstream across parallel scouts — light rate-limit politeness.
_PROVIDER_SEM: dict[str, asyncio.Semaphore] = {}


def _sem(name: str) -> asyncio.Semaphore:
    return _PROVIDER_SEM.setdefault(name, asyncio.Semaphore(2))


class MultiProvider:
    """Fan a query out to every upstream; merge, dedupe, rank. Deep-read via the reader chain."""

    name = "multi"

    def __init__(self, subs: list[SubProvider], readers: list[Reader]) -> None:
        self._subs = subs
        self._readers = readers

    async def _guarded(self, sub: SubProvider, query: str, per: int) -> list[SearchHit]:
        async with _sem(sub.name):
            return await sub.search(query, max_results=per)

    async def search(self, query: str, *, max_results: int = 8) -> SearchResults:
        start = time.monotonic()
        per = max(3, max_results // 2)
        tasks = [asyncio.create_task(self._guarded(s, query, per)) for s in self._subs]
        # Return on the budget with whatever finished; cancel the stragglers (no waiting on the slowest).
        done, pending = await asyncio.wait(tasks, timeout=_SEARCH_BUDGET_S)
        for t in pending:
            t.cancel()
        best: dict[str, SearchHit] = {}
        for t in done:
            try:
                r = t.result()
            except Exception:  # noqa: BLE001 — an upstream errored; already isolated, skip it
                continue
            for h in r:
                if not h.url:
                    continue
                cur = best.get(h.url)
                if cur is None or h.score > cur.score:
                    best[h.url] = h
        merged = sorted(best.values(), key=lambda h: h.score, reverse=True)[:max_results]
        return SearchResults(
            query=query, hits=merged, latency_ms=int((time.monotonic() - start) * 1000)
        )

    async def fetch(self, url: str) -> str:
        # Priority chain (Jina → Firecrawl → Tavily → Apify): first reader to return text wins. Each
        # reader carries its own timeout, so the chain is bounded even if an early one is slow.
        for reader in self._readers:
            text = await reader.read(url)
            if text:
                return text
        return ""


def make_search_provider() -> SearchProvider:
    """Assemble the enabled upstreams from config. Keyless providers always run, but only if at
    least one real key is configured — otherwise fall back to Canned (keeps offline deterministic).
    """
    s = settings
    keyed = [
        s.search_api_key,
        s.exa_api_key,
        s.serpapi_api_key,
        s.youcom_api_key,
        s.newsapi_key,
        s.gnews_api_key,
        s.newsdata_api_key,
        s.core_api_key,
        s.github_token,
        s.google_kg_api_key,
        s.jina_api_key,
        s.firecrawl_api_key,
        s.apify_api_key,
    ]
    if not any(keyed):
        return CannedProvider()

    subs: list[SubProvider] = []
    if s.search_api_key:
        subs.append(TavilySearch(s.search_api_key))
    if s.exa_api_key:
        subs.append(ExaSearch(s.exa_api_key))
    if s.serpapi_api_key:
        subs.append(SerpApiSearch(s.serpapi_api_key))
    if s.youcom_api_key:
        subs.append(YouSearch(s.youcom_api_key))
    if s.newsapi_key:
        subs.append(NewsApiSearch(s.newsapi_key))
    if s.gnews_api_key:
        subs.append(GNewsSearch(s.gnews_api_key))
    if s.newsdata_api_key:
        subs.append(NewsDataSearch(s.newsdata_api_key))
    subs.append(OpenAlexSearch(s.openalex_mailto))  # keyless
    if s.core_api_key:
        subs.append(CoreSearch(s.core_api_key))
    if s.github_token:
        subs.append(GitHubSearch(s.github_token))
    subs.append(HackerNewsSearch())  # keyless
    subs.append(WikidataSearch())  # keyless
    if s.google_kg_api_key:
        subs.append(GoogleKgSearch(s.google_kg_api_key))
    subs.append(DBpediaSearch())  # keyless

    readers: list[Reader] = []
    if s.jina_api_key:
        readers.append(JinaReader(s.jina_api_key))
    if s.firecrawl_api_key:
        readers.append(FirecrawlReader(s.firecrawl_api_key))
    if s.search_api_key:
        readers.append(TavilyExtractReader(s.search_api_key))
    if s.apify_api_key:
        readers.append(ApifyReader(s.apify_api_key))

    return MultiProvider(subs, readers)


# Process-wide default (mirrors how pricing.py reads settings at import). Tests force Canned.
SEARCH_PROVIDER: SearchProvider = make_search_provider()
