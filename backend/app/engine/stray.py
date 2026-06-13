"""Stray detection — sliding-window heuristics per wolf (Doc 04 §04, F10).

Triggers:
  * the same tool failing 3 times,
  * an output-similarity loop over 3 turns,
  * a step wall-clock timeout.

On trigger: cancel the task, let Alpha replan / reroute / respawn, and emit the
stray_detected -> stray_recovered pair with a plain-English note (template + light LLM
polish). See fixtures/standoff_stray.jsonl for the expected sequence.

Scaffold: the detector tracks per-wolf signals; the engine feeds it tool results and step
timings. Returns the detected pattern (or None).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

REPEAT_FAIL_THRESHOLD = 3
LOOP_THRESHOLD = 3


@dataclass
class StrayDetector:
    _fails: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    _recent_outputs: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))

    def record_tool_result(self, wolf_id: str, ok: bool) -> str | None:
        """Returns 'repeat_fail' once a wolf has failed the same tool 3 times."""
        if ok:
            self._fails[wolf_id] = 0
            return None
        self._fails[wolf_id] += 1
        if self._fails[wolf_id] >= REPEAT_FAIL_THRESHOLD:
            return "repeat_fail"
        return None

    def record_output(self, wolf_id: str, fingerprint: str) -> str | None:
        """Returns 'loop' when the last 3 outputs repeat (similarity loop)."""
        window = self._recent_outputs[wolf_id]
        window.append(fingerprint)
        if len(window) > LOOP_THRESHOLD:
            window.pop(0)
        if len(window) == LOOP_THRESHOLD and len(set(window)) == 1:
            return "loop"
        return None
