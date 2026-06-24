"""Audio transcription — turn uploaded audio into text (Doc 04 §07, F14).

A `Transcriber` turns audio bytes into a transcript. `QwenTranscriber` calls DashScope's ASR
through the configured voice endpoint (OpenAI-compatible `audio/transcriptions`); the offline
`FakeTranscriber` returns a deterministic placeholder so the system runs with no voice key.
Chosen by config: a real `qwen_voice_api_key` selects Qwen, otherwise Canned/Fake. Same seam
as SearchProvider — swap the body, nothing upstream changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.config import settings


@dataclass
class Transcript:
    text: str
    provider: str  # qwen_voice | qwen_asr (schema enum) — Fake maps to qwen_asr
    duration_s: float


class Transcriber(Protocol):
    name: str

    async def transcribe(self, data: bytes, *, content_type: str = "") -> Transcript: ...


class FakeTranscriber:
    """Deterministic offline stand-in — proves the wiring without a voice key."""

    name = "fake"

    async def transcribe(self, data: bytes, *, content_type: str = "") -> Transcript:
        # ~16 kHz 16-bit mono ≈ 32 KB/s; a rough, deterministic duration from the byte length.
        duration = round(len(data) / 32_000, 2)
        return Transcript(
            text="[offline transcript — audio received; add a voice key for real transcription]",
            provider="qwen_asr",
            duration_s=duration,
        )


class QwenTranscriber:
    """DashScope ASR via the OpenAI-compatible audio endpoint. Best-effort: the exact model id
    is config-driven (the voice contract froze late)."""

    name = "qwen_voice"

    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model

    async def transcribe(self, data: bytes, *, content_type: str = "") -> Transcript:
        import httpx

        url = f"{self._base_url}/audio/transcriptions"
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                url,
                headers={"Authorization": f"Bearer {self._api_key}"},
                files={"file": ("audio", data, content_type or "audio/wav")},
                data={"model": self._model},
            )
            resp.raise_for_status()
            body = resp.json()
        text = str(body.get("text") or "").strip()
        return Transcript(text=text, provider="qwen_voice", duration_s=float(body.get("duration", 0.0) or 0.0))


def make_transcriber() -> Transcriber:
    if settings.qwen_voice_api_key and settings.qwen_voice_base_url:
        return QwenTranscriber(
            settings.qwen_voice_api_key, settings.qwen_voice_base_url, settings.qwen_voice_model
        )
    return FakeTranscriber()


TRANSCRIBER: Transcriber = make_transcriber()
