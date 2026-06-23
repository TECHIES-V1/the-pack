"""Image understanding via Qwen-VL (multimodal).

Mirrors the offline switch used everywhere else: with no `QWEN_API_KEY` we return a deterministic
stub so the whole parse → research pipeline still runs without a key. With a key, we ask Qwen-VL to
transcribe any text and describe the visual content, returning plain text — like a parsed PDF.
"""

from __future__ import annotations

import base64

from app.config import settings

_PROMPT = (
    "Read this image for a researcher. Transcribe any text verbatim, then briefly describe charts, "
    "tables, diagrams, or other key visual content. Return plain text only — no preamble."
)


async def describe_image(data: bytes, mime: str = "", filename: str = "") -> str:
    if not settings.qwen_api_key:
        return (
            f"[offline — image '{filename or 'upload'}' received ({len(data)} bytes). "
            "Add a Qwen key for real image reading.]"
        )
    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=settings.qwen_api_key, base_url=settings.qwen_base_url)
        b64 = base64.b64encode(data).decode("ascii")
        url = f"data:{mime or 'image/png'};base64,{b64}"
        res = await client.chat.completions.create(
            model=settings.qwen_model_vision,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": _PROMPT},
                        {"type": "image_url", "image_url": {"url": url}},
                    ],
                }
            ],
        )
        out = (res.choices[0].message.content or "").strip()
        return out or "[no readable content in the image]"
    except Exception as exc:  # noqa: BLE001 — degrade to a note, never raise into the request
        return f"[could not read the image: {exc}]"
