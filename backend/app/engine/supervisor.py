"""The Supervisor — Alpha's loop, one async task per hunt (Doc 04 §04).

This drives a REAL hunt end to end and narrates every step as a typed event through the one
Emitter. Beta plans from the actual task (structured output), the user approves, the pack
spawns, and the chosen **strategy** drives the research: Scouts run real web searches on
task-derived angles, Tracker merges the findings, a Hold surfaces only on a genuine conflict,
Sentinel can challenge a weak claim in a Standoff, and Howler drafts the cited brief.

The Supervisor IS the `Engine` (app/engine/strategies): it owns the shared primitives
(spawn, scout, merge, hold, critique, standoff, draft, the boundary-gated `_dispatch`) and
hands control to the strategy's `execute(self)`. Strategies differ only in how they sequence
those primitives — orchestrate (dynamic), deep_dive (iterative), critique (rigorous).

Two human gates arrive as commands on the per-hunt queue (REST returns 202; the truth lands
here on the stream): `approve_plan` after the plan, `resolve_hold` on a Hold. `stop` ends the
hunt at any await.

THE BOUNDARY IS A GATE, NOT A GRAPH: every model dispatch goes through `_dispatch`, which
checks PROJECTED spend BEFORE the call — warn at 70%, downgrade tier at 85%, halt + checkpoint
at 100% (no call). That pre-dispatch enforcement is the whole point.

The model brain is swappable: offline it's FakeQwen (deterministic, topic-aware structured
output), live it's Qwen. Nothing in this file changes when the key lands.
"""

from __future__ import annotations

import asyncio
import contextlib
import re

from app.db.repo import Repo
from app.engine.boundary import Boundary, Verdict
from app.engine.core import Emitter
from app.engine.ids import new_artifact_id, new_checkpoint_id, new_hold_id, new_standoff_id
from app.engine.strategies import Conflict, CritiqueResult, Finding, Merged, get_strategy
from app.engine.strategies.base import (
    CRITIQUE_SCHEMA,
    FINDINGS_SCHEMA,
    GAPS_SCHEMA,
    MERGE_SCHEMA,
    PLAN_SCHEMA,
)
from app.engine.stray import StrayDetector
from app.engine.wolves import Wolf
from app.prompts import load_prompt
from app.qwen import pricing
from app.qwen.client import OnDelta, QwenClient
from app.qwen.types import CompletionResult
from app.tools.web import WEB_FETCH, WEB_SEARCH

# v2: Alpha builds the team per task. Each role's tier/thinking/default per-wolf budget cap is fixed
# here (parsing prose from the prompt frontmatter is unreliable); Beta proposes only the SHAPE — how
# many scouts, mainly. Alpha + Beta lead every hunt; the support roles always join; scouts vary.
_ROLE_SPEC: dict[str, tuple[str, bool, float]] = {
    # role:    (model_tier, thinking, default per-wolf budget cap USD)
    "alpha": ("max", True, 0.15),
    "beta": ("plus", True, 0.10),
    "scout": ("flash", False, 0.10),
    "tracker": ("plus", True, 0.15),
    "sentinel": ("max", True, 0.20),
    "howler": ("plus", False, 0.15),
    "elder": ("flash", False, 0.05),  # v2 memory agent — wired in Phase 2.6
}

# Canvas order: leads → the variable scouts → support. (Elder joins in 2.6 once it has a prompt.)
_LEAD_ROLES = ["alpha", "beta"]
_SUPPORT_ROLES = ["tracker", "sentinel", "howler"]
_DEFAULT_SCOUTS = 3
_MIN_SCOUTS = 1
_MAX_SCOUTS = 5


def _wolf_ids(role: str, count: int) -> list[str]:
    """Mint ids for a role. Scouts are always suffixed (scout-1..N, the canonical convention); a
    singleton of any other role keeps its bare role name; clones get -1..-N."""
    if role == "scout":
        return [f"scout-{i + 1}" for i in range(max(1, count))]
    if count <= 1:
        return [role]
    return [f"{role}-{i + 1}" for i in range(count)]


def _build_team(parsed: dict) -> list[dict]:
    """Beta proposes the SHAPE (mainly scout count); expand to the canonical team — each role's
    tier/thinking/budget filled from _ROLE_SPEC. Alpha + Beta always lead (×1); scouts vary 1..5;
    support roles default to 1 but honor a higher requested count (a cloned tracker, 1..3)."""
    proposed = {
        str(e.get("role")): int(e.get("count") or 0)
        for e in (parsed.get("team") or [])
        if isinstance(e, dict)
    }
    team: list[dict] = []
    for role in [*_LEAD_ROLES, "scout", *_SUPPORT_ROLES]:
        tier, thinking, budget = _ROLE_SPEC[role]
        if role in _LEAD_ROLES:
            count = 1
        elif role == "scout":
            want = proposed.get("scout", _DEFAULT_SCOUTS) or _DEFAULT_SCOUTS
            count = max(_MIN_SCOUTS, min(_MAX_SCOUTS, want))
        else:
            count = max(1, min(3, proposed.get(role, 1) or 1))
        team.append({
            "role": role,
            "count": count,
            "tier": tier,
            "thinking": thinking,
            "budget_usd": round(budget, 4),
        })
    return team


def _roster_from_team(team: list[dict]) -> list[tuple[str, str, str, bool, float]]:
    """Flatten the team spec into (wolf_id, role, tier, thinking, budget_usd) rows to spawn."""
    rows: list[tuple[str, str, str, bool, float]] = []
    for entry in team:
        role = str(entry.get("role"))
        if role not in _ROLE_SPEC:
            continue
        count = max(1, int(entry.get("count") or 1))
        tier = str(entry.get("tier") or _ROLE_SPEC[role][0])
        thinking = bool(entry.get("thinking", _ROLE_SPEC[role][1]))
        budget = float(entry.get("budget_usd") or _ROLE_SPEC[role][2])
        for wid in _wolf_ids(role, count):
            rows.append((wid, role, tier, thinking, budget))
    return rows

# Search APIs (Tavily/Exa/Serp/…) take natural language, not Google dorks — a query like
# "site:spacex.com OR site:nsf.org past week" returns nothing because the operators are read as
# literal text. Degrade any dork to plain keywords so the fan-out actually finds sources; recency is
# the engines' job, not a phrase in the query.
_DORK_RE = re.compile(
    r"""(?ix)
      \b(?:site|filetype|intitle|inurl|intext)\s*:\s*\S+   # site:foo.com, filetype:pdf, …
    | \b(?:OR|AND)\b                                        # boolean operators
    | \b(?:past|last)\s+(?:\d+\s+)?(?:day|week|month|year)s?\b   # recency phrases
    | ["']                                                  # stray quotes
    """,
)


def _plain_query(query: str) -> str:
    """Strip search operators and recency phrases down to plain keywords. Falls back to the original
    if stripping empties it (better a dork than nothing)."""
    cleaned = _DORK_RE.sub(" ", query)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -|")
    return cleaned or query.strip()

# What each dispatch asks its wolf to do. The role's prompt file is the system message; this is
# the task-specific instruction appended to the user message.
_INTENT_INSTRUCTIONS: dict[str, str] = {
    "plan": (
        "Break this into a research plan and size the pack to the task. Respond with ONLY JSON: a "
        "one-line `summary`; a `team` array of {role, count} — pick 1-5 `scout`s (more for a broad "
        "topic, fewer for a narrow one); a `queries` array with ONE plain-keyword search query per "
        "scout (match the scout count); an `assumptions` array; and numeric `est_cost` (USD) and "
        "`est_time` (seconds). Queries: plain keywords only — NO operators (site:, OR/AND, quotes, "
        "'past week'); the engine handles recency."
    ),
    "search": (
        "Using ONLY the search results provided, summarize the key findings for your angle. "
        "Respond with ONLY JSON: `summary` (string) and `confidence` (0-1). Never invent a source."
    ),
    "merge": (
        "Cross-reference the scouts' findings. Respond with ONLY JSON: a `summary`, a `claims` "
        "array, and `conflict` — a genuine disagreement as {question, options, recommended} — or "
        "null when the sources agree. Only raise a conflict that is really there."
    ),
    "critique": (
        "Check that every claim carries a real source and is supported. Respond with ONLY JSON: "
        "`ok` (boolean) and `issues` (array of {claim, problem}). Be strict but fair."
    ),
    "gaps": (
        "Name what is still missing to answer the task well. Respond with ONLY JSON: `gaps` "
        "(array of focused follow-up search queries). Empty array if nothing is missing."
    ),
    "draft": (
        "Write the final briefing in clear prose, citing the sources inline. Build on the merged "
        "claims and honor the resolved decision if one is given."
    ),
    "standoff_challenge": (
        "You are challenging a weak claim. In one or two sentences, state plainly why it doesn't "
        "yet stand — what evidence is missing or thin. Be specific, not rude."
    ),
    "standoff_defend": (
        "You are defending your claim against a challenge. In one or two sentences, either "
        "concede and say how you'll strengthen it, or defend it with the evidence you have."
    ),
    "standoff_judge": (
        "You are Alpha settling a standoff. In one or two sentences, make the call: keep, drop, or "
        "qualify the claim, and say why. Plain English."
    ),
}


class StopHunt(Exception):
    """The user stopped the hunt."""


class BoundaryHalt(Exception):
    """The Boundary halted the hunt before the next spend."""


class Supervisor:
    """Drives one hunt and serves as the `Engine` the chosen strategy orchestrates."""

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
        strategy: str | None = None,
    ) -> None:
        self._hunt_id = hunt_id
        self._emitter = emitter
        self._repo = repo
        self._client = client
        self._commands = commands
        self._source = source
        self._raw_input = raw_input
        self._strategy = get_strategy(strategy)
        self._wolves: dict[str, Wolf] = {}
        self._team: list[dict] = []  # v2: the per-task formation Beta proposes / the user edits
        self._wolf_budget: dict[str, float] = {}  # v2: per-wolf spend cap (gated in _dispatch, 2.4)
        self._boundary = Boundary(boundary_usd=0.0)
        self._stray = StrayDetector()
        self._warned = False
        self._plan: dict = {}
        self._queries: list[str] = []
        self._sources: list[dict] = []
        self._extra_inputs: list[str] = []  # mid-hunt inputs absorbed without a restart (A7)
        self._mode = "on_signal"  # autonomy: how tightly the Packmaster holds the leash
        from app.config import settings

        self._step_timeout: float = settings.step_timeout_s

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
            await self._open_pack()
            await self._strategy.execute(self)
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

    # --- planning + approval -----------------------------------------------------------

    async def _propose_plan(self) -> None:
        """Beta turns the real task into a plan (structured output). Pre-budget, so this call
        is NOT boundary-gated and NOT counted against the hunt's cumulative spend."""
        beta = self._make_wolf("beta", "beta", "plus", True)
        parsed: dict = {}
        with contextlib.suppress(Exception):
            res = await beta.think(
                "plan",
                messages=self._messages(
                    beta,
                    "plan",
                    context=f"Coordination strategy: {self._strategy.label} "
                    f"({self._strategy.pattern}).",
                ),
                response_schema=PLAN_SCHEMA,
            )
            parsed = res.parsed or {}
        self._plan = self._normalize_plan(parsed)
        self._queries = list(self._plan["queries"])
        await self._emit("plan_proposed", "beta", self._plan)
        await self._repo.set_hunt_state(self._hunt_id, "plan_ready")

    def _scout_count(self) -> int:
        """How many scouts the team carries (pre-spawn — reads the spec, not live wolves)."""
        n = next((int(e.get("count") or 0) for e in self._team if e.get("role") == "scout"), 0)
        return n or _DEFAULT_SCOUTS

    def _normalize_plan(self, parsed: dict) -> dict:
        """Coerce the model's plan into a schema-valid plan_proposed payload: build the per-task
        TEAM, then derive the scout angles/steps/worker-roster from it (additive canvas fields)."""
        task = self._raw_input or "the topic"
        self._team = _build_team(parsed)
        scout_ids = _wolf_ids("scout", self._scout_count())
        n = len(scout_ids)
        queries = [str(q).strip() for q in (parsed.get("queries") or []) if str(q).strip()][:n]
        while len(queries) < n:
            queries.append(f"{task} — angle {len(queries) + 1}")
        assumptions = [str(a).strip() for a in (parsed.get("assumptions") or []) if str(a).strip()]
        return {
            "steps": [
                {
                    "step_id": "s1",
                    "summary": f"Range on {n} angles of {task}",
                    "wolves": list(scout_ids),
                },
                {
                    "step_id": "s2",
                    "summary": "Cross-reference the findings and extract claims",
                    "wolves": ["tracker"],
                },
                {
                    "step_id": "s3",
                    "summary": "Draft the briefing with citations",
                    "wolves": ["howler"],
                },
            ],
            "wolves": [*scout_ids, "tracker", "sentinel", "howler"],
            "pattern": self._strategy.pattern,
            "assumptions": assumptions or [f"scope: {task}", "recent sources", "briefing format"],
            "est_cost": float(parsed.get("est_cost") or 0.6),
            "est_time": int(parsed.get("est_time") or 210),
            # additive (schema allows extra fields): the canvas + Door + Edit Panel read these.
            "queries": queries,
            "strategy": self._strategy.name,
            "team": self._team,
        }

    async def _approve(self, cmd: dict) -> None:
        await self._apply_edits(cmd.get("edits") or {})

        approved = float(cmd.get("boundary_usd", 1.0))
        from app.config import settings

        # First-hunt silent cap: never spend past the cap, whatever was approved.
        effective = min(approved, settings.first_hunt_cap_usd)
        self._boundary = Boundary(boundary_usd=effective)
        await self._repo.set_boundary(self._hunt_id, effective)
        self._mode = str(cmd.get("mode") or "on_signal")
        await self._emit(
            "plan_approved",
            "user",
            {"mode": self._mode, "boundary_usd": effective},
        )
        await self._repo.set_hunt_state(self._hunt_id, "hunting")

    async def _apply_edits(self, edits: dict) -> None:
        """Apply the user's plan edits (queries/assumptions) before the hunt runs and record the
        change as a plan_edited event."""
        if not isinstance(edits, dict) or not edits:
            return
        diff: dict = {}
        # The user reshaped the formation in the Edit Panel — rebuild the canonical team from it.
        raw_team = edits.get("team")
        if isinstance(raw_team, list) and raw_team:
            self._team = _build_team({"team": raw_team})
            self._plan["team"] = self._team
            workers = [*_wolf_ids("scout", self._scout_count()), "tracker", "sentinel", "howler"]
            self._plan["wolves"] = workers
            diff["team"] = self._team
        raw_queries = edits.get("queries")
        if isinstance(raw_queries, list):
            n = self._scout_count()
            qs = [str(q).strip() for q in raw_queries if str(q).strip()][:n]
            if qs:
                while len(qs) < n:
                    qs.append(f"{self.task} — angle {len(qs) + 1}")
                self._plan["queries"] = qs
                self._queries = list(qs)
                diff["queries"] = qs
        raw_assumptions = edits.get("assumptions")
        if isinstance(raw_assumptions, list):
            a = [str(x).strip() for x in raw_assumptions if str(x).strip()]
            self._plan["assumptions"] = a
            diff["assumptions"] = a
        if diff:
            await self._emit("plan_edited", "user", {"diff": diff})

    async def _absorb_inputs(self) -> None:
        """Drain any mid-hunt `add_input` commands (non-blocking), persist each as an artifact,
        record it on the hunt's context, and emit input_added. A `stop` seen here still stops."""
        held: list[dict] = []
        while True:
            try:
                cmd = self._commands.get_nowait()
            except asyncio.QueueEmpty:
                break
            ctype = cmd.get("type")
            if ctype == "add_input":
                text = str(cmd.get("text") or "").strip()
                if text:
                    aid = new_artifact_id()
                    await self._repo.save_artifact(aid, self._hunt_id, "input", "user", {"text": text})
                    self._extra_inputs.append(text)
                    kind = str(cmd.get("kind") or "text")
                    if cmd.get("transcript"):  # audio that was transcribed → fire transcript_ready
                        await self._emit(
                            "transcript_ready",
                            "engine",
                            {
                                "artifact_id": aid,
                                "provider": str(cmd.get("provider") or "qwen_asr"),
                                "duration_s": float(cmd.get("duration_s") or 0.0),
                            },
                        )
                    await self._emit("input_added", "user", {"artifact_id": aid, "kind": kind, "mid_hunt": True})
            elif ctype == "stop":
                raise StopHunt()
            else:
                held.append(cmd)
        for c in held:
            self._commands.put_nowait(c)

    async def _spawn_roster(self) -> None:
        roster = _roster_from_team(self._team or _build_team({}))
        for wolf_id, role, tier, thinking, budget in roster:
            self._wolves[wolf_id] = self._make_wolf(wolf_id, role, tier, thinking)
            self._wolf_budget[wolf_id] = budget
            await self._emit(
                "wolf_spawned",
                "engine",
                {
                    "wolf_id": wolf_id,
                    "role": role,
                    "model_tier": tier,
                    "thinking": thinking,
                    "prompt_version": load_prompt(role).version,
                    "budget_usd": budget,
                    "parent_wolf_id": None,
                },
            )

    async def _open_pack(self) -> None:
        """Wake the pack's leadership on the canvas at kickoff. Alpha takes the lead and stays active
        until finish; Beta hands the approved plan to the pack (its planning is already done). Both
        emit real lifecycle events so their nodes light up and the edges leaving them flow — without
        this, Alpha/Beta sit dormant the whole hunt and their edges never animate."""
        await self._emit(
            "step_started",
            "alpha",
            {"step_id": "s0-lead", "wolf_id": "alpha", "summary": "Leading the hunt"},
        )
        await self._emit(
            "step_started",
            "beta",
            {"step_id": "s0-brief", "wolf_id": "beta", "summary": "Briefed the pack on the plan"},
        )
        await self._emit(
            "step_completed",
            "beta",
            {
                "step_id": "s0-brief",
                "wolf_id": "beta",
                "output_ref": f"art_{self._hunt_id}_plan",
                "confidence": 0.9,
            },
        )

    # --- Engine surface (the primitives strategies orchestrate) ------------------------

    @property
    def task(self) -> str:
        return self._raw_input or "the topic"

    @property
    def plan(self) -> dict:
        return self._plan

    def scout_ids(self) -> list[str]:
        # Live scouts in spawn order — N is whatever Alpha built / the user edited, not a fixed 3.
        return [wid for wid, w in self._wolves.items() if w.role == "scout"]

    def queries(self) -> list[str]:
        return list(self._queries)

    async def progress(self, wolf_id: str, phase: str, text: str) -> None:
        """A live progress beat to a wolf's node on the canvas (throttled, never per-token)."""
        await self._emit(
            "wolf_progress", wolf_id, {"wolf_id": wolf_id, "phase": phase, "text": text[:200]}
        )

    async def scout(self, wolf_id: str, query: str, step_id: str = "s1") -> Finding:
        """One scout's range: real web search → summarize the hits with their sources → hand off."""
        wolf = self._wolves.get(wolf_id)
        if wolf is None:
            return Finding(wolf_id=wolf_id, summary="", sources=[], confidence=0.0)

        # Plain keywords reach the APIs — covers Beta's plan and the user's edited angles.
        query = _plain_query(query)
        await self._emit(
            "step_started", wolf_id, {"step_id": step_id, "wolf_id": wolf_id, "summary": f"Searching: {query}"}
        )
        await self.progress(wolf_id, "searching", f"Searching: {query}")

        hits, ok, ref, stray = await self._scout_search(wolf, query)
        if stray:  # the tools kept failing — Alpha reroutes this scout
            await self._stray_event(wolf_id, stray, ref)
        await self.progress(wolf_id, "reading", f"Reading {len(hits)} sources")

        out_ref = ref or f"art_{wolf_id}_out"
        try:
            # A wolf that stalls past the step timeout is a Stray; reroute and move on.
            res = await asyncio.wait_for(
                self._dispatch(
                    wolf,
                    "search",
                    context=self._hits_context(query, hits),
                    phase="reading",
                    response_schema=FINDINGS_SCHEMA,
                ),
                timeout=self._step_timeout,
            )
        except TimeoutError:
            await self._stray_event(wolf_id, "timeout", ref)
            await self._emit(
                "step_completed",
                wolf_id,
                {"step_id": step_id, "wolf_id": wolf_id, "output_ref": out_ref, "confidence": 0.2},
            )
            return Finding(
                wolf_id=wolf_id, summary=f"(stalled on {query})", sources=hits, confidence=0.2, output_ref=out_ref
            )

        parsed = res.parsed or {}
        summary = str(parsed.get("summary") or res.text or f"Findings on {query}")
        confidence = float(parsed.get("confidence", 0.8 if ok else 0.3) or 0.0)

        await self._emit(
            "step_completed",
            wolf_id,
            {"step_id": step_id, "wolf_id": wolf_id, "output_ref": out_ref, "confidence": round(confidence, 2)},
        )
        await self._emit(
            "message_passed",
            wolf_id,
            {
                "from_wolf": wolf_id,
                "to_wolf": "tracker",
                "intent": "handoff_findings",
                "summary": summary[:140],
                "ref": out_ref,
            },
        )
        return Finding(wolf_id=wolf_id, summary=summary, sources=hits, confidence=confidence, output_ref=out_ref)

    async def merge(self, findings: list[Finding], step_id: str = "s2") -> Merged:
        """Tracker cross-references the findings into claims and surfaces any real conflict."""
        await self._absorb_inputs()  # A7: fold in anything the Packmaster added mid-hunt
        tracker = self._wolves["tracker"]
        await self._emit(
            "step_started",
            "tracker",
            {"step_id": step_id, "wolf_id": "tracker", "summary": "Cross-referencing the scouts' findings"},
        )
        await self.progress("tracker", "merging", f"Cross-referencing {len(findings)} findings")

        res = await self._dispatch(
            tracker,
            "merge",
            context=self._findings_context(findings),
            phase="merging",
            response_schema=MERGE_SCHEMA,
        )
        parsed = res.parsed or {}
        summary = str(parsed.get("summary") or res.text or "Merged the findings.")
        claims = [str(c).strip() for c in (parsed.get("claims") or []) if str(c).strip()]
        conflict = self._conflict_from(parsed.get("conflict"))
        out_ref = new_artifact_id()
        await self._repo.save_artifact(
            out_ref, self._hunt_id, "draft", "tracker", {"summary": summary, "claims": claims}
        )
        await self._emit(
            "step_completed",
            "tracker",
            {"step_id": step_id, "wolf_id": "tracker", "output_ref": out_ref, "confidence": 0.9},
        )
        sources = [s for f in findings for s in f.sources]
        return Merged(summary=summary, claims=claims, conflict=conflict, output_ref=out_ref, sources=sources)

    async def resolve_conflict(self, conflict: Conflict) -> str:
        """Open a Hold for the human and block until they decide — unless the Packmaster set the
        leash to On Wild, in which case Alpha takes his own recommended call and keeps running."""
        hold_id = new_hold_id()
        await self._emit(
            "hold_opened",
            "alpha",
            {
                "hold_id": hold_id,
                "question": conflict.question,
                "context_ref": conflict.context_ref,
                "options": conflict.options,
                "recommended": conflict.recommended,
            },
        )
        if self._mode == "wild":
            resolution = conflict.recommended
            await self._emit(
                "hold_resolved",
                "alpha",
                {"hold_id": hold_id, "resolution": resolution, "auto": True},
            )
            return resolution
        await self._repo.set_hunt_state(self._hunt_id, "holding")
        cmd = await self._await_command("resolve_hold")
        resolution = str(cmd.get("resolution") or conflict.recommended)
        await self._emit(
            "hold_resolved",
            "user",
            {"hold_id": hold_id, "resolution": resolution, "edited_text": cmd.get("edited_text")},
        )
        await self._repo.set_hunt_state(self._hunt_id, "hunting")
        return resolution

    async def find_gaps(self, merged: Merged) -> list[str]:
        """Tracker names what's still missing — the queries for a second deep-dive round."""
        tracker = self._wolves["tracker"]
        res = await self._dispatch(
            tracker, "gaps", context=self._merged_context(merged), phase="thinking", response_schema=GAPS_SCHEMA
        )
        parsed = res.parsed or {}
        return [str(g).strip() for g in (parsed.get("gaps") or []) if str(g).strip()][:2]

    async def critique(self, merged: Merged) -> CritiqueResult:
        """Sentinel checks every claim carries a real source."""
        sentinel = self._wolves["sentinel"]
        await self._emit(
            "step_started",
            "sentinel",
            {"step_id": "s-critique", "wolf_id": "sentinel", "summary": "Verifying the claims"},
        )
        await self.progress("sentinel", "critiquing", "Checking every claim carries a source")
        res = await self._dispatch(
            sentinel,
            "critique",
            context=self._merged_context(merged),
            phase="critiquing",
            response_schema=CRITIQUE_SCHEMA,
        )
        parsed = res.parsed or {}
        issues = [i for i in (parsed.get("issues") or []) if isinstance(i, dict)]
        await self._emit(
            "step_completed",
            "sentinel",
            {"step_id": "s-critique", "wolf_id": "sentinel", "output_ref": f"art_{self._hunt_id}_critique", "confidence": 0.9},
        )
        return CritiqueResult(ok=bool(parsed.get("ok", True)), issues=issues)

    async def standoff(self, challenger: str, defendant: str, claim_ref: str, rationale: str) -> None:
        """A real, bounded debate over a weak claim: the challenger presses it, the defendant
        answers, Alpha adjudicates — each a model call, each boundary-gated."""
        sid = new_standoff_id()
        await self._repo.set_hunt_state(self._hunt_id, "standoff")
        await self._emit(
            "standoff_opened",
            challenger,
            {"standoff_id": sid, "challenger": challenger, "defendant": defendant, "claim_ref": claim_ref},
        )

        # Turn 1 — the challenger states why the claim doesn't yet stand.
        chal_text = rationale
        chal_wolf = self._wolves.get(challenger)
        if chal_wolf is not None:
            res = await self._dispatch(
                chal_wolf, "standoff_challenge", context=f"The claim under challenge: {rationale}", phase="critiquing"
            )
            chal_text = res.text or rationale
        await self._emit(
            "standoff_turn", challenger, {"standoff_id": sid, "turn_no": 1, "argument_summary": chal_text[:140]}
        )

        # Turn 2 — the defendant answers.
        def_text = "Fair — I'll back it with a second source."
        def_wolf = self._wolves.get(defendant)
        if def_wolf is not None:
            res = await self._dispatch(
                def_wolf, "standoff_defend", context=f"The challenge to answer: {chal_text}", phase="thinking"
            )
            def_text = res.text or def_text
        await self._emit(
            "standoff_turn", defendant, {"standoff_id": sid, "turn_no": 2, "argument_summary": def_text[:140]}
        )

        # Alpha adjudicates.
        rationale_out = "Keep the claim only once a second source backs it."
        alpha = self._wolves.get("alpha")
        if alpha is not None:
            res = await self._dispatch(
                alpha, "standoff_judge", context=f"Challenge: {chal_text}\nDefense: {def_text}", phase="thinking"
            )
            rationale_out = res.text or rationale_out
        await self._emit(
            "standoff_resolved",
            "alpha",
            {"standoff_id": sid, "outcome": "alpha_call", "rationale": rationale_out[:200]},
        )
        await self._repo.set_hunt_state(self._hunt_id, "hunting")

    async def _confirm_draft(self) -> None:
        """On Command only: Alpha checks in before the final write-up so the Packmaster can add
        anything first. Loops until they say go (each pass folds in any mid-hunt input)."""
        while True:
            hold_id = new_hold_id()
            await self._emit(
                "hold_opened",
                "alpha",
                {
                    "hold_id": hold_id,
                    "question": "Ready for the pack to write up the brief?",
                    "options": ["Write the brief", "Wait — I'll add something first"],
                    "recommended": "Write the brief",
                },
            )
            await self._repo.set_hunt_state(self._hunt_id, "holding")
            cmd = await self._await_command("resolve_hold")
            resolution = str(cmd.get("resolution") or "Write the brief")
            await self._emit("hold_resolved", "user", {"hold_id": hold_id, "resolution": resolution})
            await self._repo.set_hunt_state(self._hunt_id, "hunting")
            await self._absorb_inputs()
            if resolution == "Write the brief":
                return

    async def draft(self, merged: Merged, decision: str | None = None, step_id: str = "s3") -> str:
        """Howler writes the final briefing from the merged claims and the chosen decision."""
        await self._absorb_inputs()  # A7: last chance to fold in mid-hunt input before drafting
        if self._mode == "on_command":
            await self._confirm_draft()
        howler = self._wolves["howler"]
        await self._emit(
            "step_started",
            "howler",
            {"step_id": step_id, "wolf_id": "howler", "summary": "Drafting the briefing with citations"},
        )
        await self.progress("howler", "writing", "Drafting the briefing")
        res = await self._dispatch(howler, "draft", context=self._draft_context(merged, decision), phase="writing")
        await self._emit(
            "step_completed",
            "howler",
            {"step_id": step_id, "wolf_id": "howler", "output_ref": f"art_{self._hunt_id}_draft", "confidence": 0.86},
        )
        return res.text or merged.summary

    async def finish(self, draft_text: str, merged: Merged) -> None:
        """Save the final artifact + a provenance span map, then close the hunt."""
        artifact_id = new_artifact_id()
        sources = self._dedupe_sources(merged.sources)

        # B3 — a real (coarse) provenance map: each claim → the sources that back it.
        spanmap_ref: str | None = None
        if merged.claims and sources:
            spanmap_ref = new_artifact_id()
            spans = [
                {"claim": c, "source_refs": [s.get("url", "") for s in sources[:3] if s.get("url")]}
                for c in merged.claims
            ]
            await self._repo.save_artifact(spanmap_ref, self._hunt_id, "spanmap", "howler", {"spans": spans})

        await self._repo.save_artifact(
            artifact_id,
            self._hunt_id,
            "final",
            "howler",
            {"text": draft_text, "claims": merged.claims, "sources": sources, "span_map_ref": spanmap_ref},
        )
        await self._emit(
            "artifact_created",
            "howler",
            {
                "artifact_id": artifact_id,
                "kind": "final",
                "produced_by": "howler",
                "provenance_span_map_ref": spanmap_ref,
            },
        )
        totals = {
            "cost_usd": round(self._boundary.cumulative_usd, 6),
            "time_s": int(self._plan.get("est_time", 210)),
            "sources": len(sources),
            "wolves": len(self._wolves),
        }
        # Alpha closes out — its node settles to done (green) instead of glowing forever.
        await self._emit(
            "step_completed",
            "alpha",
            {
                "step_id": "s0-lead",
                "wolf_id": "alpha",
                "output_ref": artifact_id,
                "confidence": 0.95,
            },
        )
        await self._emit("hunt_completed", "engine", {"final_artifact_id": artifact_id, "totals": totals})
        await self._repo.set_hunt_state(self._hunt_id, "returned")

    # --- dispatch (the gate) + tools ---------------------------------------------------

    async def _dispatch(
        self,
        wolf: Wolf,
        intent: str,
        context: str = "",
        *,
        phase: str | None = None,
        response_schema: dict | None = None,
    ) -> CompletionResult:
        """The one path a model call takes. Gate BEFORE the call, account AFTER."""
        est = pricing.estimate(wolf.tier)
        verdict = self._boundary.check(est)

        if verdict is Verdict.HALT:
            # Halt is a PAUSE, not a death: checkpoint, surface the choice, and wait for the human
            # to raise the Boundary (resume) or stop. On resume, re-check the gate and proceed.
            await self._halt()
            await self._await_resume()
            return await self._dispatch(
                wolf, intent, context, phase=phase, response_schema=response_schema
            )
        if verdict is Verdict.DOWNGRADE and wolf.tier != "flash":
            from_tier, thinking_off = wolf.tier, wolf.thinking
            wolf.tier, wolf.thinking = "flash", False
            await self._emit(
                "boundary_downgrade",
                "engine",
                {"wolf_id": wolf.wolf_id, "from_tier": from_tier, "to_tier": "flash", "thinking_off": thinking_off},
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

        on_delta = self._progress_sink(wolf.wolf_id, phase) if (phase and wolf.thinking) else None
        result = await wolf.think(
            intent,
            messages=self._messages(wolf, intent, context),
            response_schema=response_schema,
            on_delta=on_delta,
        )
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

    async def _scout_search(
        self, wolf: Wolf, query: str
    ) -> tuple[list[dict], bool, str | None, str | None]:
        """Run the real web_search, deep-read the top hit (web_fetch), persist the hits, emit the
        tool events. Returns (hits, ok, artifact_ref, stray_pattern-or-None)."""
        await self._emit(
            "tool_called", wolf.wolf_id, {"wolf_id": wolf.wolf_id, "tool": "web_search", "args_summary": query}
        )
        res = await WEB_SEARCH.run(wolf_id=wolf.wolf_id, query=query)
        stray = self._stray.record_tool_result(wolf.wolf_id, res.ok)
        hits = (res.data or {}).get("hits", []) if isinstance(res.data, dict) else []
        ref: str | None = None
        if hits:
            ref = new_artifact_id()
            await self._repo.save_artifact(
                ref, self._hunt_id, "search", wolf.wolf_id, {"query": query, "hits": hits}
            )
            self._sources.extend(hits)
        await self._emit(
            "tool_result",
            wolf.wolf_id,
            {
                "wolf_id": wolf.wolf_id,
                "tool": "web_search",
                "ok": res.ok,
                "result_ref": ref,
                "latency_ms": res.latency_ms,
                "hits": len(hits),  # additive: lets the canvas show a per-wolf source count
            },
        )

        # A4 — deep-read the top hit so findings rest on the full page, not just the snippet.
        if hits and hits[0].get("url"):
            url = str(hits[0]["url"])
            await self._emit(
                "tool_called", wolf.wolf_id, {"wolf_id": wolf.wolf_id, "tool": "web_fetch", "args_summary": url}
            )
            fres = await WEB_FETCH.run(wolf_id=wolf.wolf_id, url=url)
            stray = stray or self._stray.record_tool_result(wolf.wolf_id, fres.ok)
            text = (fres.data or {}).get("text", "") if isinstance(fres.data, dict) else ""
            if text:
                hits[0] = {**hits[0], "text": text[:1500]}
            await self._emit(
                "tool_result",
                wolf.wolf_id,
                {
                    "wolf_id": wolf.wolf_id,
                    "tool": "web_fetch",
                    "ok": fres.ok,
                    "result_ref": None,
                    "latency_ms": fres.latency_ms,
                    "hits": 1 if text else 0,
                },
            )

        # Provenance tags (B3): which scout brought it back, and whether we actually read the page.
        for h in hits:
            h["by"] = wolf.wolf_id
            h["verified"] = bool(h.get("text"))
        return hits, res.ok, ref, stray

    def _progress_sink(self, wolf_id: str, phase: str) -> OnDelta:
        """Coalesce streamed text into a few sentence-bounded `wolf_progress` beats (never one
        per token), so a thinking wolf's evolving thought lands on its node without flooding
        the log. Deterministic: no clock — it throttles on sentence boundaries and length."""
        state = {"acc": "", "mark": 0, "beats": 0}

        async def on_delta(delta: str) -> None:
            state["acc"] += delta
            pending = state["acc"][state["mark"] :]
            sentence_end = pending.endswith((".", "!", "?", "\n")) and len(pending.strip()) >= 40
            overflow = len(pending) >= 160
            if (sentence_end or overflow) and state["beats"] < 8:
                state["mark"] = len(state["acc"])
                state["beats"] += 1
                await self.progress(wolf_id, phase, pending.strip())

        return on_delta

    async def _await_resume(self) -> None:
        """Block at a Boundary halt until the human raises the Boundary (resume) or stops."""
        await self._repo.set_hunt_state(self._hunt_id, "halted_boundary")
        while True:
            cmd = await self._commands.get()
            ctype = cmd.get("type")
            if ctype == "stop":
                raise StopHunt()
            if ctype == "resume":
                raised = float(cmd.get("boundary_usd", self._boundary.boundary_usd * 2))
                self._boundary.boundary_usd = max(raised, self._boundary.boundary_usd)
                self._warned = False  # let a fresh warning fire against the new ceiling
                await self._repo.set_boundary(self._hunt_id, self._boundary.boundary_usd)
                await self._repo.set_hunt_state(self._hunt_id, "hunting")
                return
            # ignore anything else while paused

    async def _halt(self) -> None:
        ckpt = new_checkpoint_id()
        await self._repo.save_checkpoint(
            ckpt, self._hunt_id, self._emitter.last_seq, {"cumulative_usd": self._boundary.cumulative_usd}
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

    async def _stray_event(self, wolf_id: str, pattern: str, evidence_ref: str | None) -> None:
        """Narrate a Stray and Alpha's recovery (reroute). The hunt stays in 'hunting'."""
        await self._emit(
            "stray_detected",
            "engine",
            {"wolf_id": wolf_id, "pattern": pattern, "evidence_ref": evidence_ref or f"art_{wolf_id}_stray"},
        )
        note = {
            "repeat_fail": f"{wolf_id} kept hitting dead ends — Alpha rerouted it.",
            "loop": f"{wolf_id} was circling the same ground — Alpha reset its angle.",
            "timeout": f"{wolf_id} stalled — Alpha pulled it back and the pack moved on.",
        }.get(pattern, f"{wolf_id} went off track — Alpha recovered the hunt.")
        await self._emit(
            "stray_recovered",
            "engine",
            {"wolf_id": wolf_id, "action": "reroute", "note_plain_english": note},
        )

    # --- prompt + context builders -----------------------------------------------------

    def _messages(self, wolf: Wolf, intent: str, context: str) -> list[dict]:
        """The role's prompt file is the system message; the task + intent instruction + any
        upstream context is the user message."""
        system = load_prompt(wolf.role).body
        user = f"Task: {self._raw_input or 'Research the topic and produce a briefing.'}\n\n"
        user += _INTENT_INSTRUCTIONS.get(intent, intent)
        if context:
            user += f"\n\nContext:\n{context}"
        return [{"role": "system", "content": system}, {"role": "user", "content": user}]

    def _hits_context(self, query: str, hits: list[dict]) -> str:
        if not hits:
            return f"Your angle: {query}\n(No results returned.)"
        lines = []
        for h in hits:
            line = f"- {h.get('title', '')} — {h.get('url', '')}: {h.get('snippet', '')}"
            if h.get("text"):  # the deep-read full page (web_fetch), when available
                line += f"\n    [full text] {h['text'][:800]}"
            lines.append(line)
        return f"Your angle: {query}\nSearch results:\n" + "\n".join(lines)

    def _findings_context(self, findings: list[Finding]) -> str:
        blocks = []
        for f in findings:
            srcs = "; ".join(f"{s.get('title', '')} ({s.get('url', '')})" for s in f.sources[:4])
            blocks.append(f"[{f.wolf_id}] {f.summary}\nSources: {srcs or 'none'}")
        out = "\n\n".join(blocks) or "No findings."
        return out + self._extra_inputs_block()

    def _extra_inputs_block(self) -> str:
        if not self._extra_inputs:
            return ""
        joined = "\n".join(f"- {t[:800]}" for t in self._extra_inputs)
        return f"\n\nThe Packmaster also provided this input — weigh it:\n{joined}"

    def _merged_context(self, merged: Merged) -> str:
        claims = "\n".join(f"- {c}" for c in merged.claims)
        return f"Summary: {merged.summary}\nClaims:\n{claims}"

    def _draft_context(self, merged: Merged, decision: str | None) -> str:
        parts = [self._merged_context(merged)]
        if decision:
            parts.append(f"Resolved decision: {decision}")
        sources = self._dedupe_sources(merged.sources)
        if sources:
            parts.append(
                "Sources:\n" + "\n".join(f"- {s.get('title', '')}: {s.get('url', '')}" for s in sources[:8])
            )
        block = self._extra_inputs_block()
        if block:
            parts.append(block.strip())
        return "\n\n".join(parts)

    def _conflict_from(self, obj: object) -> Conflict | None:
        if not isinstance(obj, dict):
            return None
        question = str(obj.get("question") or "").strip()
        options = [str(o).strip() for o in (obj.get("options") or []) if str(o).strip()]
        if not question or len(options) < 2:
            return None
        return Conflict(
            question=question,
            options=options,
            recommended=str(obj.get("recommended") or options[0]),
            context_ref=None,
        )

    def _dedupe_sources(self, sources: list[dict]) -> list[dict]:
        seen: set[str] = set()
        out: list[dict] = []
        for s in sources:
            url = s.get("url", "")
            if url and url not in seen:
                seen.add(url)
                out.append(s)
        return out

    # --- helpers -----------------------------------------------------------------------

    def _make_wolf(self, wolf_id: str, role: str, tier: str, thinking: bool) -> Wolf:
        return Wolf(
            hunt_id=self._hunt_id,
            wolf_id=wolf_id,
            role=role,
            tier=tier,
            thinking=thinking,
            prompt_version=load_prompt(role).version,
            client=self._client,
        )

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
