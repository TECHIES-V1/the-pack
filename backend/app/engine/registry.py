"""The hunt registry — live, in-process hunt handles (Doc 04 §6).

REST commands return 202 immediately; the running Supervisor is what actually acts. The
registry is the bridge: it maps `hunt_id` to the Supervisor's asyncio task plus a command
queue. A REST handler pushes a command (approve plan, resolve hold, stop) onto the queue
and returns; the Supervisor, blocked on `commands.get()`, picks it up and emits the
resulting events in proper seq order through the one Emitter.
"""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass, field
from typing import Any


@dataclass
class HuntHandle:
    hunt_id: str
    commands: asyncio.Queue[dict[str, Any]] = field(default_factory=asyncio.Queue)
    task: asyncio.Task | None = None


class HuntRegistry:
    def __init__(self) -> None:
        self._hunts: dict[str, HuntHandle] = {}

    def register(self, hunt_id: str) -> HuntHandle:
        handle = HuntHandle(hunt_id=hunt_id)
        self._hunts[hunt_id] = handle
        return handle

    def get(self, hunt_id: str) -> HuntHandle | None:
        return self._hunts.get(hunt_id)

    async def send(self, hunt_id: str, command: dict[str, Any]) -> bool:
        """Queue a command for a live hunt. False if the hunt isn't running here."""
        handle = self._hunts.get(hunt_id)
        if handle is None:
            return False
        await handle.commands.put(command)
        return True

    async def shutdown(self) -> None:
        """Cancel every running Supervisor task (lifespan shutdown)."""
        for handle in self._hunts.values():
            if handle.task is not None and not handle.task.done():
                handle.task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await handle.task
        self._hunts.clear()
