# The Pack

A multi-agent orchestrator you can **watch**. You give the pack a task; a team of AI wolves —
Alpha (orchestrator), Beta (planner), Scouts (researchers), Tracker (analyst), Sentinel
(critic), Howler (writer) — plan it, run it, and surface decisions to you live on a visual
canvas (the Territory). Every action is a typed, append-only event; the UI is a pure function
of that event stream.

## Architecture

```
 Browser (React)            Python engine (FastAPI)              Rust gateway (Axum)
 ┌───────────────┐  REST   ┌──────────────────────────┐        ┌──────────────────┐
 │ Door / Territory│──────▶│ commands → Supervisor      │        │ read-only WS      │
 │ pure reducer    │  202   │ Emitter → Postgres (truth) │        │ fan-out (tail)    │
 │ over events     │        │ outbox relay → Redis ──────┼──XADD─▶│ XRANGE + XREAD    │
 │        ▲        │        └──────────────────────────┘        └────────┬─────────┘
 │        └──────────────────────── WS event stream ───────────────────────┘
 └───────────────┘
```

- **Engine (Python)** owns all logic and all writes. It assigns a dense, per-hunt `seq`,
  validates every event against the **frozen** schema (`backend/schema/events.schema.json`),
  and writes to Postgres in one transaction.
- **Transactional outbox.** Postgres is the single source of truth. A relay tails committed
  events and republishes them to Redis Streams — no dual-write inconsistency window. Delivery
  is at-least-once; the frontend reducer drops `seq <= lastSeq`, so duplicates are no-ops.
- **Gateway (Rust)** is a read-only WebSocket fan-out that tails Redis and streams events to
  browsers. It never writes.
- **Frontend (React)** renders only from the event stream via a pure reducer (CQRS read model).

The wolf brain and the web tools are **swappable**: with no API key the engine runs on a
deterministic offline provider (`FakeQwen`); the moment a real `QWEN_API_KEY` lands it uses
Qwen — with zero change to the orchestrator or the event stream.

## Run it locally

Prerequisites: Docker (Redis + Postgres), Python 3.12+, Rust/cargo (for the gateway), Node +
pnpm (for the frontend).

```bash
# 1. Infrastructure
docker compose up -d redis postgres        # pack/pack/pack

# 2. Engine (Python) — http://localhost:8000
cd backend
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000

# 3. Gateway (Rust) — ws://localhost:8080
cd gateway && cargo run

# 4. Frontend — http://localhost:5173
cd frontend
pnpm install
cp .env.example .env.local                 # points at the engine + gateway
pnpm dev
```

Then open the app → **Territory**:
- **Replay** mode plays any committed fixture into the canvas (no backend needed).
- **Live** mode (or the Door) starts a real hunt: `POST /hunts` → approve the plan → watch the
  pack work → answer the Hold → the final artifact returns.

`make test` runs the backend suite, the frontend tests, and a gateway check. The DB-backed
backend tests skip automatically if Postgres isn't running.

## API docs

The contract is simple: **commands return `202 Accepted`; the result arrives on the stream.**
A command nudges the running Supervisor, which emits the resulting events (in seq order). To
see what happened, watch the gateway WebSocket.

**Swagger / OpenAPI** — with the engine running, open:
- Swagger UI: <http://localhost:8000/docs>
- OpenAPI JSON: <http://localhost:8000/openapi.json>

**Postman** — import both files from `docs/postman/`:
1. `Pack.postman_collection.json` — every endpoint, with example bodies and saved example
   responses, plus a WebSocket entry for the stream.
2. `Pack.postman_environment.json` — `engineUrl`, `gatewayWs`, `hunt_id`, `hold_id`.

Select the **Pack — Local** environment. Run **Create hunt** first — its test script captures
`hunt_id` into the environment, so every other request is ready to fire. Then open a Postman
WebSocket request to `{{gatewayWs}}/hunts/{{hunt_id}}/stream?from_seq=0` and approve the plan.

### Endpoints

| Method | Path | What |
| --- | --- | --- |
| POST | `/hunts` | Open a hunt (202; starts planning) |
| GET | `/hunts/:id` | Snapshot — `state` + `last_seq` |
| POST | `/hunts/:id/plan/approve` | Approve plan, set the Boundary |
| POST | `/hunts/:id/holds/:hold_id/resolve` | Answer an open Hold |
| POST | `/hunts/:id/inputs` | Add input mid-hunt *(NEXT)* |
| POST | `/hunts/:id/stop` | Stop the hunt |
| POST | `/hunts/:id/resume` | Resume from checkpoint *(NEXT)* |
| POST | `/hunts/:id/benchmark` | Lone Wolf vs Pack *(NEXT)* |
| GET | `/hunts/:id/tracks/export` | Full event log for a hunt |
| GET / POST | `/instincts` | Saved plan presets |
| WS | `/hunts/:id/stream?from_seq=n` | **(gateway)** live event stream |

## Going live with Qwen

Put `QWEN_API_KEY` in `backend/.env` (copy `backend/.env.example`). The client auto-detects it
and switches off the offline provider — no code change. Then run
`python scripts/hello_qwen.py` to confirm the base URL, auth, the real model names for the
max/plus/flash tiers (update `QWEN_MODEL_*` if they differ), and the thinking-requires-streaming
behaviour.
