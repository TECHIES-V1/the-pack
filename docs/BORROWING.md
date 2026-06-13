# Borrowing map — what we adapt, and from where

We design almost none of the orchestration from scratch (Doc 04 §4A). Each piece is
**adapted** from a proven, permissively licensed source — we study the pattern and perfect
it into our voice and our event model. **We do not vendor these repos.** A public, judged,
prize-money submission cannot carry provenance risk, so this file is the audit trail.

The four reference repos that were dumped into this repo's first commit
(`autogen-main`, `langgraph-main`, `letta-main`, `open-agent-builder-main`) were **removed**
during setup — see `docs/SETUP_REPORT.md`. Study them from their upstreams below.

| Pack piece | Borrow from | License | Upstream |
|---|---|---|---|
| The Alpha loop (dual ledgers: Task + Progress) | Microsoft Magentic-One / AutoGen | MIT + Apache-2.0 (code MIT; docs CC-BY-4.0) | https://github.com/microsoft/autogen |
| Shared state, graph, checkpoints, Holds | LangGraph state-graph model | MIT | https://github.com/langchain-ai/langgraph |
| Qwen tool-calling conventions | Qwen-Agent (Alibaba's own) | Apache-2.0 | https://github.com/QwenLM/Qwen-Agent |
| Wolf-to-wolf handoff primitive | OpenAI Agents SDK handoff | MIT | https://github.com/openai/openai-agents-python |
| Message-bus pattern | MetaGPT publish-subscribe pool | MIT (study the pattern) | https://github.com/geekan/MetaGPT |
| The Elder (tiered memory, P1) | Letta / MemGPT | Apache-2.0 | https://github.com/letta-ai/letta |
| Standoffs (debate + reviewer) | Multi-agent debate (Du et al.) | public paper | https://arxiv.org/abs/2305.14325 |
| The event spine (event sourcing + CQRS) | Anthropic orchestrator-worker essay | public | https://www.anthropic.com/engineering/building-effective-agents |
| Designing against failure | MAST taxonomy (Cemri et al. 2025) | public paper | https://arxiv.org/abs/2503.13657 |
| **Canvas wiring (the Territory)** | **Firecrawl Open Agent Builder** | **MIT** | https://github.com/mendableai/open-agent-builder |

## What we lifted from Open Agent Builder (the only code-level harvest)

OAB is a Next.js app; Doc 03 mandates **Vite**, so we did not fork it. We lifted these
*patterns* into `frontend/src/canvas/` and rebuilt the look as our own:

- **State-driven custom-node styling** — border/background/outline/shadow chosen from the
  node's `data` (running/selected/status). See OAB `CustomNodes.tsx` → our `WolfNode.tsx`.
- **`animated` edge toggling** — an edge flips `animated: true` + a heavier stroke when the
  handoff is live. See OAB `WorkflowBuilder.tsx` edge effect → our `Territory.tsx` EdgeFlow.
- **The React Flow setup** — `nodeTypes`, `useNodesState/useEdgesState`, `onConnect`,
  `Background`/`Controls`, `proOptions={{ hideAttribution: true }}`.
- React Flow's own MIT examples (animated edges, custom nodes) are the second reference.

React Flow core is MIT and needs no paid tier for commercial use (Doc 03 §3).

## The rule

Screens speak Pack; code speaks plain engineering. No leaked or non-permissive material
goes anywhere near this codebase.
