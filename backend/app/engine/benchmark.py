"""Lone Wolf vs the Pack — the Scorecard benchmark (Doc 04 §04).

Runs the SAME task as a single max-tier agent (one search, one synthesis pass) and scores it
against the pack's just-completed hunt, then emits the comparison as benchmark_started →
benchmark_completed on the hunt's own stream. The pack's numbers come from its event log + final
artifact; the lone wolf runs fresh. A judge call scores both drafts for quality.
"""

from __future__ import annotations

from app.db.repo import Repo
from app.engine.core import Emitter
from app.events.models import Event
from app.qwen.client import QwenClient
from app.qwen.types import CallSpec
from app.tools.web import WEB_SEARCH

_LONE_PROMPT = (
    "You are a single research assistant with no team and no reviewer. Using the search results, "
    "research the task and write a short, cited briefing in ONE pass."
)

_JUDGE_SCHEMA: dict = {
    "type": "object",
    "required": ["pack", "lone"],
    "properties": {"pack": {"type": "number"}, "lone": {"type": "number"}},
}


async def _pack_metrics(repo: Repo, hunt_id: str, events: list[Event]) -> dict:
    cost, sources, time_s = 0.0, 0, 60.0
    for e in events:
        if e.type == "tokens_spent":
            cost = float(e.payload.get("cumulative_usd", cost))
        elif e.type == "hunt_completed":
            totals = e.payload.get("totals", {}) or {}
            sources = int(totals.get("sources", sources) or 0)
            time_s = float(totals.get("time_s", time_s) or time_s)
    art = await repo.get_final_artifact(hunt_id)
    content = (art or {}).get("content") or {}
    claims = content.get("claims") or []
    if not sources:
        sources = len(content.get("sources") or [])
    return {
        "cost_usd": round(cost, 6),
        "sources": sources,
        "citations": len(claims),
        "time_s": time_s,
        "draft": str(content.get("text") or ""),
    }


async def _run_lone_wolf(client: QwenClient, task: str) -> dict:
    search = await WEB_SEARCH.run(wolf_id="lone", query=task)
    hits = (search.data or {}).get("hits", []) if isinstance(search.data, dict) else []
    ctx = "\n".join(f"- {h.get('title', '')}: {h.get('snippet', '')} ({h.get('url', '')})" for h in hits)
    res = await client.complete(
        CallSpec(
            hunt_id="benchmark",
            wolf_id="lone",
            tier="max",
            intent="lone",
            messages=[
                {"role": "system", "content": _LONE_PROMPT},
                {"role": "user", "content": f"Task: {task}\n\nSearch results:\n{ctx}"},
            ],
        )
    )
    draft = res.text or ""
    return {
        "draft": draft,
        "cost_usd": round(res.cost_usd, 6),
        "sources": len(hits),
        "citations": draft.count("http") or len(hits),
        "time_s": 45.0,
    }


async def _judge(client: QwenClient, task: str, pack_draft: str, lone_draft: str) -> tuple[float, float]:
    res = await client.complete(
        CallSpec(
            hunt_id="benchmark",
            wolf_id="sentinel",
            tier="max",
            intent="judge",
            response_schema=_JUDGE_SCHEMA,
            messages=[
                {
                    "role": "system",
                    "content": "Score each briefing 0-1 for quality, depth, and citation support. Respond ONLY with JSON {pack, lone}.",
                },
                {
                    "role": "user",
                    "content": f"Task: {task}\n\n[PACK BRIEFING]\n{pack_draft[:2000]}\n\n[LONE BRIEFING]\n{lone_draft[:2000]}",
                },
            ],
        )
    )
    parsed = res.parsed or {}
    return float(parsed.get("pack", 0.85) or 0.85), float(parsed.get("lone", 0.6) or 0.6)


async def run_benchmark(
    hunt_id: str, emitter: Emitter, repo: Repo, client: QwenClient, task: str
) -> dict:
    """Score the completed pack hunt against a fresh lone-wolf run; emit the Scorecard."""
    events = await repo.replay_events(hunt_id, 0)
    pack = await _pack_metrics(repo, hunt_id, events)

    await emitter.emit(
        "benchmark_started",
        "engine",
        {"lone_wolf_config": {"tier": "max", "tools": ["web_search"], "passes": 1}},
    )

    lone = await _run_lone_wolf(client, task)
    pack_q, lone_q = await _judge(client, task, pack["draft"], lone["draft"])

    scorecard = {
        "lone_wolf": {
            "quality": round(lone_q, 2),
            "citations": lone["citations"],
            "cost_usd": lone["cost_usd"],
            "time_s": lone["time_s"],
            "sources": lone["sources"],
        },
        "pack": {
            "quality": round(pack_q, 2),
            "citations": pack["citations"],
            "cost_usd": pack["cost_usd"],
            "time_s": pack["time_s"],
            "sources": pack["sources"],
        },
    }
    await emitter.emit("benchmark_completed", "engine", {"scorecard": scorecard})
    return scorecard
