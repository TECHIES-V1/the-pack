"""PII redaction for the Tracks export (Doc 04).

Regex-based masking applied to event payloads before the audit log leaves the box: emails,
phone numbers, long digit runs (card/account-like), and secret-ish tokens. Deliberately
conservative — it over-masks rather than leak. The event log itself is never mutated; only the
exported copy is redacted.
"""

from __future__ import annotations

import re
from typing import Any

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_CARD = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")
_PHONE = re.compile(r"(?<!\d)\+?\d[\d\s().-]{7,}\d(?!\d)")
_TOKEN = re.compile(r"\b(?:sk-[A-Za-z0-9]{6,}|[A-Za-z0-9_-]{32,})\b")


def redact_text(text: str) -> str:
    text = _EMAIL.sub("[email]", text)
    text = _CARD.sub("[redacted-number]", text)
    text = _PHONE.sub("[phone]", text)
    text = _TOKEN.sub("[token]", text)
    return text


def redact_value(value: Any) -> Any:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        return {k: redact_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_value(v) for v in value]
    return value


def redact_event(event: dict) -> dict:
    """Return a copy of the event with its payload redacted."""
    out = dict(event)
    if isinstance(out.get("payload"), dict):
        out["payload"] = redact_value(out["payload"])
    return out
