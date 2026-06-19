"""Prompt loader — read the wolf prompts from prompts/<role>/v1.md (Doc 04 §04).

Each prompt file carries a small frontmatter block (wolf, role, model_tier, thinking,
version, structured_output) above the Markdown body. We hand-parse it — no YAML dependency
for five obvious keys. The Supervisor uses this to spawn each wolf on the right tier with
the right thinking mode and to stamp `prompt_version` on the wolf_spawned event.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

_TRUTHY = {"on", "true", "yes", "1"}


@dataclass
class Prompt:
    role: str
    version: str
    model_tier: str  # max | plus | flash
    thinking: bool
    body: str
    meta: dict[str, str] = field(default_factory=dict)


def _split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    meta: dict[str, str] = {}
    i = 1
    while i < len(lines) and lines[i].strip() != "---":
        if ":" in lines[i]:
            key, _, val = lines[i].partition(":")
            meta[key.strip()] = val.strip()
        i += 1
    body = "\n".join(lines[i + 1 :]).strip()
    return meta, body


@cache
def load_prompt(role: str) -> Prompt:
    path = PROMPTS_DIR / role / "v1.md"
    meta, body = _split_frontmatter(path.read_text(encoding="utf-8"))
    return Prompt(
        role=role,
        version=meta.get("version", f"{role}/v1"),
        model_tier=meta.get("model_tier", "plus"),
        thinking=meta.get("thinking", "off").lower() in _TRUTHY,
        body=body,
        meta=meta,
    )
