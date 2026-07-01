"""HTTP command layer integration tests — HTTP → registry → Supervisor.

Drives the real Supervisor through the FastAPI route layer using httpx.AsyncClient without
entering the context manager (so the lifespan, Postgres, and Redis never run). All state
dependencies are satisfied via app.dependency_overrides, injecting real in-memory fakes.

Key invariant being tested: the 202-Accepted command path ACTUALLY reaches the running
Supervisor and produces the expected events — not just a queue.put() that's never consumed.
"""

from __future__ import annotations

import asyncio

import httpx

from app.dependencies import get_background, get_client, get_registry, get_repo
from app.engine.registry import HuntRegistry
from app.main import app
from app.qwen.client import QwenClient

from ._fakes import FakeRepo


def _make_deps() -> tuple[FakeRepo, HuntRegistry, QwenClient]:
    """Fresh in-memory world for each test."""
    repo = FakeRepo()
    registry = HuntRegistry()
    client = QwenClient()
    assert client.offline, "HTTP tests must run offline (no QWEN_API_KEY in test env)"
    return repo, registry, client


def _override(repo: FakeRepo, registry: HuntRegistry, client: QwenClient) -> None:
    app.dependency_overrides[get_repo] = lambda: repo
    app.dependency_overrides[get_registry] = lambda: registry
    app.dependency_overrides[get_client] = lambda: client
    app.dependency_overrides[get_background] = lambda: set()


def _transport():
    """ASGI transport — bypasses the lifespan entirely."""
    return httpx.ASGITransport(app=app)


async def _wait_for_hunt_done(repo: FakeRepo, hunt_id: str, timeout: float = 15.0) -> list:
    """Poll the FakeRepo until hunt_completed arrives or timeout."""
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        events = repo.all_events(hunt_id)
        if events and events[-1].type == "hunt_completed":
            return events
        await asyncio.sleep(0.05)
    return repo.all_events(hunt_id)


# ---------------------------------------------------------------------------
# Hunt lifecycle: create → approve → complete
# ---------------------------------------------------------------------------


async def test_create_hunt_registers_supervisor_and_emits_hunt_created() -> None:
    """POST /hunts creates a handle in the registry; hunt_created event lands in FakeRepo."""
    repo, registry, client = _make_deps()
    _override(repo, registry, client)

    async with httpx.AsyncClient(transport=_transport(), base_url="http://test") as ac:
        r = await ac.post("/hunts", json={"input": "the BNPL market in Nigeria"})

    assert r.status_code == 202
    hunt_id = r.json()["hunt_id"]

    # Registry must have a live handle.
    handle = registry.get(hunt_id)
    assert handle is not None
    assert handle.task is not None

    # Approve the plan so the hunt can run to completion.
    await handle.commands.put({"type": "approve_plan", "mode": "on_signal", "boundary_usd": 1.0})

    await asyncio.wait_for(handle.task, timeout=15)

    events = repo.all_events(hunt_id)
    assert events[0].type == "hunt_created"
    assert events[-1].type == "hunt_completed"


async def test_approve_plan_via_http_starts_the_hunt() -> None:
    """POST /hunts then POST /hunts/{id}/plan/approve → the command reaches the Supervisor."""
    repo, registry, client = _make_deps()
    _override(repo, registry, client)

    async with httpx.AsyncClient(transport=_transport(), base_url="http://test") as ac:
        r = await ac.post("/hunts", json={"input": "solid-state battery market"})
        assert r.status_code == 202
        hunt_id = r.json()["hunt_id"]

        # Approve via HTTP — the command must reach the running Supervisor.
        r2 = await ac.post(
            f"/hunts/{hunt_id}/plan/approve",
            json={"mode": "on_signal", "boundary_usd": 1.0},
        )
        assert r2.status_code == 202

    handle = registry.get(hunt_id)
    await asyncio.wait_for(handle.task, timeout=15)

    events = repo.all_events(hunt_id)
    assert any(e.type == "plan_approved" for e in events)
    assert events[-1].type == "hunt_completed"


async def test_stop_hunt_via_http_emits_hunt_stopped() -> None:
    """POST /hunts/{id}/stop → Supervisor receives the command and emits hunt_stopped."""
    repo, registry, client = _make_deps()
    _override(repo, registry, client)

    async with httpx.AsyncClient(transport=_transport(), base_url="http://test") as ac:
        r = await ac.post("/hunts", json={"input": "the BNPL market in Nigeria"})
        hunt_id = r.json()["hunt_id"]

        r_stop = await ac.post(f"/hunts/{hunt_id}/stop")
        assert r_stop.status_code == 202

    handle = registry.get(hunt_id)
    await asyncio.wait_for(handle.task, timeout=10)

    types = [e.type for e in repo.all_events(hunt_id)]
    assert "hunt_stopped" in types


async def test_stop_unknown_hunt_returns_404() -> None:
    """POST /hunts/{id}/stop for a non-existent hunt → 404 (not 202)."""
    repo, registry, client = _make_deps()
    _override(repo, registry, client)

    async with httpx.AsyncClient(transport=_transport(), base_url="http://test") as ac:
        r = await ac.post("/hunts/hunt_does_not_exist/stop")

    assert r.status_code == 404


async def test_approve_plan_for_unknown_hunt_returns_404() -> None:
    """POST /hunts/{id}/plan/approve for a non-existent hunt → 404."""
    repo, registry, client = _make_deps()
    _override(repo, registry, client)

    async with httpx.AsyncClient(transport=_transport(), base_url="http://test") as ac:
        r = await ac.post(
            "/hunts/nope/plan/approve",
            json={"mode": "on_signal", "boundary_usd": 0.5},
        )

    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Intake gate
# ---------------------------------------------------------------------------


async def test_intake_greeting_returns_ready_false() -> None:
    """POST /hunts/intake with a greeting → ready=False, no hunt created."""
    repo, registry, client = _make_deps()
    _override(repo, registry, client)

    async with httpx.AsyncClient(transport=_transport(), base_url="http://test") as ac:
        r = await ac.post(
            "/hunts/intake",
            json={"messages": [{"role": "user", "content": "hi"}]},
        )

    assert r.status_code == 200
    body = r.json()
    assert body["ready"] is False
    # No hunts were created.
    assert repo.hunts == {}


async def test_intake_task_returns_ready_true_with_brief() -> None:
    """POST /hunts/intake with a real task → ready=True, brief is non-empty."""
    repo, registry, client = _make_deps()
    _override(repo, registry, client)

    async with httpx.AsyncClient(transport=_transport(), base_url="http://test") as ac:
        r = await ac.post(
            "/hunts/intake",
            json={
                "messages": [
                    {"role": "user", "content": "research the BNPL market in Nigeria for me"}
                ]
            },
        )

    assert r.status_code == 200
    body = r.json()
    assert body["ready"] is True
    assert body.get("brief", "")  # brief must be non-empty on a real task


# ---------------------------------------------------------------------------
# Command on finished hunt
# ---------------------------------------------------------------------------


async def test_command_after_hunt_done_returns_404() -> None:
    """Commands sent to a hunt after it finishes are rejected (registry guard)."""
    repo, registry, client = _make_deps()
    _override(repo, registry, client)

    async with httpx.AsyncClient(transport=_transport(), base_url="http://test") as ac:
        r = await ac.post("/hunts", json={"input": "the BNPL market in Nigeria"})
        hunt_id = r.json()["hunt_id"]

        r2 = await ac.post(
            f"/hunts/{hunt_id}/plan/approve",
            json={"mode": "on_signal", "boundary_usd": 1.0},
        )
        assert r2.status_code == 202

    handle = registry.get(hunt_id)
    await asyncio.wait_for(handle.task, timeout=15)
    assert handle.task.done()

    # Registry must now reject further commands.
    assert await registry.send(hunt_id, {"type": "stop"}) is False
