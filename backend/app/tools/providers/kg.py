"""Knowledge-graph sub-providers — entity facts and definitions."""

from __future__ import annotations

from app.tools.providers.base import SearchHit, _clip, _get_json


def _first(v: object) -> str:
    if isinstance(v, list):
        return str(v[0]) if v else ""
    return str(v or "")


class WikidataSearch:
    """Keyless — Wikidata entity search."""

    name = "wikidata"
    _URL = "https://www.wikidata.org/w/api.php"

    async def search(self, query: str, *, max_results: int) -> list[SearchHit]:
        data = await _get_json(
            self._URL,
            params={
                "action": "wbsearchentities",
                "search": query,
                "language": "en",
                "format": "json",
                "limit": max_results,
            },
        )
        if not isinstance(data, dict):
            return []
        return [
            SearchHit(
                title=str(r.get("label", "")),
                url=str(r.get("concepturi", "") or r.get("url", "")),
                snippet=_clip(str(r.get("description", "") or "")),
                provider=self.name,
            )
            for r in data.get("search", [])
            if r.get("concepturi") or r.get("url")
        ]


class GoogleKgSearch:
    name = "google_kg"
    _URL = "https://kgsearch.googleapis.com/v1/entities:search"

    def __init__(self, api_key: str) -> None:
        self._key = api_key

    async def search(self, query: str, *, max_results: int) -> list[SearchHit]:
        data = await _get_json(
            self._URL,
            params={"query": query, "key": self._key, "limit": max_results, "languages": "en"},
        )
        if not isinstance(data, dict):
            return []
        out: list[SearchHit] = []
        for el in data.get("itemListElement", [])[:max_results]:
            r = el.get("result", {}) if isinstance(el, dict) else {}
            desc = (r.get("detailedDescription") or {}).get("articleBody", "") or r.get(
                "description", ""
            )
            url = (
                r.get("url") or (r.get("detailedDescription") or {}).get("url") or r.get("@id", "")
            )
            if not url:
                continue
            out.append(
                SearchHit(
                    title=str(r.get("name", "")),
                    url=str(url),
                    snippet=_clip(str(desc)),
                    provider=self.name,
                )
            )
        return out


class DBpediaSearch:
    """Keyless — DBpedia Lookup."""

    name = "dbpedia"
    _URL = "https://lookup.dbpedia.org/api/search"

    async def search(self, query: str, *, max_results: int) -> list[SearchHit]:
        data = await _get_json(
            self._URL,
            params={"query": query, "maxResults": max_results, "format": "json"},
        )
        if not isinstance(data, dict):
            return []
        return [
            SearchHit(
                title=_first(d.get("label")),
                url=_first(d.get("resource")),
                snippet=_clip(_first(d.get("comment"))),
                provider=self.name,
            )
            for d in data.get("docs", [])[:max_results]
            if _first(d.get("resource"))
        ]
