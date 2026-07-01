"""SSRF-safe URL validation and fetch — shared by every server-side fetch path.

assert_public_url validates a single URL's resolved IP against the private/loopback/reserved
blocklist. safe_fetch re-validates on every redirect hop so a 302 to 169.254.169.254 can't
sneak past the initial check (the classic SSRF redirect bypass).
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from urllib.parse import urljoin, urlparse

import httpx


async def assert_public_url(url: str) -> None:
    """Allow only http/https and reject any URL resolving to a private / loopback / reserved
    address (e.g. localhost, 10.x, 169.254.169.254 cloud-metadata, ::1)."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("only http/https URLs are allowed")
    host = parsed.hostname
    if not host:
        raise ValueError("missing host")
    try:
        infos = await asyncio.get_event_loop().getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise ValueError(f"could not resolve host: {exc}") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            raise ValueError("URL resolves to a non-public address")


async def safe_fetch(
    url: str,
    *,
    headers: dict | None = None,
    timeout: float = 20.0,
    max_redirects: int = 5,
) -> httpx.Response:
    """SSRF-safe HTTP GET. Validates EVERY URL in the redirect chain — not just the initial URL —
    so a server-controlled 302 cannot redirect us to an internal address after validation passes."""
    current = url
    for _ in range(max_redirects + 1):
        await assert_public_url(current)
        async with httpx.AsyncClient(follow_redirects=False, timeout=timeout) as client:
            resp = await client.get(current, headers=headers or {})
        if resp.status_code in (301, 302, 303, 307, 308):
            location = resp.headers.get("location", "")
            if not location:
                break
            current = urljoin(current, location)
            continue
        resp.raise_for_status()
        return resp
    raise ValueError(f"too many redirects fetching {url}")
