# backend — the Python brain (engine)

FastAPI · asyncio · Pydantic v2 · the OpenAI SDK pointed at Qwen's compatible endpoint ·
asyncpg. Owns the whole brain (Alpha loop, wolves, tools, Standoffs, Strays, Holds, the
Boundary), **all** REST commands, and **all** writes — it appends every event to the Redis
stream and archives it to Postgres (Doc 04 §2).

## Layout

```
app/
  config.py            env-driven settings + the model-tier registry
  main.py              the REST API surface (Doc 04 §6) — commands return 202
  events/models.py     the Event envelope + the frozen-schema loader
  bus/redis_stream.py  XADD writer + XRANGE replay over Redis Streams (the seam)
  qwen/client.py       the single inference chokepoint (tiers, thinking, accounting)
  engine/boundary.py   the gate-before-the-call (warn 70 / downgrade 85 / halt 100)
  engine/stray.py      sliding-window stray heuristics
scripts/hello_pack.py  pushes a fixture stream into Redis (the seam demo)
tests/test_contract.py every fixture validates against schema/events.schema.json
```

## Quickstart

```bash
# from backend/
uv sync --extra dev            # or: python -m venv .venv && pip install -e ".[dev]"
uv run pytest                  # contract tests: the fixtures stay green
uv run uvicorn app.main:app --reload --port 8000
```

## The seam demo (hello-pack)

```bash
docker compose up -d redis     # from repo root
uv run python scripts/hello_pack.py flow_a_researcher.jsonl
# then start the gateway and tail /hunts/hunt_a/stream?from_seq=0
```

## Rules that bind this service

- The engine is the **only** writer to the stream. The gateway only reads.
- One JSON envelope format end to end (schema/events.schema.json) — no second format.
- Thinking mode requires streaming — non-streamed thinking calls fail. See `qwen/client.py`.
- Keys are server-side only. Real model names live in config, verified in Model Studio.
- Code speaks plain engineering (orchestrator, event, checkpoint). The metaphor stays on
  the screens, never in this codebase.
