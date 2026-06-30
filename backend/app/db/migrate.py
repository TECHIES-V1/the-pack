"""Lightweight migration runner — replaces `apply_schema` for safe, versioned schema evolution.

Migrations are plain SQL files in app/db/migrations/, named 0001_*.sql, 0002_*.sql, ... .
Each runs exactly once per database, tracked in the `schema_migrations` table. Idempotent:
safe on every boot, zero-cost after all migrations are applied. No Alembic, no SQLAlchemy —
raw asyncpg to keep the dep surface small.

Ordering rule: lexicographic on filename, so four-digit prefixes like 0001_, 0002_, ... give
deterministic order across OS filesystems.
"""

from __future__ import annotations

import logging
from pathlib import Path

import asyncpg

_LOG = logging.getLogger(__name__)

_MIGRATIONS_DIR = Path(__file__).parent / "migrations"


async def run_migrations(pool: asyncpg.Pool) -> None:
    """Apply every unapplied migration in lexicographic filename order."""
    async with pool.acquire() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version    TEXT        PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        applied = {r["version"] for r in await conn.fetch("SELECT version FROM schema_migrations")}

    for path in sorted(_MIGRATIONS_DIR.glob("*.sql")):
        version = path.stem
        if version in applied:
            continue
        _LOG.info("applying migration %s …", version)
        sql = path.read_text(encoding="utf-8")
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(sql)
                await conn.execute(
                    "INSERT INTO schema_migrations (version) VALUES ($1)", version
                )
        _LOG.info("migration %s applied", version)
