"""The offline hunt — the whole engine runs end to end with no key and no infrastructure.

Drives the REAL Supervisor (real Emitter, real Boundary, real QwenClient in offline mode, the
real strategy package) over an in-memory repo and asserts the engine's invariants: dense seq,
every event valid against the FROZEN schema, the Boundary respected, the hunt opens with
`hunt_created` and closes with `hunt_completed`, and the live-research lifecycle is present.

This is the proof that the pipeline is correct before the model key ever arrives. It no longer
pins the exact event MULTISET to a hand-authored fixture (the engine is now dynamic and
strategy-driven); it tests the invariants the contract actually guarantees.
"""

from __future__ import annotations

import asyncio

import pytest
from jsonschema import Draft202012Validator

from app.engine.core import Emitter
from app.engine.supervisor import Supervisor
from app.events.models import load_event_schema
from app.qwen.client import QwenClient

from ._fakes import FakeRepo

# The lifecycle every offline hunt must exhibit, whatever the strategy.
_REQUIRED_TYPES = {
    "hunt_created",
    "plan_proposed",
    "plan_approved",
    "wolf_spawned",
    "step_started",
    "tool_called",
    "tool_result",
    "tokens_spent",
    "wolf_progress",
    "message_passed",
    "step_completed",
    "artifact_created",
    "hunt_completed",
}


async def _run(strategy: str) -> list:
    repo = FakeRepo()
    hunt_id = f"hunt_offline_{strategy}"
    emitter = Emitter(hunt_id, repo)
    client = QwenClient()
    assert client.offline, "test env has no key, so the brain must be FakeQwen"

    commands: asyncio.Queue = asyncio.Queue()
    # Offline findings are clean (no conflict), so orchestrate opens no Hold — only the one
    # human gate is needed. Pre-queue it so the supervisor runs straight through.
    commands.put_nowait({"type": "approve_plan", "mode": "on_signal", "boundary_usd": 1.0})

    sup = Supervisor(
        hunt_id,
        emitter,
        repo,
        client,
        commands,
        source="typed",
        raw_input="the BNPL market in Nigeria",
        strategy=strategy,
    )
    await asyncio.wait_for(sup.run(), timeout=15)
    return repo.all_events(hunt_id)


def _assert_invariants(events: list) -> None:
    # seq is dense, 0-based, gap-free.
    assert [e.seq for e in events] == list(range(len(events)))

    # every emitted event validates against the frozen schema.
    validator = Draft202012Validator(load_event_schema())
    for e in events:
        errors = list(validator.iter_errors(e.model_dump()))
        assert not errors, f"seq {e.seq} ({e.type}) invalid: {[x.message for x in errors]}"

    # it starts created and ends completed.
    assert events[0].type == "hunt_created"
    assert events[-1].type == "hunt_completed"

    # the full live-research lifecycle is present.
    produced = {e.type for e in events}
    assert _REQUIRED_TYPES <= produced, f"missing: {_REQUIRED_TYPES - produced}"

    # the Boundary was respected: no spend event ever exceeds the (first-hunt-capped) budget.
    boundary = next(e for e in events if e.type == "plan_approved").payload["boundary_usd"]
    for e in events:
        if e.type == "tokens_spent":
            assert e.payload["cumulative_usd"] <= boundary + 1e-9

    # the happy path stays well under budget — no boundary events at all.
    assert not any(e.type.startswith("boundary_") for e in events)


async def test_offline_orchestrate_runs_clean() -> None:
    events = await _run("orchestrate")
    _assert_invariants(events)
    # the default strategy never invents a conflict offline, so no Hold fires.
    assert not any(e.type == "hold_opened" for e in events)


async def test_offline_deep_dive_does_a_second_round() -> None:
    events = await _run("deep_dive")
    _assert_invariants(events)
    # the iterative strategy ranges twice — more than three scout step_starts.
    scout_steps = [e for e in events if e.type == "step_started" and e.payload["wolf_id"].startswith("scout")]
    assert len(scout_steps) > 3


async def test_offline_critique_opens_a_standoff() -> None:
    events = await _run("critique")
    _assert_invariants(events)
    # Sentinel challenges the weakest claim, and the standoff resolves cleanly.
    assert any(e.type == "standoff_opened" for e in events)
    assert any(e.type == "standoff_resolved" for e in events)


async def test_offline_per_wolf_budget_relieves_a_scout(monkeypatch: pytest.MonkeyPatch) -> None:
    """v2: a scout that would blow its own tiny per-wolf cap stands down — the hunt still finishes
    (one runaway wolf can't drain or halt the whole hunt)."""
    from app.engine import supervisor as sup_mod

    tier, thinking, _ = sup_mod._ROLE_SPEC["scout"]
    monkeypatch.setitem(sup_mod._ROLE_SPEC, "scout", (tier, thinking, 0.001))  # near-zero cap

    repo = FakeRepo()
    hunt_id = "hunt_offline_relief"
    emitter = Emitter(hunt_id, repo)
    client = QwenClient()
    commands: asyncio.Queue = asyncio.Queue()
    commands.put_nowait({"type": "approve_plan", "mode": "on_signal", "boundary_usd": 1.0})
    sup = Supervisor(
        hunt_id, emitter, repo, client, commands,
        source="typed", raw_input="the BNPL market in Nigeria", strategy="orchestrate",
    )
    await asyncio.wait_for(sup.run(), timeout=15)
    events = repo.all_events(hunt_id)

    assert any(wid.startswith("scout") for wid in sup._relieved), "a scout should be relieved"
    assert events[-1].type == "hunt_completed", "the hunt still finishes despite a relieved scout"
    # seq stays dense and every event is schema-valid even on the relief path.
    assert [e.seq for e in events] == list(range(len(events)))
    validator = Draft202012Validator(load_event_schema())
    for e in events:
        assert not list(validator.iter_errors(e.model_dump()))


async def test_offline_doctor_heals_faults_and_clones() -> None:
    """v2: a fault dispatches the Doctor to heal it; a second concurrent fault clones the Doctor."""
    repo = FakeRepo()
    hunt_id = "hunt_doctor"
    emitter = Emitter(hunt_id, repo)
    sup = Supervisor(
        hunt_id, emitter, repo, QwenClient(), asyncio.Queue(),
        source="typed", raw_input="a topic", strategy="orchestrate",
    )
    await sup._stray_event("scout-1", "timeout", None)
    await sup._stray_event("scout-2", "repeat_fail", None)  # a second fault → the Doctor clones
    events = repo.all_events(hunt_id)
    types = [e.type for e in events]

    assert types.count("doctor_dispatched") == 2
    assert types.count("doctor_healed") == 2
    spawns = [e.payload for e in events if e.type == "wolf_spawned"]
    doctors = [p for p in spawns if p["role"] == "doctor"]
    assert len(doctors) == 2, "the Doctor clones itself for the second fault"
    assert any(d.get("parent_wolf_id") for d in doctors), "the clone records its parent Doctor"
    # the Stray path still fires alongside the Doctor, and every event is schema-valid.
    assert types.count("stray_detected") == 2 and types.count("stray_recovered") == 2
    validator = Draft202012Validator(load_event_schema())
    for e in events:
        assert not list(validator.iter_errors(e.model_dump()))


async def test_memory_recall_and_remember_roundtrip() -> None:
    """v2: local memory recalls empty on a first hunt, then surfaces a written takeaway."""
    from app.tools.memory import recall, remember

    repo = FakeRepo()
    assert await recall(repo) == ""  # nothing learned yet
    await remember(repo, "h1", "Prefer primary sources for finance topics.")
    note = await recall(repo)
    assert "Prefer primary sources" in note


async def test_offline_elder_recalls_and_remembers() -> None:
    """v2: the Elder appears, recalls seeded memory into planning, and writes a takeaway."""
    repo = FakeRepo()
    await repo.save_memory(None, "takeaway", "Prefer primary sources for finance topics.")
    hunt_id = "hunt_elder"
    emitter = Emitter(hunt_id, repo)
    commands: asyncio.Queue = asyncio.Queue()
    commands.put_nowait({"type": "approve_plan", "mode": "on_signal", "boundary_usd": 1.0})
    sup = Supervisor(
        hunt_id, emitter, repo, QwenClient(), commands,
        source="typed", raw_input="the BNPL market in Nigeria", strategy="orchestrate",
    )
    await asyncio.wait_for(sup.run(), timeout=15)
    events = repo.all_events(hunt_id)

    assert any(e.type == "wolf_spawned" and e.payload["role"] == "elder" for e in events)
    elder = next(e for e in events if e.type == "step_started" and e.payload["wolf_id"] == "elder")
    assert "Recalled" in elder.payload["summary"], "the seeded memory reached the Elder's recall"
    assert len(repo.memory) == 2 and any("BNPL" in m["text"] for m in repo.memory)


async def test_offline_no_sources_is_honest(monkeypatch: pytest.MonkeyPatch) -> None:
    """v3 (3.0): when search returns nothing, the pack returns an honest notice — never a fabricated
    brief — and flags the artifact so the Reward shows a clear empty state."""
    from app.tools import web

    class _Empty:
        ok = True
        data = {"hits": []}
        latency_ms = 5

    async def _empty_run(**_kwargs):
        return _Empty()

    monkeypatch.setattr(web.WEB_SEARCH, "run", _empty_run)

    repo = FakeRepo()
    hunt_id = "hunt_nosrc"
    emitter = Emitter(hunt_id, repo)
    commands: asyncio.Queue = asyncio.Queue()
    commands.put_nowait({"type": "approve_plan", "mode": "on_signal", "boundary_usd": 1.0})
    sup = Supervisor(
        hunt_id, emitter, repo, QwenClient(), commands,
        source="typed", raw_input="an extremely obscure topic", strategy="orchestrate",
    )
    await asyncio.wait_for(sup.run(), timeout=15)

    final = next(a for a in repo.artifacts if a["kind"] == "final")
    assert final["content"]["no_sources"] is True
    assert "couldn't find sources" in final["content"]["text"]  # the honest no-results notice
    assert final["content"]["sources"] == []
    assert repo.all_events(hunt_id)[-1].type == "hunt_completed"  # still finishes cleanly


async def test_memory_carries_across_hunts() -> None:
    """v4.1: a takeaway written when one hunt finishes is recalled into the next hunt's planning."""
    repo = FakeRepo()

    c1: asyncio.Queue = asyncio.Queue()
    c1.put_nowait({"type": "approve_plan", "mode": "on_signal", "boundary_usd": 1.0})
    sup1 = Supervisor(
        "hunt_m1", Emitter("hunt_m1", repo), repo, QwenClient(), c1,
        source="typed", raw_input="the solid-state battery market", strategy="orchestrate",
    )
    await asyncio.wait_for(sup1.run(), timeout=15)
    assert any(m["kind"] == "takeaway" for m in repo.memory)  # a takeaway was stored

    c2: asyncio.Queue = asyncio.Queue()
    c2.put_nowait({"type": "approve_plan", "mode": "on_signal", "boundary_usd": 1.0})
    sup2 = Supervisor(
        "hunt_m2", Emitter("hunt_m2", repo), repo, QwenClient(), c2,
        source="typed", raw_input="a totally unrelated topic", strategy="orchestrate",
    )
    await asyncio.wait_for(sup2.run(), timeout=15)
    assert "solid-state battery" in sup2._memory_note  # hunt 1's lesson reached hunt 2's planning


async def test_seed_team_overrides_beta_sizing() -> None:
    """v5.1: a saved Instinct's formation seeds the team instead of Beta's per-task sizing."""
    repo = FakeRepo()
    commands: asyncio.Queue = asyncio.Queue()
    commands.put_nowait({"type": "approve_plan", "mode": "on_signal", "boundary_usd": 1.0})
    sup = Supervisor(
        "hunt_seed", Emitter("hunt_seed", repo), repo, QwenClient(), commands,
        source="typed", raw_input="anything at all", strategy="orchestrate",
        seed_team=[{"role": "scout", "count": 5}],
    )
    await asyncio.wait_for(sup.run(), timeout=15)
    scouts = [
        e.payload["wolf_id"]
        for e in repo.all_events("hunt_seed")
        if e.type == "wolf_spawned" and e.payload.get("role") == "scout"
    ]
    assert len(scouts) == 5  # the seeded 5 scouts, not FakeQwen's default 3


async def test_knowledge_base_doc_becomes_a_source() -> None:
    """v4.2: a relevant library doc is injected into the hunt and shows up as a cited source."""
    repo = FakeRepo()
    await repo.save_document(
        "battery-notes.md",
        "md",
        "Internal notes on the solid-state battery market: supplier roadmap and the cost curve.",
    )
    commands: asyncio.Queue = asyncio.Queue()
    commands.put_nowait({"type": "approve_plan", "mode": "on_signal", "boundary_usd": 1.0})
    sup = Supervisor(
        "hunt_kb", Emitter("hunt_kb", repo), repo, QwenClient(), commands,
        source="typed", raw_input="the solid-state battery market", strategy="orchestrate",
    )
    await asyncio.wait_for(sup.run(), timeout=15)

    final = next(a for a in repo.artifacts if a["kind"] == "final")
    libs = [s for s in final["content"]["sources"] if str(s.get("url", "")).startswith("lib://")]
    assert libs, "the library doc should appear as a source"
    assert libs[0]["by"] == "your library"


def test_broaden_keeps_the_subject_and_drops_filler() -> None:
    """Part 1: _broaden() makes a dry scout's retry query — short, plain, subject preserved."""
    repo = FakeRepo()
    sup = Supervisor(
        "h", Emitter("h", repo), repo, QwenClient(), asyncio.Queue(),
        source="typed", raw_input="the Qwen3 open-source model family", strategy="orchestrate",
    )
    out = sup._broaden("Qwen3 code math variants GitHub release notes")
    assert out == sup._broaden("Qwen3 code math variants GitHub release notes")  # deterministic
    low = out.lower()
    assert "qwen3" in low  # the task subject survives
    assert "github" not in low and "release" not in low and "notes" not in low  # filler dropped
    assert 0 < len(out.split()) <= 7  # capped short so it actually returns hits


async def test_offline_dry_scout_broadens_and_recovers(monkeypatch: pytest.MonkeyPatch) -> None:
    """Part 1: when the scouts' first (narrow) angles come back dry, each broadens once and ranges
    again — so the pack returns with sources instead of collapsing onto a single working scout."""
    from app.tools import web

    class _R:
        def __init__(self, hits: list[dict]) -> None:
            self.ok = True
            self.data = {"hits": hits}
            self.latency_ms = 5

    calls = {"n": 0}

    async def _flaky_search(**_kwargs):
        calls["n"] += 1
        if calls["n"] <= 3:  # the 3 scouts' first angles return nothing
            return _R([])
        n = calls["n"]
        return _R(
            [{"title": f"Hit {n}", "url": f"https://example.com/{n}", "snippet": "real ground"}]
        )

    class _F:
        ok = False
        data = {"text": ""}
        latency_ms = 1

    async def _no_fetch(**_kwargs):
        return _F()

    monkeypatch.setattr(web.WEB_SEARCH, "run", _flaky_search)
    monkeypatch.setattr(web.WEB_FETCH, "run", _no_fetch)

    repo = FakeRepo()
    hunt_id = "hunt_dry"
    emitter = Emitter(hunt_id, repo)
    commands: asyncio.Queue = asyncio.Queue()
    commands.put_nowait({"type": "approve_plan", "mode": "on_signal", "boundary_usd": 1.0})
    sup = Supervisor(
        hunt_id, emitter, repo, QwenClient(), commands,
        source="typed", raw_input="a narrow research topic", strategy="orchestrate",
    )
    await asyncio.wait_for(sup.run(), timeout=15)

    final = next(a for a in repo.artifacts if a["kind"] == "final")
    assert final["content"]["no_sources"] is False
    assert final["content"]["sources"], "the broadened retry recovered real sources"
    assert calls["n"] > 3, "the dry first pass triggered at least one broaden retry"


async def test_offline_draft_is_tagged_with_provenance() -> None:
    """v3 (3.2): the final brief carries tagged blocks + a block-level provenance map."""
    repo = FakeRepo()
    hunt_id = "hunt_prov"
    emitter = Emitter(hunt_id, repo)
    commands: asyncio.Queue = asyncio.Queue()
    commands.put_nowait({"type": "approve_plan", "mode": "on_signal", "boundary_usd": 1.0})
    sup = Supervisor(
        hunt_id, emitter, repo, QwenClient(), commands,
        source="typed", raw_input="the BNPL market in Nigeria", strategy="orchestrate",
    )
    await asyncio.wait_for(sup.run(), timeout=15)

    final = next(a for a in repo.artifacts if a["kind"] == "final")
    blocks = final["content"]["blocks"]
    assert blocks and all("text" in b and "source_ids" in b for b in blocks)
    assert any(b["source_ids"] for b in blocks), "at least one block cites a source"

    prov = next(a for a in repo.artifacts if a["kind"] == "provenance_map")
    assert prov["content"]["spans"]
    assert final["content"]["span_map_ref"] == prov["artifact_id"]


async def test_offline_forge_renders_real_files() -> None:
    """v3 (3.4): the Forge turns the brief into real MD/HTML/PDF/DOCX files."""
    import base64 as b64

    repo = FakeRepo()
    hunt_id = "hunt_forge"
    emitter = Emitter(hunt_id, repo)
    commands: asyncio.Queue = asyncio.Queue()
    commands.put_nowait({"type": "approve_plan", "mode": "on_signal", "boundary_usd": 1.0})
    sup = Supervisor(
        hunt_id, emitter, repo, QwenClient(), commands,
        source="typed", raw_input="the BNPL market in Nigeria", strategy="orchestrate",
    )
    await asyncio.wait_for(sup.run(), timeout=15)

    kinds = {a["kind"] for a in repo.artifacts}
    assert {"md", "html", "pdf", "docx", "xlsx", "pptx", "png"} <= kinds  # v5.8: broader formats

    def body(kind: str) -> bytes:
        return b64.b64decode(next(a for a in repo.artifacts if a["kind"] == kind)["content"]["b64"])

    assert body("pdf").startswith(b"%PDF")  # a real PDF
    assert body("docx").startswith(b"PK")  # docx/xlsx/pptx are OOXML zips
    assert body("xlsx").startswith(b"PK")
    assert body("pptx").startswith(b"PK")
    assert body("png").startswith(b"\x89PNG")  # a real PNG
    types = [e.type for e in repo.all_events(hunt_id)]
    assert "forge_started" in types and "forge_completed" in types


@pytest.mark.parametrize("strategy", ["orchestrate", "deep_dive", "critique"])
async def test_offline_topic_awareness(strategy: str) -> None:
    """The hunt is topic-aware: the scouts' real queries mention the task, not a hardcoded demo."""
    events = await _run(strategy)
    tool_calls = [e for e in events if e.type == "tool_called"]
    assert tool_calls, "scouts must actually search"
    assert any("BNPL" in e.payload["args_summary"] or "Nigeria" in e.payload["args_summary"] for e in tool_calls)
