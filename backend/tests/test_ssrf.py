"""The /parse SSRF guard. IP literals resolve without DNS, so these stay hermetic."""

from __future__ import annotations

import pytest

from app.tools.file_parse import assert_public_url


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/admin",
        "http://10.0.0.1/",
        "http://192.168.1.1/",
        "http://169.254.169.254/latest/meta-data/",  # cloud metadata
        "ftp://example.com/file",  # non-http scheme
        "file:///etc/passwd",
        "http://[::1]/",  # IPv6 loopback
    ],
)
async def test_rejects_unsafe_urls(url):
    with pytest.raises(ValueError):
        await assert_public_url(url)


async def test_allows_public_ip():
    await assert_public_url("http://8.8.8.8/")  # public — no raise
