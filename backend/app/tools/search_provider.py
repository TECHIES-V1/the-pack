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
from app.tools.cache import TTLCache
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


# Fan-out timing — defaults mirror config, but read from `settings` at call time so a .env override
# (or a test monkeypatch of these module globals) takes effect. BUDGET is the hard ceiling; SOFT is
# the early return once we have ground, so a hung upstream can't make every search wait it out —
# which, under parallel scouts, pileup-throttles most of them to zero hits.
_SEARCH_BUDGET_S = settings.search_budget_s
_SEARCH_SOFT_S = settings.search_soft_s

# Cap concurrent calls to the SAME upstream across parallel scouts — light rate-limit politeness.
_PROVIDER_SEM: dict[str, asyncio.Semaphore] = {}


def _sem(name: str) -> asyncio.Semaphore:
    # Cap concurrent calls to the SAME upstream. Sized so a full pack (3-5 scouts, each searching +
    # broadening) doesn't serialize on one fast provider — that pileup, not the providers, is what
    # left most scouts with zero hits while one got them all. Tunable via settings.
    return _PROVIDER_SEM.setdefault(name, asyncio.Semaphore(settings.search_provider_concurrency))


class MultiProvider:
    """Fan a query out to every upstream; merge, dedupe, rank. Deep-read via the reader chain."""

    name = "multi"

    def __init__(self, subs: list[SubProvider], readers: list[Reader]) -> None:
        self._subs = subs
        self._readers = readers
        # Per-instance so the singleton caches across scouts + hunts in-process, while tests that
        # build their own MultiProvider stay isolated. Single-flight collapses concurrent dups.
        self._search_cache: TTLCache[list[SearchHit]] = TTLCache(settings.search_cache_ttl_s)
        self._fetch_cache: TTLCache[str] = TTLCache(settings.search_cache_ttl_s)

    async def _guarded(self, sub: SubProvider, query: str, per: int) -> list[SearchHit]:
        async with _sem(sub.name):
            return await sub.search(query, max_results=per)

    async def _fan_out(self, query: str, max_results: int) -> list[SearchHit]:
        per = max(3, max_results // 2)
        tasks = [asyncio.create_task(self._guarded(s, query, per)) for s in self._subs]
        best: dict[str, SearchHit] = {}

        def collect(finished: set) -> None:
            for t in finished:
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

        # Phase 1 — gather whatever the FAST providers return within the soft window (never longer
        # than the hard budget, so a patched/tiny budget still bounds the whole fan-out).
        soft = min(_SEARCH_SOFT_S, _SEARCH_BUDGET_S)
        done, pending = await asyncio.wait(set(tasks), timeout=soft)
        collect(done)
        # Phase 2 — only if we still have nothing, wait out the stragglers to the hard ceiling.
        if not best and pending:
            done, pending = await asyncio.wait(pending, timeout=_SEARCH_BUDGET_S - soft)
            collect(done)
        for t in pending:
            t.cancel()
        return sorted(best.values(), key=lambda h: h.score, reverse=True)[:max_results]

    async def search(self, query: str, *, max_results: int = 8) -> SearchResults:
        start = time.monotonic()
        key = f"{max_results}:{query.strip().lower()}"
        hits = await self._search_cache.get_or_compute(
            key, lambda: self._fan_out(query, max_results)
        )
        return SearchResults(
            query=query, hits=hits, latency_ms=int((time.monotonic() - start) * 1000)
        )

    async def _read_chain(self, url: str) -> str:
        # Priority chain (Jina → Firecrawl → Tavily → Apify): first reader to return text wins. Each
        # reader carries its own timeout, so the chain is bounded even if an early one is slow.
        for reader in self._readers:
            text = await reader.read(url)
            if text:
                return text
        return ""

    async def fetch(self, url: str) -> str:
        return await self._fetch_cache.get_or_compute(url, lambda: self._read_chain(url))


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
