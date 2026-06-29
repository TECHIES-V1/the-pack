"""Registry liveness (backend B7): commands to a finished hunt are rejected, not silently accepted."""

from __future__ import annotations

import asyncio

from app.engine.registry import HuntRegistry


async def test_send_rejects_unknown_and_finished_hunts() -> None:
    reg = HuntRegistry()
    handle = reg.register("h1")

    # No task attached yet = the brief pre-start window → still live, command queues.
    assert await reg.send("h1", {"type": "approve_plan"}) is True

    # Unknown hunt → rejected.
    assert await reg.send("nope", {"type": "stop"}) is False

    # Once the Supervisor task has finished, further commands are rejected (no false 202).
    async def _done() -> None:
        return None

    handle.task = asyncio.create_task(_done())
    await handle.task
    assert await reg.send("h1", {"type": "stop"}) is False
