"""Video → audio (v5.7). Pull a clip's audio track so the Transcriber can turn it into text.

Uses the ffmpeg binary bundled with `imageio-ffmpeg` (no system install, Windows-safe). The decode
runs in a worker thread so it never blocks the event loop. Best-effort: returns b"" on any failure,
so a bad clip degrades to "no text" rather than crashing the upload.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import tempfile


def _extract_sync(data: bytes) -> bytes:
    from imageio_ffmpeg import get_ffmpeg_exe

    ffmpeg = get_ffmpeg_exe()
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "in")
        out = os.path.join(d, "out.mp3")
        with open(src, "wb") as f:
            f.write(data)
        try:
            subprocess.run(
                [ffmpeg, "-y", "-i", src, "-vn", "-acodec", "libmp3lame", "-b:a", "96k", out],
                capture_output=True,
                timeout=120,
                check=True,
            )
        except Exception:  # noqa: BLE001 — bad/garbled clip; caller falls back to "no text"
            return b""
        try:
            with open(out, "rb") as f:
                return f.read()
        except OSError:
            return b""


async def extract_audio(data: bytes) -> bytes:
    """Return the clip's audio as mp3 bytes (b"" if it can't be decoded)."""
    return await asyncio.to_thread(_extract_sync, data)
