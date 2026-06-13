# Pack

**A pack of AI agents, led by an orchestrator named Alpha, that hunts your task down while
you watch.** No code. No config. No jargon. You describe a task in plain language, then
watch the pack plan it, hunt it, argue over it, and deliver it — live, on a visual canvas.

> Qwen Cloud Global AI Hackathon · Agent Society Track · **submit July 8** (deadline
> Jul 9, 2:00 pm Pacific). Build doc set: `docs/pack/` (PRD, Flows, Frontend, Backend,
> Prerequisites).

## Architecture decisions (confirmed)

- **D1 — backend shape (CLOSED):** a **Python brain** does all the thinking, a **Rust
  gateway** does all the streaming, with **Redis Streams** as the one-directional seam
  between them. Fallback built in: delete the gateway and FastAPI serves the stream
  directly. (Doc 04 §2.)
- **D2 — canvas (CHOSEN):** **React Flow** (`@xyflow/react`, MIT) + dagre + Framer Motion,
  on a Vite + React 18 + TS frontend. (Doc 03 §3.)

Two rules govern everything else:
1. **The PRD is the contract.** Not in P0/P1 → P2 → `PARKING_LOT.md`, zero code.
2. **The event stream is the spine.** The backend emits a typed event for every action;
   the frontend renders *only* from that stream. One pipeline feeds the Territory, Tracks,
   the Boundary, Stray detection, and the benchmark. (`schema/events.schema.json`.)

## Repo map

The repo is split so the two teams own self-contained folders — nothing they both edit
lives at the root (keeps merge conflicts off the critical path).

```
backend/       the Python engine (FastAPI) — OWNS the contract + all writes
  schema/        events.schema.json — the FROZEN event contract (the spine)
  fixtures/      the four hand-authored event streams (canonical copy)
  prompts/       /{wolf}/v1.md — the seven wolf system prompts
  app/ tests/ scripts/  engine code, contract tests, hello-pack seam demo
  .env.example   server-side secrets template
gateway/       the Rust gateway (Axum) — realtime read path only (self-contained)
frontend/      the Territory (Vite + React Flow) — renders only from the stream
  fixtures/      synced copy of the pack (self-contained; backend is canonical)
  .env.example   VITE_* public config only (no secrets)
docs/          BORROWING.md, pack/ (build docs), SETUP_REPORT.md, GATE_STATUS.md
.github/workflows/  one workflow per team: backend / frontend / gateway / secrets
COMPLIANCE.md · PARKING_LOT.md · LICENSE · Makefile · docker-compose.yml  (lead-owned)
```

## Quickstart

```bash
# infra (redis + postgres)
docker compose up -d redis postgres

# backend — the engine + contract tests
cd backend && uv sync --extra dev   # or: python -m venv .venv && pip install -e ".[dev]"
uv run pytest                        # the fixtures stay green
uv run uvicorn app.main:app --reload --port 8000

# frontend — the Territory
cd frontend && pnpm install && pnpm dev   # http://localhost:5173

# gateway — the stream fan-out
cd gateway && cargo run                   # :8080

# the seam demo (hello-pack): push a fixture through real infra
cd backend && uv run python scripts/hello_pack.py flow_a_researcher.jsonl
```

On Windows, `pwsh scripts/dev.ps1` launches all three services. See `Makefile` for targets.

## Status

Day-Zero setup is done; the gate scorecard (what's green vs. blocked) lives in
`docs/GATE_STATUS.md`. The naming convention: **screens speak Pack; code speaks plain
engineering.** Never let the metaphor leak into the codebase.

— *Send the pack.*
