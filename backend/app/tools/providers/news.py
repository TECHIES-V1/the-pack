"""News sub-providers — current-events coverage."""

from __future__ import annotations

from app.tools.providers.base import SearchHit, _clip, _get_json


class NewsApiSearch:
    name = "newsapi"
    _URL = "https://newsapi.org/v2/everything"

    def __init__(self, api_key: str) -> None:
        self._key = api_key

    async def search(self, query: str, *, max_results: int) -> list[SearchHit]:
        data = await _get_json(
            self._URL,
            params={"q": query, "pageSize": max_results, "sortBy": "relevancy", "language": "en"},
            headers={"X-Api-Key": self._key},
        )
        if not isinstance(data, dict):
            return []
        return [
            SearchHit(
                title=str(a.get("title", "")),
                url=str(a.get("url", "")),
                snippet=_clip(str(a.get("description", "") or "")),
                provider=self.name,
            )
            for a in data.get("articles", [])
            if a.get("url")
        ]


class GNewsSearch:
    name = "gnews"
    _URL = "https://gnews.io/api/v4/search"

    def __init__(self, api_key: str) -> None:
        self._key = api_key

    async def search(self, query: str, *, max_results: int) -> list[SearchHit]:
        data = await _get_json(
            self._URL,
            params={"q": query, "max": max_results, "lang": "en", "apikey": self._key},
        )
        if not isinstance(data, dict):
            return []
        return [
            SearchHit(
                title=str(a.get("title", "")),
                url=str(a.get("url", "")),
                snippet=_clip(str(a.get("description", "") or "")),
                provider=self.name,
            )
            for a in data.get("articles", [])
            if a.get("url")
        ]


class NewsDataSearch:
    name = "newsdata"
    _URL = "https://newsdata.io/api/1/news"

    def __init__(self, api_key: str) -> None:
        self._key = api_key

    async def search(self, query: str, *, max_results: int) -> list[SearchHit]:
        data = await _get_json(
            self._URL, params={"q": query, "apikey": self._key, "language": "en"}
        )
        if not isinstance(data, dict):
            return []
        return [
            SearchHit(
                title=str(a.get("title", "")),
                url=str(a.get("link", "")),
                snippet=_clip(str(a.get("description", "") or "")),
                provider=self.name,
            )
            for a in (data.get("results", []) or [])[:max_results]
            if a.get("link")
        ]
