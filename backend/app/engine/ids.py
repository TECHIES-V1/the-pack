"""ULID id helpers — one prefix per entity kind (Doc 04 §3).

Ids are sortable (ULIDs embed a timestamp) and human-greppable by prefix: hunt_, art_,
hold_, etc. The event_id default lives on the Event model itself; everything else is here.
"""

from __future__ import annotations

from ulid import ULID


def new_hunt_id() -> str:
    return f"hunt_{ULID()}"


def new_artifact_id() -> str:
    return f"art_{ULID()}"


def new_hold_id() -> str:
    return f"hold_{ULID()}"


def new_standoff_id() -> str:
    return f"standoff_{ULID()}"


def new_checkpoint_id() -> str:
    return f"ckpt_{ULID()}"


def new_instinct_id() -> str:
    return f"instinct_{ULID()}"


def new_project_id() -> str:
    return f"proj_{ULID()}"
