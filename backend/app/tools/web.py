"""Web tools — web_search and web_fetch (Doc 04 §04).

These delegate to a pluggable `SearchProvider` (app/tools/search_provider.py): a real
`SEARCH_API_KEY` selects the live vendor (Tavily by default), an empty key falls back to the
deterministic canned provider so the offline hunt still runs end to end. The interface and the
engine's gate-and-emit wrapper are identical either way — swapping providers changes nothing
upstream. The raw hits ride back on `ToolResult.data`; the Supervisor persists them as an
artifact and points `result_ref` at it, so Tracker and Howler read real ground truth.
"""

from __future__ import annotations

from app.tools.base import ToolResult
from app.tools.search_provider import SEARCH_PROVIDER, SearchProvider


class WebSearch:
    name = "web_search"

    def __init__(self, provider: SearchProvider | None = None) -> None:
        self._provider = provider or SEARCH_PROVIDER

    async def run(
        self, *, wolf_id: str, query: str, max_results: int = 5, **_: object
    ) -> ToolResult:
        try:
            results = await self._provider.search(query, max_results=max_results)
            return ToolResult(
                ok=bool(results.hits),
                result_ref=None,  # the Supervisor persists hits and sets the real ref
                latency_ms=results.latency_ms,
                data=results.as_dict(),
            )
        except Exception as exc:  # noqa: BLE001 - a tool failure is data, not a crash (Stray-detected)
            return ToolResult(
                ok=False,
                result_ref=None,
                latency_ms=0,
                data={"query": query, "error": str(exc)},
            )


class WebFetch:
    name = "web_fetch"

    def __init__(self, provider: SearchProvider | None = None) -> None:
        self._provider = provider or SEARCH_PROVIDER

    async def run(self, *, wolf_id: str, url: str, **_: object) -> ToolResult:
        try:
            text = await self._provider.fetch(url)
            return ToolResult(
                ok=bool(text),
                result_ref=None,
                latency_ms=0,
                data={"url": url, "chars": len(text), "text": text},
            )
        except Exception as exc:  # noqa: BLE001
            return ToolResult(ok=False, result_ref=None, latency_ms=0, data={"url": url, "error": str(exc)})


WEB_SEARCH = WebSearch()
WEB_FETCH = WebFetch()
