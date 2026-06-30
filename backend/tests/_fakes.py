"""In-memory test doubles — let the engine run with no Postgres and no Redis.

`FakeRepo` mimics the parts of `app.db.repo.Repo` the Emitter and Supervisor touch, keeping
events in a dict and rejecting duplicate seq the way the real (hunt_id, seq) primary key
would. `CollectingBus` mimics `EventBus.append` by appending to a list. Together they make
the seq/emitter/offline-hunt tests run instantly, with no infrastructure.
"""

from __future__ import annotations

from typing import Any

from app.events.models import Event


class FakeRepo:
    def __init__(self) -> None:
        self.events: dict[str, list[Event]] = {}
        self.hunts: dict[str, dict[str, Any]] = {}
        self.artifacts: list[dict[str, Any]] = []
        self.memory: list[dict[str, Any]] = []
        self.documents: list[dict[str, Any]] = []
        self.instincts: list[dict[str, Any]] = []
        self.feedback: list[dict[str, Any]] = []
        self.projects: list[dict[str, Any]] = []

    async def save_memory(self, hunt_id: str | None, kind: str, text: str) -> None:
        self.memory.append({"hunt_id": hunt_id, "kind": kind, "text": text})

    async def recent_memory(self, limit: int = 5) -> list[dict[str, Any]]:
        return list(reversed(self.memory))[:limit]

    async def save_document(self, name: str, kind: str, text: str) -> int:
        doc_id = len(self.documents) + 1
        self.documents.append(
            {"id": doc_id, "name": name, "kind": kind, "text": text, "chars": len(text)}
        )
        return doc_id

    async def list_documents(self, *, with_text: bool = False) -> list[dict[str, Any]]:
        out = []
        for d in reversed(self.documents):
            row = {"id": d["id"], "name": d["name"], "kind": d["kind"], "chars": d["chars"]}
            if with_text:
                row["text"] = d["text"]
            out.append(row)
        return out

    async def get_document(self, doc_id: int) -> dict[str, Any] | None:
        return next((d for d in self.documents if d["id"] == doc_id), None)

    async def delete_document(self, doc_id: int) -> None:
        self.documents = [d for d in self.documents if d["id"] != doc_id]

    async def save_feedback(self, hunt_id: str, turn_index: int, vote: str) -> None:
        self.feedback.append({"hunt_id": hunt_id, "turn_index": turn_index, "vote": vote})

    async def feedback_for_hunt(self, hunt_id: str) -> dict[str, Any]:
        votes = [
            {"turn_index": f["turn_index"], "vote": f["vote"]}
            for f in self.feedback
            if f["hunt_id"] == hunt_id
        ]
        up = sum(1 for v in votes if v["vote"] == "up")
        return {"votes": votes, "up": up, "down": len(votes) - up}

    async def create_project(self, project_id: str, label: str, instructions: str | None) -> None:
        self.projects.append(
            {"project_id": project_id, "label": label, "instructions": instructions}
        )

    async def get_project(self, project_id: str) -> dict[str, Any] | None:
        return next((p for p in self.projects if p["project_id"] == project_id), None)

    async def clear_documents(self) -> None:
        self.documents = []

    async def clear_memory(self) -> None:
        self.memory = []

    async def list_hunts(
        self, limit: int = 50, project_id: str | None = None, cursor: str | None = None
    ) -> list[dict[str, Any]]:
        return [
            {
                "hunt_id": hid,
                "title": h.get("raw_input") or hid,
                "state": h.get("state", "draft"),
                "source": h.get("source", "typed"),
                "boundary_usd": None,
                "project_id": None,
                "created_at": "2026-01-01T00:00:00Z",
            }
            for hid, h in self.hunts.items()
        ]

    async def spend_summary(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for hid, evs in self.events.items():
            for e in evs:
                if e.type == "hunt_completed":
                    cost = round(float((e.payload.get("totals") or {}).get("cost_usd") or 0), 4)
                    if cost > 0:
                        title = (self.hunts.get(hid, {}) or {}).get("raw_input") or hid
                        out.append({"hunt_id": hid, "title": title, "cost_usd": cost})
        out.sort(key=lambda x: x["cost_usd"], reverse=True)
        return out

    async def create_hunt(
        self, hunt_id: str, source: str, raw_input: str | None, strategy: str = "orchestrate"
    ) -> None:
        self.hunts[hunt_id] = {
            "state": "planning",
            "source": source,
            "raw_input": raw_input,
            "strategy": strategy,
        }

    async def set_hunt_state(self, hunt_id: str, state: str) -> None:
        self.hunts.setdefault(hunt_id, {})["state"] = state

    async def set_boundary(self, hunt_id: str, boundary_usd: float) -> None:
        self.hunts.setdefault(hunt_id, {})["boundary_usd"] = boundary_usd

    async def get_last_seq(self, hunt_id: str) -> int:
        evs = self.events.get(hunt_id, [])
        return evs[-1].seq if evs else -1

    async def append_event(self, event: Event) -> None:
        evs = self.events.setdefault(event.hunt_id, [])
        if any(e.seq == event.seq for e in evs):
            raise ValueError(f"duplicate seq {event.seq} for {event.hunt_id}")
        evs.append(event)

    async def save_artifact(
        self, artifact_id: str, hunt_id: str, kind: str, produced_by: str | None, content: Any
    ) -> None:
        self.artifacts.append(
            {
                "artifact_id": artifact_id,
                "hunt_id": hunt_id,
                "kind": kind,
                "produced_by": produced_by,
                "content": content,
            }
        )

    async def get_final_artifact(self, hunt_id: str) -> dict[str, Any] | None:
        finals = [a for a in self.artifacts if a["hunt_id"] == hunt_id and a["kind"] == "final"]
        return finals[-1] if finals else None

    async def save_checkpoint(
        self, checkpoint_id: str, hunt_id: str, at_seq: int, state: Any
    ) -> None:
        pass

    async def list_instincts(self) -> list[dict[str, Any]]:
        return list(reversed(self.instincts))

    async def get_instinct(self, instinct_id: str) -> dict[str, Any] | None:
        return next((i for i in self.instincts if i["instinct_id"] == instinct_id), None)

    async def save_instinct(self, instinct_id: str, label: str, spec: dict[str, Any]) -> None:
        self.instincts.append({"instinct_id": instinct_id, "label": label, "spec": spec})

    async def update_instinct(
        self, instinct_id: str, label: str | None, spec: dict[str, Any] | None
    ) -> bool:
        for i in self.instincts:
            if i["instinct_id"] == instinct_id:
                if label is not None:
                    i["label"] = label
                if spec is not None:
                    i["spec"] = spec
                return True
        return False

    async def delete_instinct(self, instinct_id: str) -> bool:
        before = len(self.instincts)
        self.instincts = [i for i in self.instincts if i["instinct_id"] != instinct_id]
        return len(self.instincts) < before

    def all_events(self, hunt_id: str) -> list[Event]:
        return self.events.get(hunt_id, [])

    async def replay_events(self, hunt_id: str, from_seq: int = 0) -> list[Event]:
        return [e for e in self.events.get(hunt_id, []) if e.seq >= from_seq]


class CollectingBus:
    """Stands in for EventBus — records what the relay would publish to Redis."""

    def __init__(self) -> None:
        self.published: list[Event] = []

    async def append(self, event: Event) -> str:
        self.published.append(event)
        return f"{event.seq}-0"


class FakeQwenBad:
    """FakeQwen variant with configurable failure modes for resilience tests.

    Usage::

        bad = FakeQwenBad(fail_on_call=2, mode="rate_limit")
        monkeypatch.setattr(client, "_fake", bad)
    """

    def __init__(
        self,
        *,
        fail_on_call: int = 0,
        mode: str = "none",
    ) -> None:
        from app.qwen.fake import FakeQwen

        self._delegate = FakeQwen()
        self._calls = 0
        self._fail_on = fail_on_call
        self._mode = mode  # "none" | "bad_json" | "rate_limit" | "null_parsed"

    async def complete(self, spec, on_delta=None):
        from openai import RateLimitError

        from app.qwen.types import CompletionResult

        self._calls += 1
        if self._fail_on and self._calls == self._fail_on:
            if self._mode == "rate_limit":
                raise RateLimitError(
                    "rate limit hit (injected by FakeQwenBad)",
                    response=None,  # type: ignore[arg-type]
                    body=None,
                )
            if self._mode == "null_parsed":
                result = await self._delegate.complete(spec, on_delta)
                return CompletionResult(
                    text=result.text,
                    model=result.model,
                    tier=result.tier,
                    in_tokens=result.in_tokens,
                    out_tokens=result.out_tokens,
                    cost_usd=result.cost_usd,
                    parsed=None,
                )
            if self._mode == "bad_json":
                result = await self._delegate.complete(spec, on_delta)
                return CompletionResult(
                    text="Here is the answer: ```not valid json```",
                    model=result.model,
                    tier=result.tier,
                    in_tokens=result.in_tokens,
                    out_tokens=result.out_tokens,
                    cost_usd=result.cost_usd,
                    parsed=None,
                )
        return await self._delegate.complete(spec, on_delta)
