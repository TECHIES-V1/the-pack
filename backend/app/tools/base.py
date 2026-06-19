"""Tool contract (Doc 04 §04).

Every tool — web_search, web_fetch, file_parse, transcribe, artifact_write — speaks the same
shape: a `name` (one of the schema's tool enum) and an async `run(**kwargs) -> ToolResult`.
The Supervisor wraps each call in the same gate-and-emit envelope (tool_called →
tool_result, fed to the StrayDetector), so swapping a canned tool for a real one later
changes nothing upstream.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class ToolResult:
    ok: bool
    result_ref: str | None
    latency_ms: int
    data: Any = None


class Tool(Protocol):
    name: str

    async def run(self, **kwargs: Any) -> ToolResult: ...
