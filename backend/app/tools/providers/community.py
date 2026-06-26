"""Community sub-providers — developer + forum signal."""

from __future__ import annotations

from app.tools.providers.base import SearchHit, _clip, _get_json


class GitHubSearch:
    name = "github"
    _URL = "https://api.github.com/search/repositories"

    def __init__(self, token: str) -> None:
        self._token = token

    async def search(self, query: str, *, max_results: int) -> list[SearchHit]:
        data = await _get_json(
            self._URL,
            params={"q": query, "per_page": max_results, "sort": "stars"},
            headers={
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/vnd.github+json",
            },
        )
        if not isinstance(data, dict):
            return []
        return [
            SearchHit(
                title=str(r.get("full_name", "")),
                url=str(r.get("html_url", "")),
                snippet=_clip(str(r.get("description", "") or "")),
                score=float(r.get("stargazers_count", 0) or 0),
                provider=self.name,
            )
            for r in data.get("items", [])[:max_results]
            if r.get("html_url")
        ]


class HackerNewsSearch:
    """Keyless — HN's Algolia search front-end."""

    name = "hackernews"
    _URL = "https://hn.algolia.com/api/v1/search"

    async def search(self, query: str, *, max_results: int) -> list[SearchHit]:
        data = await _get_json(self._URL, params={"query": query, "hitsPerPage": max_results})
        if not isinstance(data, dict):
            return []
        out: list[SearchHit] = []
        for h in data.get("hits", [])[:max_results]:
            url = h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID', '')}"
            title = h.get("title") or h.get("story_title") or "Hacker News discussion"
            out.append(
                SearchHit(
                    title=str(title),
                    url=str(url),
                    snippet=_clip(str(h.get("story_text", "") or h.get("comment_text", "") or "")),
                    score=float(h.get("points", 0) or 0),
                    provider=self.name,
                )
            )
        return out
