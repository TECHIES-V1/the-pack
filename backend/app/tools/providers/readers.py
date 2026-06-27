"""Deep-read readers — turn a URL into readable text. Tried in order by the MultiProvider until
one returns content. Each returns None on any failure so the chain falls through."""

from __future__ import annotations

from app.tools.providers.base import _get_text, _post_json


class JinaReader:
    name = "jina"

    def __init__(self, api_key: str) -> None:
        self._key = api_key

    async def read(self, url: str) -> str | None:
        text = await _get_text(
            f"https://r.jina.ai/{url}",
            headers={"Authorization": f"Bearer {self._key}", "Accept": "text/plain"},
            timeout=15.0,
        )
        return text.strip() if text and text.strip() else None


class FirecrawlReader:
    name = "firecrawl"
    _URL = "https://api.firecrawl.dev/v1/scrape"

    def __init__(self, api_key: str) -> None:
        self._key = api_key

    async def read(self, url: str) -> str | None:
        data = await _post_json(
            self._URL,
            headers={"Authorization": f"Bearer {self._key}"},
            json={"url": url, "formats": ["markdown"]},
            timeout=20.0,
        )
        if not isinstance(data, dict):
            return None
        md = (data.get("data") or {}).get("markdown") or ""
        return md.strip() or None


class TavilyExtractReader:
    name = "tavily-extract"
    _URL = "https://api.tavily.com/extract"

    def __init__(self, api_key: str) -> None:
        self._key = api_key

    async def read(self, url: str) -> str | None:
        data = await _post_json(self._URL, json={"api_key": self._key, "urls": [url]}, timeout=20.0)
        if not isinstance(data, dict):
            return None
        results = data.get("results", [])
        if not results:
            return None
        return str(results[0].get("raw_content", "")).strip() or None


class ApifyReader:
    """Best-effort — Apify actor runs are slow; usually times out and the chain moves on. Last."""

    name = "apify"
    _URL = "https://api.apify.com/v2/acts/apify~website-content-crawler/run-sync-get-dataset-items"

    def __init__(self, api_key: str) -> None:
        self._key = api_key

    async def read(self, url: str) -> str | None:
        data = await _post_json(
            f"{self._URL}?token={self._key}",
            json={"startUrls": [{"url": url}], "maxCrawlPages": 1},
            timeout=25.0,
        )
        if not isinstance(data, list) or not data:
            return None
        return str((data[0] or {}).get("text", "")).strip() or None
