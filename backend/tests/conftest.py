"""Shared fixtures. The `pg_pool` fixture connects to Postgres, or skips the test if there
isn't one (so the DB-backed tests run in CI, where Postgres is a service, and quietly skip
on a laptop without Docker)."""

from __future__ import annotations

import asyncio

import pytest
import pytest_asyncio

from app.db.pool import apply_schema, create_pool


@pytest.fixture(autouse=True)
def _force_offline(monkeypatch):
    """Tests are hermetic: pin the model brain to the offline FakeQwen regardless of whether a
    real QWEN_API_KEY happens to sit in the developer's .env."""
    monkeypatch.setattr("app.config.settings.qwen_api_key", "", raising=False)


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
