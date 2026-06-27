"""General web-search sub-providers."""

from __future__ import annotations

from app.tools.providers.base import SearchHit, _clip, _get_json, _post_json


class TavilySearch:
    name = "tavily"
    _URL = "https://api.tavily.com/search"

    def __init__(self, api_key: str) -> None:
        self._key = api_key

    async def search(self, query: str, *, max_results: int) -> list[SearchHit]:
        data = await _post_json(
            self._URL,
            json={
                "api_key": self._key,
                "query": query,
                "max_results": max_results,
                "search_depth": "advanced",
            },
        )
        if not isinstance(data, dict):
            return []
        return [
            SearchHit(
                title=str(r.get("title", "")),
                url=str(r.get("url", "")),
                snippet=_clip(str(r.get("content", ""))),
                score=float(r.get("score", 0.0) or 0.0),
                provider=self.name,
            )
            for r in data.get("results", [])
            if r.get("url")
        ]


class ExaSearch:
    name = "exa"
    _URL = "https://api.exa.ai/search"

    def __init__(self, api_key: str) -> None:
        self._key = api_key

    async def search(self, query: str, *, max_results: int) -> list[SearchHit]:
        data = await _post_json(
            self._URL,
            headers={"x-api-key": self._key},
            json={
                "query": query,
                "numResults": max_results,
                "contents": {"text": {"maxCharacters": 600}},
            },
        )
        if not isinstance(data, dict):
            return []
        return [
            SearchHit(
                title=str(r.get("title", "") or ""),
                url=str(r.get("url", "")),
                snippet=_clip(str(r.get("text", "") or "")),
                score=float(r.get("score", 0.0) or 0.0),
                provider=self.name,
            )
            for r in data.get("results", [])
            if r.get("url")
        ]


class SerpApiSearch:
    name = "serpapi"
    _URL = "https://serpapi.com/search.json"

    def __init__(self, api_key: str) -> None:
        self._key = api_key

    async def search(self, query: str, *, max_results: int) -> list[SearchHit]:
        data = await _get_json(
            self._URL,
            params={"engine": "google", "q": query, "num": max_results, "api_key": self._key},
        )
        if not isinstance(data, dict):
            return []
        return [
            SearchHit(
                title=str(r.get("title", "")),
                url=str(r.get("link", "")),
                snippet=_clip(str(r.get("snippet", ""))),
                score=0.0,
                provider=self.name,
            )
            for r in data.get("organic_results", [])
            if r.get("link")
        ]


class YouSearch:
    name = "you.com"
    _URL = "https://api.ydc-index.io/search"

    def __init__(self, api_key: str) -> None:
        self._key = api_key

    async def search(self, query: str, *, max_results: int) -> list[SearchHit]:
        data = await _get_json(self._URL, params={"query": query}, headers={"X-API-Key": self._key})
        if not isinstance(data, dict):
            return []
        hits = data.get("hits", []) or []
        out: list[SearchHit] = []
        for r in hits[:max_results]:
            snippets = r.get("snippets") or []
            snippet = snippets[0] if snippets else r.get("description", "")
            if not r.get("url"):
                continue
            out.append(
                SearchHit(
                    title=str(r.get("title", "")),
                    url=str(r.get("url", "")),
                    snippet=_clip(str(snippet)),
                    provider=self.name,
                )
            )
        return out
