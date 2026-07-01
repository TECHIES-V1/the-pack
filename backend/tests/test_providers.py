"""Hermetic tests for the multi-source research providers — no network. We stub the shared httpx
helpers per module and assert each parser maps the upstream JSON to clean SearchHits, plus the
MultiProvider merge/dedupe and the offline fallback."""

from __future__ import annotations

from app.tools.providers.academic import OpenAlexSearch, _openalex_abstract
from app.tools.providers.base import SearchHit
from app.tools.providers.community import GitHubSearch, HackerNewsSearch
from app.tools.providers.kg import DBpediaSearch, WikidataSearch
from app.tools.providers.news import NewsApiSearch
from app.tools.providers.web import ExaSearch
from app.tools.search_provider import CannedProvider, MultiProvider, make_search_provider


def _stub(monkeypatch, module: str, fn: str, payload):
    async def _fake(*_a, **_k):
        return payload

    monkeypatch.setattr(f"app.tools.providers.{module}.{fn}", _fake)


async def test_exa_parses_results(monkeypatch):
    _stub(
        monkeypatch,
        "web",
        "_post_json",
        {"results": [{"title": "T", "url": "https://a.com", "text": "body", "score": 0.9}]},
    )
    hits = await ExaSearch("k").search("q", max_results=5)
    assert len(hits) == 1
    assert hits[0].url == "https://a.com" and hits[0].provider == "exa" and hits[0].score == 0.9


async def test_newsapi_skips_urlless(monkeypatch):
    _stub(
        monkeypatch,
        "news",
        "_get_json",
        {
            "articles": [
                {"title": "A", "url": "https://n.com/1", "description": "d"},
                {"title": "B"},
            ]
        },
    )
    hits = await NewsApiSearch("k").search("q", max_results=5)
    assert [h.url for h in hits] == ["https://n.com/1"]


def test_openalex_abstract_rebuilds_from_inverted_index():
    inv = {"Hello": [0], "world": [1], "again": [2]}
    assert _openalex_abstract(inv) == "Hello world again"
    assert _openalex_abstract(None) == ""


async def test_openalex_prefers_doi(monkeypatch):
    _stub(
        monkeypatch,
        "academic",
        "_get_json",
        {
            "results": [
                {
                    "display_name": "Paper",
                    "doi": "https://doi.org/10.1/x",
                    "abstract_inverted_index": {"big": [0], "idea": [1]},
                }
            ]
        },
    )
    hits = await OpenAlexSearch("me@x.com").search("q", max_results=5)
    assert hits[0].url == "https://doi.org/10.1/x" and "big idea" in hits[0].snippet


async def test_wikidata_uses_concepturi(monkeypatch):
    _stub(
        monkeypatch,
        "kg",
        "_get_json",
        {"search": [{"label": "Tesla", "description": "company", "concepturi": "http://wd/Q1"}]},
    )
    hits = await WikidataSearch().search("tesla", max_results=5)
    assert hits[0].url == "http://wd/Q1" and hits[0].provider == "wikidata"


async def test_dbpedia_unwraps_arrays(monkeypatch):
    _stub(
        monkeypatch,
        "kg",
        "_get_json",
        {
            "docs": [
                {"label": ["SpaceX"], "resource": ["http://dbp/SpaceX"], "comment": ["rockets"]}
            ]
        },
    )
    hits = await DBpediaSearch().search("spacex", max_results=5)
    assert hits[0].title == "SpaceX" and hits[0].url == "http://dbp/SpaceX"


async def test_hackernews_falls_back_to_item_url(monkeypatch):
    _stub(
        monkeypatch,
        "community",
        "_get_json",
        {"hits": [{"title": "Ask HN", "objectID": "42", "points": 7}]},
    )
    hits = await HackerNewsSearch().search("q", max_results=5)
    assert hits[0].url == "https://news.ycombinator.com/item?id=42" and hits[0].score == 7


async def test_github_scores_by_stars(monkeypatch):
    _stub(
        monkeypatch,
        "community",
        "_get_json",
        {
            "items": [
                {
                    "full_name": "a/b",
                    "html_url": "https://gh/ab",
                    "description": "d",
                    "stargazers_count": 1200,
                }
            ]
        },
    )
    hits = await GitHubSearch("t").search("q", max_results=5)
    assert hits[0].score == 1200.0


async def test_dead_upstream_returns_empty(monkeypatch):
    _stub(monkeypatch, "web", "_post_json", None)  # helper swallowed an error
    assert await ExaSearch("k").search("q", max_results=5) == []


class _FakeSub:
    name = "fake"

    def __init__(self, hits):
        self._hits = hits

    async def search(self, query, *, max_results):
        return self._hits


async def test_multiprovider_merges_dedupes_and_ranks():
    a = SearchHit("A", "https://x.com", "s", score=0.5, provider="p1")
    a_dup = SearchHit(
        "A2", "https://x.com", "s", score=0.9, provider="p2"
    )  # same url, higher score
    b = SearchHit("B", "https://y.com", "s", score=0.7, provider="p1")
    mp = MultiProvider([_FakeSub([a, b]), _FakeSub([a_dup])], readers=[])
    res = await mp.search("q", max_results=8)
    urls = [h.url for h in res.hits]
    assert urls == ["https://x.com", "https://y.com"]  # deduped, ranked by score
    assert res.hits[0].score == 0.9  # kept the higher-scored duplicate


async def test_multiprovider_isolates_a_failing_sub():
    class _Boom:
        name = "boom"

        async def search(self, query, *, max_results):
            raise RuntimeError("down")

    ok = SearchHit("A", "https://x.com", "s", score=0.5)
    mp = MultiProvider([_Boom(), _FakeSub([ok])], readers=[])
    res = await mp.search("q", max_results=8)
    assert [h.url for h in res.hits] == ["https://x.com"]  # the crash didn't sink the search


async def test_multiprovider_returns_within_budget(monkeypatch):
    import asyncio

    import app.tools.search_provider as sp

    monkeypatch.setattr(sp, "_SEARCH_BUDGET_S", 0.2)

    class _Slow:
        name = "slow"

        async def search(self, query, *, max_results):
            await asyncio.sleep(2)
            return [SearchHit("slow", "https://slow.com", "s")]

    fast = SearchHit("F", "https://fast.com", "s", score=0.5)
    mp = sp.MultiProvider([_Slow(), _FakeSub([fast])], readers=[])
    res = await mp.search("q", max_results=8)
    assert [h.url for h in res.hits] == ["https://fast.com"]  # slow upstream cancelled at budget


async def test_multiprovider_returns_at_soft_deadline_with_ground(monkeypatch):
    """The fix: once we have ANY ground, don't block on a hung upstream — return at the soft
    deadline instead of waiting out the whole budget (what was starving parallel scouts)."""
    import asyncio
    import time

    import app.tools.search_provider as sp

    monkeypatch.setattr(sp, "_SEARCH_SOFT_S", 0.15)
    monkeypatch.setattr(sp, "_SEARCH_BUDGET_S", 5.0)  # generous hard ceiling, should NOT be hit

    class _Hung:
        name = "hung"

        async def search(self, query, *, max_results):
            await asyncio.sleep(3)
            return [SearchHit("hung", "https://hung.com", "s")]

    fast = SearchHit("F", "https://fast.com", "s", score=0.5)
    mp = sp.MultiProvider([_Hung(), _FakeSub([fast])], readers=[])
    start = time.monotonic()
    res = await mp.search("q", max_results=8)
    elapsed = time.monotonic() - start
    assert [h.url for h in res.hits] == ["https://fast.com"]  # didn't wait on the hung provider
    assert elapsed < 1.0  # returned at the soft deadline, not the 3s sub / 5s budget


async def test_multiprovider_extends_to_budget_when_nothing_fast(monkeypatch):
    """Desperate path: if nothing returns inside the soft window, wait out the stragglers to the
    hard ceiling rather than giving up empty."""
    import asyncio

    import app.tools.search_provider as sp

    monkeypatch.setattr(sp, "_SEARCH_SOFT_S", 0.1)
    monkeypatch.setattr(sp, "_SEARCH_BUDGET_S", 2.0)

    class _Late:
        name = "late"

        async def search(self, query, *, max_results):
            await asyncio.sleep(0.3)  # past the soft window, within the budget
            return [SearchHit("L", "https://late.com", "s")]

    mp = sp.MultiProvider([_Late()], readers=[])
    res = await mp.search("q", max_results=8)
    assert [h.url for h in res.hits] == ["https://late.com"]  # the budget path waited it out


def test_offline_fallback_when_no_keys(monkeypatch):
    for k in (
        "search_api_key",
        "exa_api_key",
        "serpapi_api_key",
        "youcom_api_key",
        "newsapi_key",
        "gnews_api_key",
        "newsdata_api_key",
        "core_api_key",
        "github_token",
        "google_kg_api_key",
        "jina_api_key",
        "firecrawl_api_key",
        "apify_api_key",
    ):
        monkeypatch.setattr(f"app.config.settings.{k}", "", raising=False)
    assert isinstance(make_search_provider(), CannedProvider)
