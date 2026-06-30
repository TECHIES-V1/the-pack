"""The asyncpg connection pool — owned by the app lifespan (Doc 04 §5).

One pool per process. Created on startup, the schema applied once (idempotent), closed on
shutdown. A jsonb codec is installed so `payload` round-trips as a dict, not a string.
"""

from __future__ import annotations

import json
from pathlib import Path

import asyncpg

from app.config import settings

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


async def _init_connection(conn: asyncpg.Connection) -> None:
    # jsonb in/out as native dicts — no manual json.dumps at every call site.
    await conn.set_type_codec(
        "jsonb",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
    )


async def create_pool() -> asyncpg.Pool:
    # asyncpg accepts a libpq sslmode string for `ssl` (e.g. "require", "verify-full").
    # Empty → no TLS, for local Docker. Cloud RDS sets POSTGRES_SSLMODE=require.
    kwargs: dict = {}
    if settings.postgres_sslmode:
        kwargs["ssl"] = settings.postgres_sslmode
    return await asyncpg.create_pool(
        dsn=settings.postgres_url,
        min_size=5,                         # keep 5 warm; relay holds 1, leaves 4 always ready
        max_size=settings.db_pool_max_size,
        command_timeout=60.0,               # headroom for long event replays
        max_inactive_connection_lifetime=300.0,
        init=_init_connection,
        **kwargs,
    )


async def apply_schema(pool: asyncpg.Pool) -> None:
    """Run schema.sql. Idempotent — safe on every boot."""
    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    async with pool.acquire() as conn:
        await conn.execute(sql)
