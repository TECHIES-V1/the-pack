# Gate status — Doc 05 §07, the ten boxes

The Day-Zero gate. **No feature code before all ten are ticked.** Each box is marked
✅ done · 🟡 built, needs a human step · 🔴 blocked (needs credentials/people).
As of **2026-06-12** (gate closes **Jun 13**) on branch `setup/day-zero`.

## Roster (Doc 05 §06 — now filled)

| Role | Person |
|---|---|
| Team lead + backend (engine, event bus, Boundary, Qwen client) | **Tobi** |
| Frontend lead (the Territory canvas, frontend repo) | **Eyitayo** |
| Frontend (Composer, Plan, Output, Tracks) | **devbyte**, **Devrobert** |
| Design (tokens, the WolfNode, the demo film) | **Abdul** |
| Docs & prompts (COMPLIANCE, wolf prompts, fixtures, write-up) | **Bezzy** |

| # | Gate box | Status | What's done / what's needed | Owner |
|---|----------|--------|------------------------------|-------|
| 1 | Alibaba Cloud proven from Nigeria (account, billing, credits, region) | 🔴 | Signup + payment card + hackathon credits + region (D6) verified from Nigeria. `backend/.env.example` + `config.py` ready for the keys. **Risk R1 — escalate to organizers today if blocked.** | **Tobi** |
| 2 | One real Qwen API call from our code | 🔴 | Qwen client chokepoint scaffolded (`backend/app/qwen/client.py`). Needs a key + the real model names from Model Studio. **Next:** a 10-line script hits a Qwen model and prints a reply. | **Tobi** |
| 3 | Rules read by all; `COMPLIANCE.md` committed; Qwen-voice disclosure noted | 🟡 | `COMPLIANCE.md` written from the **official rules** with the Qwen-voice disclosure. **Needs two sign-offs** + the team to read the rules. | **Bezzy** (draft) + 2 sign-offs |
| 4 | Devpost team formed; every member registered | 🔴 | Each member registers on the Devpost page and joins the team. | **All** |
| 5 | Repo, CI, and board live; week-1 tasks loaded | 🟡 | **Repos + CI done** — backend repo up; per-team workflows (`.github/workflows/{backend,frontend,gateway,secrets}.yml`). **Needs:** frontend repo/scaffold stood up, repo flipped **public**, the board created + week-1 tasks loaded. | **Tobi** (backend/board), **Eyitayo** (frontend) |
| 6 | D1 & D2 confirmed in the repo README | ✅ | `README.md` confirms D1 (Python brain + Rust gateway + Redis Streams) and D2 (React Flow). Note: hello-pack ships **Python-only** (FastAPI serves the stream); Rust is W2/W3. | — |
| 7 | Event schema v1 frozen; fixture pack committed | ✅ | `backend/schema/events.schema.json` (29 event types) + `backend/fixtures/` (4 streams, 112 events; synced copy in `frontend/fixtures/`). All validate in CI. | Tobi / Bezzy |
| 8 | Design tokens & WolfNode direction approved | 🟡 | Tokens (`frontend/src/styles/tokens.css` + Tailwind) and the WolfNode state matrix + states gallery are built. **Needs design-lead approval** of the direction. | **Abdul** |
| 9 | Roster filled; every TBD replaced with a name | ✅ | Filled — see the roster table above (6 people across lead/backend, frontend, design, docs). | — |
| 10 | Qwen voice model access confirmed; contract may be in flight | 🔴 | Keys/endpoint reachable from a script; full contract freezes **Jun 16**. Fallback: Qwen ASR behind the same Transcriber interface (D7, decision Jun 20). | **Tobi** |

## Score: 3 ✅ · 3 🟡 · 4 🔴

The four 🔴 boxes need **credentials or people**. The three 🟡 boxes are built and just need
a **human sign-off or an external account** (compliance sign-offs, design approval, frontend
repo + board + repo→public).

## The critical path to clearing the gate (by Jun 13)

1. **Box 1 — Tobi, first:** prove Alibaba Cloud works from Nigeria (billing + credits +
   region). If blocked, escalate to organizers via Discord + email **today** and test an
   alternate card/entity in parallel. Boxes 2, 10, and hello-pack all wait on this.
2. **Box 2 — Tobi:** once the key exists, run the 10-line Qwen call (token counts flowing).
3. **Box 5:** Eyitayo stands up the frontend repo; Tobi flips repos **public** + creates the
   board and loads week-1 tasks.
4. **Box 3 (Bezzy → two sign-offs)** and **Box 8 (Abdul approves the direction)**.
5. **Box 4:** everyone registers on Devpost and joins the team.
6. **Box 10** tracks to the Jun 16 voice-contract freeze.

## Already cleared by this setup (no longer blocking)

- Event schema + fixtures (box 7) — the spine the whole frontend builds against.
- D1/D2 in the README (box 6).
- Roster filled (box 9).
- Repos + CI half of box 5 (backend repo + per-team workflows).
- Tokens/WolfNode built (box 8 — pending Abdul's approval).
- `COMPLIANCE.md` drafted (box 3 — pending two sign-offs).
- `LICENSE` added — required for the public OSS submission (see `COMPLIANCE.md` §4).
