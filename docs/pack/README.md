# The PACK build docs

The six source documents that govern this build. Drop the PDFs (or their markdown
exports) into this folder; the repo's artifacts (schema, fixtures, prompts, READMEs)
encode the decisions in them.

| # | Document | Who must read it |
|---|----------|------------------|
| 00 | Start Here | Everyone |
| 01 | PRD v0.5 | Everyone, first |
| 02 | Pages, Flows & IA | Everyone (design + frontend own it) |
| 03 | Frontend Brief | Frontend + design |
| 04 | Backend Brief | Backend (frontend reads §3 events + §6 API) |
| 05 | Prerequisites & Day Zero | Everyone (team lead enforces) |

The three rules that govern everything (Doc 00 §02):
1. The PRD is the contract.
2. The event stream is the spine.
3. Nobody writes feature code before the Day-Zero gate (see `docs/GATE_STATUS.md`).
