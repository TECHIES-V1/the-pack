"""The Supervisor — Alpha's loop, one async task per hunt (Doc 04 §04).

This drives a real hunt end to end and narrates every step as a typed event through the one
Emitter. It follows Magentic-One's spirit — a Task Ledger (the plan) and a Progress Ledger
(what's done, who's next) — and today runs flow_a's `parallel_then_merge` shape: Beta plans,
the user approves, the pack spawns, Scouts range in parallel, Tracker merges, a Hold surfaces
a conflict for the human, Howler drafts, the hunt returns a final artifact.

Two human gates arrive as commands on the per-hunt queue (REST returns 202; the truth lands
here on the stream): `approve_plan` after the plan, `resolve_hold` after a Hold. `stop`
ends the hunt at any await.

THE BOUNDARY IS A GATE, NOT A GRAPH: every model dispatch goes through `_dispatch`, which
checks PROJECTED spend BEFORE the call — warn at 70%, downgrade tier at 85%, halt + checkpoint
at 100% (no call). That pre-dispatch enforcement is the whole point.

The model brain is swappable: offline it's FakeQwen, live it's Qwen. Nothing in this file
changes when the key lands. Real per-wolf prompting (replacing the canned plan/outputs) is
the next layer; the event shape it produces is already final.
"""

from __future__ import annotations

import asyncio
import contextlib

from app.db.repo import Repo
from app.engine.boundary import Boundary, Verdict
from app.engine.core import Emitter
from app.engine.ids import new_artifact_id, new_checkpoint_id, new_hold_id
from app.engine.stray import StrayDetector
from app.engine.wolves import Wolf
from app.prompts import load_prompt
from app.qwen import pricing
from app.qwen.client import QwenClient
from app.qwen.types import CompletionResult
from app.tools.web import WEB_SEARCH

# The roster for flow_a. Tiers/thinking are explicit (the canonical fixture values) rather
# than parsed from prompt frontmatter, which carries prose like "plus / max".
_ROSTER: list[tuple[str, str, str, bool]] = [
    ("alpha", "alpha", "max", True),
    ("beta", "beta", "plus", True),
    ("scout-1", "scout", "flash", False),
    ("scout-2", "scout", "flash", False),
    ("scout-3", "scout", "flash", False),
    ("tracker", "tracker", "plus", True),
    ("sentinel", "sentinel", "max", True),
    ("howler", "howler", "plus", False),
]

_SCOUTS: list[tuple[str, str, str]] = [
    ("scout-1", "Searching for the market leaders", "BNPL Nigeria market leaders 2025"),
    ("scout-2", "Searching for the regulator's guidance", "CBN buy now pay later guidance"),
    ("scout-3", "Searching for adoption numbers", "BNPL Nigeria active users millions"),
]

_PLAN = {
    "steps": [
        {
            "step_id": "s1",
            "summary": "Range for market players",
            "wolves": ["scout-1", "scout-2", "scout-3"],
        },
        {"step_id": "s2", "summary": "Cross-reference and extract claims", "wolves": ["tracker"]},
        {"step_id": "s3", "summary": "Draft the briefing with citations", "wolves": ["howler"]},
    ],
    "wolves": ["scout-1", "scout-2", "scout-3", "tracker", "sentinel", "howler"],
    "pattern": "parallel_then_merge",
    "assumptions": ["consumer scope", "recent window", "briefing doc"],
    "est_cost": 0.60,
    "est_time": 210,
}


# What each dispatch asks its wolf to do. The role's prompt file is the system message; this
# is the task-specific instruction appended to the user message.
_INTENT_INSTRUCTIONS: dict[str, str] = {
    "search": "Search for and report the key findings on this, each with its source.",
    "merge": "Cross-reference the findings, resolve any conflicts, and extract the key claims.",
    "draft": "Write the final briefing in clear prose, citing the sources inline.",
}


class StopHunt(Exception):
    """The user stopped the hunt."""


class BoundaryHalt(Exception):
    """The Boundary halted the hunt before the next spend."""


class Supervisor:
    def __init__(
        self,
        hunt_id: str,
        emitter: Emitter,
        repo: Repo,
        client: QwenClient,
        commands: asyncio.Queue,
        *,
        source: str = "typed",
        raw_input: str = "",
    ) -> None:
        self._hunt_id = hunt_id
        self._emitter = emitter
        self._repo = repo
        self._client = client
        self._commands = commands
        self._source = source
        self._raw_input = raw_input
        self._wolves: dict[str, Wolf] = {}
        self._boundary = Boundary(boundary_usd=0.0)
        self._stray = StrayDetector()
        self._warned = False
        # Real model output threaded between wolves (scouts → tracker → howler). Empty in
        # offline mode (FakeQwen returns canned text); populated for real with a live key.
        self._findings: list[str] = []
        self._tracker_text: str = ""

    # --- the run -----------------------------------------------------------------------

    async def run(self) -> None:
        try:
            await self._emit(
                "hunt_created",
                "user",
                {"source": self._source, "raw_input_ref": f"art_{self._hunt_id}_raw"},
            )
            await self._repo.set_hunt_state(self._hunt_id, "planning")

            await self._propose_plan()
            approve = await self._await_command("approve_plan")
            await self._approve(approve)

            await self._spawn_roster()
            await self._run_scouts()
            await self._merge_and_hold()
            await self._draft_and_finish()
        except StopHunt:
            with contextlib.suppress(Exception):
                await self._emit("hunt_stopped", "user", {"by": "user"})
                await self._repo.set_hunt_state(self._hunt_id, "stopped_by_user")
        except BoundaryHalt:
            await self._repo.set_hunt_state(self._hunt_id, "halted_boundary")
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - a hunt must fail as an event, not a crash
            with contextlib.suppress(Exception):
                await self._emit(
                    "hunt_failed",
                    "engine",
                    {"reason_plain_english": f"The hunt hit an error: {exc}"},
                )
                await self._repo.set_hunt_state(self._hunt_id, "failed")

    # --- phases ------------------------------------------------------------------------

    async def _propose_plan(self) -> None:
        await self._emit("plan_proposed", "beta", dict(_PLAN))
        await self._repo.set_hunt_state(self._hunt_id, "plan_ready")

    async def _approve(self, cmd: dict) -> None:
        approved = float(cmd.get("boundary_usd", 1.0))
        from app.config import settings

        # First-hunt silent cap: never spend past the cap, whatever was approved.
        effective = min(approved, settings.first_hunt_cap_usd)
        self._boundary = Boundary(boundary_usd=effective)
        await self._repo.set_boundary(self._hunt_id, effective)
        await self._emit(
            "plan_approved",
            "user",
            {"mode": cmd.get("mode", "on_signal"), "boundary_usd": effective},
        )
        await self._repo.set_hunt_state(self._hunt_id, "hunting")

    async def _spawn_roster(self) -> None:
        for wolf_id, role, tier, thinking in _ROSTER:
            version = load_prompt(role).version
            self._wolves[wolf_id] = Wolf(
                hunt_id=self._hunt_id,
                wolf_id=wolf_id,
                role=role,
                tier=tier,
                thinking=thinking,
                prompt_version=version,
                client=self._client,
            )
            await self._emit(
                "wolf_spawned",
                "engine",
                {
                    "wolf_id": wolf_id,
                    "role": role,
                    "model_tier": tier,
                    "thinking": thinking,
                    "prompt_version": version,
                },
            )

    async def _run_scouts(self) -> None:
        # parallel_then_merge, phased so the canvas shows the pack moving together.
        for wolf_id, summary, _q in _SCOUTS:
            await self._emit(
                "step_started", wolf_id, {"step_id": "s1", "wolf_id": wolf_id, "summary": summary}
            )
        for wolf_id, _summary, query in _SCOUTS:
            await self._scout_search(self._wolves[wolf_id], query)
        for wolf_id, _summary, query in _SCOUTS:
            res = await self._dispatch(
                self._wolves[wolf_id], "search", context=f"Your angle: {query}"
            )
            self._findings.append(f"{wolf_id}: {res.text}")
        for wolf_id, _summary, _q in _SCOUTS:
            await self._emit(
                "step_completed",
                wolf_id,
                {
                    "step_id": "s1",
                    "wolf_id": wolf_id,
                    "output_ref": f"art_{wolf_id}_out",
                    "confidence": 0.82,
                },
            )
        for wolf_id, _summary, _q in _SCOUTS:
            await self._emit(
                "message_passed",
                wolf_id,
                {
                    "from_wolf": wolf_id,
                    "to_wolf": "tracker",
                    "intent": "handoff_findings",
                    "summary": "findings with sources",
                    "ref": f"art_{wolf_id}_out",
                },
            )

    async def _merge_and_hold(self) -> None:
        await self._emit(
            "step_started",
            "tracker",
            {
                "step_id": "s2",
                "wolf_id": "tracker",
                "summary": "Cross-referencing the scouts' findings",
            },
        )

        hold_id = new_hold_id()
        await self._emit(
            "hold_opened",
            "alpha",
            {
                "hold_id": hold_id,
                "question": "Conflicting user numbers, 2M vs 3.4M. Use the regulator's figure?",
                "context_ref": "art_scout-3_out",
                "options": [
                    "Use the regulator figure (2M)",
                    "Use the higher figure (3.4M)",
                    "Report the range",
                ],
                "recommended": "Use the regulator figure (2M)",
            },
        )
        await self._repo.set_hunt_state(self._hunt_id, "holding")

        await self._await_command("resolve_hold")
        await self._emit(
            "hold_resolved",
            "user",
            {
                "hold_id": hold_id,
                "resolution": "Use the regulator figure (2M)",
                "edited_text": None,
            },
        )
        await self._repo.set_hunt_state(self._hunt_id, "hunting")

        tracker_res = await self._dispatch(
            self._wolves["tracker"], "merge", context="\n".join(self._findings)
        )
        self._tracker_text = tracker_res.text
        await self._emit(
            "step_completed",
            "tracker",
            {
                "step_id": "s2",
                "wolf_id": "tracker",
                "output_ref": "art_tracker_out",
                "confidence": 0.9,
            },
        )

    async def _draft_and_finish(self) -> None:
        await self._emit(
            "step_started",
            "howler",
            {
                "step_id": "s3",
                "wolf_id": "howler",
                "summary": "Drafting the briefing with citations",
            },
        )
        draft = await self._dispatch(self._wolves["howler"], "draft", context=self._tracker_text)
        await self._emit(
            "step_completed",
            "howler",
            {
                "step_id": "s3",
                "wolf_id": "howler",
                "output_ref": "art_howler_draft",
                "confidence": 0.86,
            },
        )

        artifact_id = new_artifact_id()
        await self._repo.save_artifact(
            artifact_id, self._hunt_id, "final", "howler", {"text": draft.text}
        )
        await self._emit(
            "artifact_created",
            "howler",
            {
                "artifact_id": artifact_id,
                "kind": "final",
                "produced_by": "howler",
                "provenance_span_map_ref": None,
            },
        )

        totals = {
            "cost_usd": round(self._boundary.cumulative_usd, 6),
            "time_s": _PLAN["est_time"],
            "sources": 9,
            "wolves": len(self._wolves),
        }
        await self._emit(
            "hunt_completed", "engine", {"final_artifact_id": artifact_id, "totals": totals}
        )
        await self._repo.set_hunt_state(self._hunt_id, "returned")

    # --- dispatch (the gate) + tools ---------------------------------------------------

    def _messages(self, wolf: Wolf, intent: str, context: str) -> list[dict]:
        """Build the real prompt: the role's prompt file is the system message; the task +
        intent instruction + any upstream context is the user message. (Ignored by FakeQwen.)"""
        system = load_prompt(wolf.role).body
        user = f"Task: {self._raw_input or 'Research the topic and produce a briefing.'}\n\n"
        user += _INTENT_INSTRUCTIONS.get(intent, intent)
        if context:
            user += f"\n\nContext:\n{context}"
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

    async def _dispatch(self, wolf: Wolf, intent: str, context: str = "") -> CompletionResult:
        """The one path a model call takes. Gate BEFORE the call, account AFTER."""
        est = pricing.estimate(wolf.tier)
        verdict = self._boundary.check(est)

        if verdict is Verdict.HALT:
            await self._halt()
            raise BoundaryHalt()
        if verdict is Verdict.DOWNGRADE and wolf.tier != "flash":
            from_tier, thinking_off = wolf.tier, wolf.thinking
            wolf.tier, wolf.thinking = "flash", False
            await self._emit(
                "boundary_downgrade",
                "engine",
                {
                    "wolf_id": wolf.wolf_id,
                    "from_tier": from_tier,
                    "to_tier": "flash",
                    "thinking_off": thinking_off,
                },
            )
        elif verdict is Verdict.WARN and not self._warned:
            self._warned = True
            await self._emit(
                "boundary_warning",
                "engine",
                {
                    "pct": round(self._boundary.projected_pct(est), 2),
                    "cumulative_usd": round(self._boundary.cumulative_usd, 6),
                },
            )

        result = await wolf.think(intent, messages=self._messages(wolf, intent, context))
        self._boundary.cumulative_usd += result.cost_usd
        await self._emit(
            "tokens_spent",
            wolf.wolf_id,
            {
                "wolf_id": wolf.wolf_id,
                "model": result.model,
                "in_tokens": result.in_tokens,
                "out_tokens": result.out_tokens,
                "cost_usd": round(result.cost_usd, 6),
                "cumulative_usd": round(self._boundary.cumulative_usd, 6),
            },
        )
        return result

    async def _scout_search(self, wolf: Wolf, query: str) -> None:
        await self._emit(
            "tool_called",
            wolf.wolf_id,
            {"wolf_id": wolf.wolf_id, "tool": "web_search", "args_summary": query},
        )
        res = await WEB_SEARCH.run(wolf_id=wolf.wolf_id, query=query)
        self._stray.record_tool_result(wolf.wolf_id, res.ok)
        await self._emit(
            "tool_result",
            wolf.wolf_id,
            {
                "wolf_id": wolf.wolf_id,
                "tool": "web_search",
                "ok": res.ok,
                "result_ref": res.result_ref,
                "latency_ms": res.latency_ms,
            },
        )

    async def _halt(self) -> None:
        ckpt = new_checkpoint_id()
        await self._repo.save_checkpoint(
            ckpt,
            self._hunt_id,
            self._emitter.last_seq,
            {"cumulative_usd": self._boundary.cumulative_usd},
        )
        await self._emit(
            "boundary_halt",
            "engine",
            {
                "checkpoint_id": ckpt,
                "spend_breakdown": {"cumulative_usd": round(self._boundary.cumulative_usd, 6)},
                "resume_options": ["raise_boundary", "stop"],
            },
        )

    # --- helpers -----------------------------------------------------------------------

    async def _emit(self, type: str, actor: str, payload: dict) -> None:
        await self._emitter.emit(type, actor, payload)  # type: ignore[arg-type]

    async def _await_command(self, expected: str) -> dict:
        """Block until the expected command arrives. `stop` ends the hunt from any await."""
        while True:
            cmd = await self._commands.get()
            ctype = cmd.get("type")
            if ctype == "stop":
                raise StopHunt()
            if ctype == expected:
                return cmd
            # Unexpected command for this phase (e.g. a mid-plan input) — ignore for now (NEXT).
