# Gate status — Doc 05 §07, the ten boxes

The Day-Zero gate. **No feature code before all ten are ticked.** This report marks each as
✅ done here · 🟡 partially done (needs a human step) · 🔴 blocked (needs credentials/people).
As of **2026-06-13** on branch `setup/day-zero`.

| # | Gate box | Status | What's done / what's needed | Owner |
|---|----------|--------|------------------------------|-------|
| 1 | Alibaba Cloud proven from Nigeria (account, billing, credits, region) | 🔴 | Needs signup + payment card + hackathon credits + region (D6) verified from Nigeria. `.env.example` + `config.py` are ready for the keys. **This is risk R1 — escalate to organizers if blocked.** | Backend 2 / infra (TBD) |
| 2 | One real Qwen API call from our code | 🔴 | The Qwen client chokepoint is scaffolded (`backend/app/qwen/client.py`). Needs a key + the real model names from Model Studio. **Next:** a 10-line script hits a Qwen model and prints a reply. | Backend lead (Tobi) |
| 3 | Rules read by all; `COMPLIANCE.md` committed; Qwen-voice disclosure noted | 🟡 | `COMPLIANCE.md` written from the **official rules**, with the Qwen-voice pre-existing-service disclosure. **Needs two sign-offs** + the team to read the rules. | Team lead (TBD) |
| 4 | Devpost team formed; every member registered | 🔴 | External. Each member registers on the Devpost page and joins the team. | All |
| 5 | Repo, CI, and board live; week-1 tasks loaded | 🟡 | **Repo + CI done** (`.github/workflows/ci.yml`: backend/frontend/gateway/secret-scan). Board is external (task tracker) — **needs setup + week-1 tasks loaded.** Repo must be flipped **public**. | Backend 2 / infra (TBD) |
| 6 | D1 & D2 confirmed in the repo README | ✅ | `README.md` confirms D1 (Python brain + Rust gateway + Redis Streams) and D2 (React Flow). | — |
| 7 | Event schema v1 frozen; fixture pack committed | ✅ | `schema/events.schema.json` (29 event types) + `fixtures/` (4 streams, 112 events). All validate in CI. | — |
| 8 | Design tokens & WolfNode direction approved | 🟡 | Tokens (`frontend/src/styles/tokens.css` + Tailwind) and the WolfNode state matrix + states gallery are built. **Needs design-lead approval** of the direction. | Design (TBD) |
| 9 | Roster filled; every TBD replaced with a name | 🔴 | Human. Only Tobi (backend lead) is named. Fill the §06 table before the gate (risk R7). | Team lead (TBD) |
| 10 | Qwen voice model access confirmed; contract may be in flight | 🔴 | Keys/endpoint reachable from a script; full contract freezes **Jun 16**. Fallback: Qwen ASR behind the same Transcriber interface (D7, decision Jun 20). | Backend lead (Tobi) |

## Score: 2 ✅ · 3 🟡 · 5 🔴

The five 🔴 boxes all need **credentials or people** — none can be done from this machine.
The three 🟡 boxes are built but need a **human sign-off or an external account** (board,
design approval, compliance sign-offs, repo→public).

## The critical path to clearing the gate

1. **R1 first (box 1):** prove Alibaba Cloud works from Nigeria — billing + credits +
   region. If it fails by **Jun 11** (already past), escalate to organizers via Discord +
   email *today*, and test an alternate card/entity in parallel. Everything downstream
   (boxes 2, 10, deployment) waits on this.
2. **Box 2** follows immediately once the key exists: run the 10-line Qwen call.
3. **Fill the roster (box 9)** — it blocks per-person task assignment and the board (box 5).
4. **Flip the repo public + load the board** (box 5), get **compliance sign-offs** (box 3)
   and **design approval** (box 8).
5. **Box 10** tracks to the Jun 16 voice-contract freeze.

## Already cleared by this setup (no longer blocking)

- The event schema + fixtures (box 7) — the spine the whole frontend builds against.
- D1/D2 in the README (box 6).
- The repo skeleton + CI half of box 5.
- The tokens/WolfNode half of box 8 (pending approval).
- The `COMPLIANCE.md` half of box 3 (pending sign-offs).
- `LICENSE` added (required for the public OSS submission — see `COMPLIANCE.md` §4).
