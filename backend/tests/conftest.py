"""Shared fixtures. The `pg_pool` fixture connects to Postgres, or skips the test if there
isn't one (so the DB-backed tests run in CI, where Postgres is a service, and quietly skip
on a laptop without Docker)."""

from __future__ import annotations

import asyncio

import pytest
import pytest_asyncio

import app.tools.web as web
from app.db.pool import apply_schema, create_pool
from app.tools.search_provider import CannedProvider


@pytest.fixture(autouse=True)
def _clear_dependency_overrides():
    """Prevent dependency_overrides set in one test from leaking into the next."""
    from app.main import app
    yield
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _force_offline(monkeypatch):
    """Tests are hermetic: pin the model brain to the offline FakeQwen AND force the deterministic
    canned search provider, regardless of whatever real keys sit in the developer's .env (the web
    tools bind a live MultiProvider at import once keys are present)."""
    monkeypatch.setattr("app.config.settings.qwen_api_key", "", raising=False)
    canned = CannedProvider()
    monkeypatch.setattr(web.WEB_SEARCH, "_provider", canned, raising=False)
    monkeypatch.setattr(web.WEB_FETCH, "_provider", canned, raising=False)


@pytest_asyncio.fixture
async def pg_pool():
    try:
        pool = await asyncio.wait_for(create_pool(), timeout=3)
    except Exception as exc:  # noqa: BLE001 - any connect failure means "no DB here"
        pytest.skip(f"Postgres not available: {exc}")
    await apply_schema(pool)
    try:
        yield pool
    finally:
        await pool.close()
