"""Web tools — web_search and web_fetch (Doc 04 §04).

Canned today (deterministic results so the offline hunt is reproducible), real NEXT. The
interface and the engine's gate-and-emit wrapper are identical either way, so the swap to a
live search/fetch provider is a body change here and nothing else.
"""

from __future__ import annotations

from app.tools.base import ToolResult


class WebSearch:
    name = "web_search"

    async def run(self, *, wolf_id: str, query: str, **_: object) -> ToolResult:
        # Canned: pretend we hit a search API and got a results page back.
        return ToolResult(
            ok=True,
            result_ref=f"art_{wolf_id}_search",
            latency_ms=2100,
            data={"query": query, "hits": 3},
        )


class WebFetch:
    name = "web_fetch"

    async def run(self, *, wolf_id: str, url: str, **_: object) -> ToolResult:
        return ToolResult(
            ok=True,
            result_ref=f"art_{wolf_id}_fetch",
            latency_ms=900,
            data={"url": url, "chars": 4200},
        )


WEB_SEARCH = WebSearch()
WEB_FETCH = WebFetch()
