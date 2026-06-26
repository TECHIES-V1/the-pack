"""Academic / scholarly sub-providers."""

from __future__ import annotations

from app.tools.providers.base import SearchHit, _clip, _get_json


def _openalex_abstract(inv: object) -> str:
    """OpenAlex returns abstracts as an inverted index {word: [positions]}; rebuild the prose."""
    if not isinstance(inv, dict):
        return ""
    positions: list[tuple[int, str]] = []
    for word, idxs in inv.items():
        if isinstance(idxs, list):
            positions.extend((int(i), str(word)) for i in idxs)
    positions.sort()
    return " ".join(w for _, w in positions)


class OpenAlexSearch:
    """Keyless (OpenAlex's polite pool just wants a mailto)."""

    name = "openalex"
    _URL = "https://api.openalex.org/works"

    def __init__(self, mailto: str = "") -> None:
        self._mailto = mailto

    async def search(self, query: str, *, max_results: int) -> list[SearchHit]:
        params = {"search": query, "per_page": max_results}
        if self._mailto:
            params["mailto"] = self._mailto
        data = await _get_json(self._URL, params=params)
        if not isinstance(data, dict):
            return []
        out: list[SearchHit] = []
        for w in data.get("results", [])[:max_results]:
            loc = w.get("primary_location") or {}
            url = w.get("doi") or loc.get("landing_page_url") or w.get("id") or ""
            if not url:
                continue
            out.append(
                SearchHit(
                    title=str(w.get("title", "") or w.get("display_name", "")),
                    url=str(url),
                    snippet=_clip(_openalex_abstract(w.get("abstract_inverted_index"))),
                    provider=self.name,
                )
            )
        return out


class CoreSearch:
    name = "core"
    _URL = "https://api.core.ac.uk/v3/search/works"

    def __init__(self, api_key: str) -> None:
        self._key = api_key

    async def search(self, query: str, *, max_results: int) -> list[SearchHit]:
        data = await _get_json(
            self._URL,
            params={"q": query, "limit": max_results},
            headers={"Authorization": f"Bearer {self._key}"},
        )
        if not isinstance(data, dict):
            return []
        out: list[SearchHit] = []
        for w in data.get("results", [])[:max_results]:
            url = w.get("downloadUrl") or w.get("doi") or ""
            if not url:
                continue
            out.append(
                SearchHit(
                    title=str(w.get("title", "")),
                    url=str(url),
                    snippet=_clip(str(w.get("abstract", "") or "")),
                    provider=self.name,
                )
            )
        return out
