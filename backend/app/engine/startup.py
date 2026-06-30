"""Engine startup helpers — called from the FastAPI lifespan, not from route code."""
from __future__ import annotations

import asyncio
import logging

from fastapi import FastAPI

from app.db.repo import Repo
from app.engine.core import Emitter
from app.engine.registry import HuntRegistry
from app.events.models import Event

_RESTART_REASON = "The engine restarted before this hunt could finish — start a new one."

logger = logging.getLogger("pack")


async def recover_stranded_hunts(app: FastAPI, repo: Repo) -> None:
    """A previous engine stop leaves in-flight hunts with no Supervisor (state lived in-process).
    On startup:
    - `halted_boundary` → RE-REGISTERED and resumed (B11): rebuilds from the event log and
      waits for the Packmaster's /resume command.
    - Any other in-flight state → closed with an honest `hunt_failed`.
    Best-effort — never blocks startup; a bad row is skipped."""
    try:
        stranded = await repo.list_unfinished_hunts()
    except Exception:  # noqa: BLE001
        logger.exception("stranded-hunt recovery failed to list; skipping")
        return

    # Import here to avoid a circular dependency at module level
    from app.engine.supervisor import Supervisor

    registry: HuntRegistry = app.state.registry
    for h in stranded:
        hid = h["hunt_id"]
        try:
            if h.get("state") == "halted_boundary":
                handle = registry.register(hid)
                sup = Supervisor(hid, Emitter(hid, repo), repo, app.state.client, handle.commands)
                handle.task = asyncio.create_task(sup.resume_run(), name=f"resume-{hid}")
                logger.info("re-registered halted hunt %s for resume", hid)
                continue
            seq = (await repo.get_last_seq(hid)) + 1
            await repo.append_event(
                Event(
                    hunt_id=hid,
                    seq=seq,
                    type="hunt_failed",
                    actor="engine",
                    payload={"reason": "engine_restarted", "reason_plain_english": _RESTART_REASON},
                )
            )
            await repo.set_hunt_state(hid, "failed")
        except Exception:  # noqa: BLE001
            logger.warning("could not reconcile stranded hunt %s", hid)
            continue
