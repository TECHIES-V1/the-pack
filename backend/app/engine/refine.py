"""Refine the Reward (v5 A3) — re-draft + re-forge a returned hunt's brief from its stored claims
and sources, NO re-scout. One Howler call + the Forge, emitted on the existing event spine so the
canvas updates. Reconstructs from the final artifact (the hunt's Supervisor is long gone).
"""

from __future__ import annotations

import base64

from app.engine.core import Emitter
from app.engine.forge import MIME, forge
from app.engine.ids import new_artifact_id
from app.engine.strategies.base import DRAFT_SCHEMA
from app.qwen.client import QwenClient
from app.qwen.types import CallSpec

_REFINE_SYSTEM = (
    "You are Howler, the Pack's writer. Re-draft the briefing tighter and clearer, honoring the "
    "Packmaster's instruction. Cite ONLY the listed sources by number."
)


def _blocks_from(parsed: dict | None, text: str, sources: list[dict]) -> list[dict]:
    """Normalize Howler's tagged output into [{text, source_ids}] (mirror of the Supervisor's)."""
    parsed = parsed or {}
    out: list[dict] = []
    title = str(parsed.get("title") or "").strip()
    if title:
        out.append({"text": f"# {title}", "source_ids": []})
    for b in parsed.get("blocks") or []:
        if not isinstance(b, dict):
            continue
        body = str(b.get("text") or "").strip()
        if not body:
            continue
        ids = [
            int(i)
            for i in (b.get("source_ids") or [])
            if isinstance(i, int | float) and 1 <= int(i) <= len(sources)
        ]
        out.append({"text": body, "source_ids": sorted(set(ids))})
    if not any(b["text"] and not b["text"].startswith("# ") for b in out):
        out.append({"text": (text or "").strip(), "source_ids": list(range(1, len(sources) + 1))})
    return out


async def refine_brief(repo, client: QwenClient, hunt_id: str, instruction: str) -> str | None:
    """Re-draft + re-forge. Returns the new final artifact id, or None if nothing to refine."""
    art = await repo.get_final_artifact(hunt_id)
    content = (art or {}).get("content") or {}
    sources = content.get("sources") or []
    if not sources:
        return None  # no sourced ground → nothing to refine

    claims = content.get("claims") or []
    numbered = "\n".join(
        f"[{i + 1}] {s.get('title') or s.get('url') or ''}" for i, s in enumerate(sources)
    )
    user = (
        f"Refine this briefing. {instruction or 'Tighten it and sharpen the framing.'}\n\n"
        + ("Claims:\n" + "\n".join(f"- {c}" for c in claims) + "\n\n" if claims else "")
        + f"Sources (cite each block by number):\n{numbered}\n\n"
        "Respond with ONLY JSON: a `title` and `blocks` array of {text, source_ids}."
    )
    res = await client.complete(
        CallSpec(
            hunt_id=hunt_id,
            wolf_id="howler",
            tier="plus",
            intent="draft",
            response_schema=DRAFT_SCHEMA,
            messages=[
                {"role": "system", "content": _REFINE_SYSTEM},
                {"role": "user", "content": user},
            ],
        )
    )
    blocks = _blocks_from(res.parsed, res.text, sources)

    emitter = Emitter(hunt_id, repo)
    await emitter.emit("forge_started", "howler", {"formats": list(MIME)})
    artifact_id = new_artifact_id()
    await repo.save_artifact(
        artifact_id,
        hunt_id,
        "final",
        "howler",
        {
            "text": "\n\n".join(b["text"] for b in blocks),
            "blocks": blocks,
            "claims": claims,
            "sources": sources,
            "no_sources": False,
            "refined": True,
        },
    )
    await emitter.emit(
        "artifact_created",
        "howler",
        {"artifact_id": artifact_id, "kind": "final", "produced_by": "howler"},
    )
    for fmt, data in forge(blocks, sources).items():
        fid = new_artifact_id()
        await repo.save_artifact(
            fid,
            hunt_id,
            fmt,
            "howler",
            {
                "mime": MIME.get(fmt, "application/octet-stream"),
                "b64": base64.b64encode(data).decode(),
            },
        )
        await emitter.emit(
            "artifact_created", "howler", {"artifact_id": fid, "kind": fmt, "produced_by": "howler"}
        )
    await emitter.emit("forge_completed", "howler", {"formats": list(MIME)})
    return artifact_id
