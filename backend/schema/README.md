# Event schema v1 — the spine

`events.schema.json` is the **frozen** contract (Doc 04 §3, target freeze June 12). It is
the single source of truth and the frontend↔backend seam. Treat it like a public API.

## Rules (Doc 04 §3.1)

- `seq` is strictly increasing **per hunt**.
- Events are **append-only**. They are never edited.
- The stream replays from `seq=0` or from any checkpoint.
- Every wolf and engine action emits. **If it is not an event, it did not happen.**

## The envelope

```json
{ "event_id": "evt_01J...", "hunt_id": "hunt_01J...", "seq": 142,
  "ts": "2026-06-12T10:04:31.221Z", "type": "step_started",
  "actor": "scout-2", "payload": { } }
```

## Consumers of this one stream

The Territory, the Activity Feed, Tracks, the Boundary meter, Stray detection, and the
Lone-Wolf benchmark all read the **same** stream. Build one, get all six.

## Source of truth & codegen

- Backend mirrors this as Pydantic v2 models in `backend/app/events/models.py`.
- Frontend mirrors the envelope + reducer types in `frontend/src/events/`.
- The fixture pack in `fixtures/` is validated against this schema in CI
  (`backend/tests/test_contract.py`). **The fixtures stay green.**

## Changing the schema

A schema change is a pull request that updates: this file, the Pydantic models, the
frontend types, and any affected fixtures — together, in one PR. After June 12 the bar is
high; additive-only where possible.
