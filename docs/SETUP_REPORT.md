# Setup report — Day-Zero repo bring-up

**Date:** 2026-06-13 · **Branch:** `setup/day-zero` · **Starting commit:** `af66ba5`
("Added the essential repos")

## What this was, and what it is now

The repo arrived as a **dump of four reference frameworks** with no application code:
`autogen-main/`, `langgraph-main/`, `letta-main/`, `open-agent-builder-main/` (4,051 files,
Python/TS/C#/Jupyter). Per the PACK docs these are **study-and-borrow** sources, not
dependencies (Doc 04 §4A, Doc 03 §3).

It is now the **monorepo the docs prescribe**: a Python brain + Rust gateway + Vite/React
Flow frontend on a single frozen event spine, with the gate prerequisites that don't need
external credentials completed.

## What was removed, and why

| Removed | Why | Where it lives now |
|---|---|---|
| `autogen-main/` | Reference for the Alpha loop (Magentic-One dual ledgers). Not a dependency; the C# was its .NET half. | Borrow map → `docs/BORROWING.md` |
| `langgraph-main/` | Reference for state graph / checkpoints / Holds. | `docs/BORROWING.md` |
| `letta-main/` | Reference for the Elder (tiered memory) — a **P1** feature. | `docs/BORROWING.md` |
| `open-agent-builder-main/` | Closest analog to the Territory, but **Next.js**; Doc 03 mandates **Vite**. Harvested patterns, didn't vendor. | Patterns lifted into `frontend/`; credited in `docs/BORROWING.md` |

All four were inspected before deletion. A git-LFS image in `autogen-main` 404'd on the
server during clone — irrelevant, since the folder was being removed. **4,051 files
deleted.**

## What was harvested from Open Agent Builder (the only code-level lift)

From `components/.../workflow-builder/{WorkflowBuilder,CustomNodes}.tsx` (MIT): the
state-driven custom-node styling pattern, the `animated`-edge toggle for live handoffs, and
the React Flow setup (`nodeTypes`, `useNodesState/useEdgesState`, `Background`/`Controls`,
`proOptions hideAttribution`). Rebuilt fresh in `frontend/src/canvas/` as Vite-native
components. Details in `docs/BORROWING.md`.

## What was built (the doable gate items)

- **Event schema v1 — FROZEN.** `backend/schema/events.schema.json` (draft 2020-12): the
  envelope + a discriminated union over all 29 v1 event types from Doc 04 §3.2, plus the
  provenance span-map shape (§3.3). Mirrored as Pydantic v2 in
  `backend/app/events/models.py` and TS in `frontend/src/events/types.ts`.
- **Fixture pack — 4 streams, 112 events.** `backend/fixtures/{flow_a_researcher,
  flow_b_meeting, boundary_halt, standoff_stray}.jsonl` (canonical); the frontend keeps a
  synced copy in `frontend/fixtures/`. Hand-authored, strictly-increasing `seq`,
  append-only. The frontend's fuel and the reducer's/engine's test corpus.
- **Seven wolf prompts.** `backend/prompts/{alpha,beta,scout,tracker,howler,sentinel,hunter}/v1.md`
  with role, Qwen tier, thinking mode, structured-output contract, and span-map provenance
  for Howler/Tracker.
- **Backend** (`backend/`): FastAPI app with the Doc 04 §6 API surface (commands return
  202); the Qwen client chokepoint (tiers, thinking-requires-streaming gotcha, token
  accounting); the Redis-Streams bus (XADD writer + XRANGE replay); Boundary gate
  (warn 70 / downgrade 85 / halt 100) and Stray heuristics; `hello_pack.py` seam demo;
  contract tests.
- **Gateway** (`gateway/`): Rust + Axum WS `/hunts/:id/stream?from_seq=n` — XRANGE replay
  then XREAD live-tail. Zero agent logic. Compiles clean.
- **Frontend** (`frontend/`): Vite + React 18 + TS + Tailwind tokens + Zustand + React
  Flow. The **pure reducer** (the golden rule), WolfNode state matrix, the Territory,
  dagre layout, a states gallery, design tokens.
- **DevOps:** `.gitignore`, `.gitattributes`, `.env.example`, `.pre-commit-config.yaml`
  (ruff/prettier/cargo-fmt + **gitleaks secret scan**), `.github/workflows/ci.yml`
  (backend/frontend/gateway/secret-scan jobs), `Makefile` + `scripts/dev.ps1` (Windows),
  `docker-compose.yml` (redis + postgres).
- **Governance:** `README.md` (D1/D2 confirmed), `COMPLIANCE.md` (filled from the official
  rules), `PARKING_LOT.md`, `docs/BORROWING.md`, `LICENSE` (MIT — required for the public
  OSS submission).

## Two-team, self-contained layout

After the initial bring-up, the repo was split so the **frontend** and **backend** teams
own self-contained folders and never edit the same files (no cross-team merge conflicts):

- `schema/`, `prompts/`, and the canonical `fixtures/` moved **into `backend/`** (the
  backend produces events and loads prompts).
- The frontend carries its **own** `frontend/fixtures/` copy (synced via `make
  sync-fixtures`; backend is canonical) and its own `src/events/types.ts` mirror.
- `.env.example` split into `backend/.env.example` (secrets) and `frontend/.env.example`
  (VITE_* only).
- CI split into per-team workflows: `.github/workflows/{backend,frontend,gateway,secrets}.yml`,
  each path-filtered to its folder.
- Per-service `.gitignore` files; the root `.gitignore` is repo-level only.
- `gateway/` stays its own self-contained top-level unit (backend team, Tobi).

## Verification run (this machine: Python 3.14, Node 24, pnpm 10, cargo 1.94)

| Check | Result |
|---|---|
| Schema valid (draft 2020-12) + all 112 fixture events validate | ✅ |
| `pytest tests/test_contract.py` (schema + seq + boundary invariants) | ✅ 15 passed |
| `pnpm test` (reducer snapshots over the fixture pack) | ✅ 4 passed |
| `pnpm build` (tsc + vite, code-split canvas chunk) | ✅ |
| `cargo check` (gateway) | ✅ |

> uv and docker are not installed on this machine — CI uses uv + the dev extra (which adds
> pytest-asyncio); local backend tests ran in a venv with the minimal deps.

## Notable findings surfaced for the team

1. **Open Question #5 answered:** the rules **require a public, open-source repo with a
   detectable LICENSE** — added `LICENSE` (MIT); the GitHub repo must be flipped to public.
2. **Deployment proof** per the rules is *a link to a code file* showing Alibaba Cloud
   usage, **in addition to** the screen recording the docs plan. Do both.
3. **Deadline is Pacific Time** (Jul 9, 2:00 pm PT ≈ 23:00 Lagos). Submitting Jul 8 is safe.
4. **Track name:** docs say "Agent Society"; Devpost lists named tracks — confirm the exact
   one. See `COMPLIANCE.md`.

## What remains (cannot be done here) → `docs/GATE_STATUS.md`

Alibaba account/billing/region, a real Qwen API call, Devpost team, roster names, the Qwen
voice contract, and flipping GitHub to public + branch protection. Each has a named next
action in the gate status report.
