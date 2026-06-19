"""hello-qwen — confirm the key, base URL, and real model names (gate box 2 / F14).

Runs a tiny real call per tier and one thinking+streaming call. Only does anything when
QWEN_API_KEY is set; offline it just reminds you the system uses FakeQwen.

    python scripts/hello_qwen.py
"""

from __future__ import annotations

import asyncio

from app.config import TIER_REGISTRY, settings
from app.qwen.client import QwenClient
from app.qwen.types import CallSpec


async def main() -> None:
    if not settings.qwen_api_key:
        print("No QWEN_API_KEY set — nothing to smoke-test. Offline mode uses FakeQwen.")
        return

    client = QwenClient()
    print(f"base_url={settings.qwen_base_url}  region={settings.qwen_region}")

    for tier in ("flash", "plus", "max"):
        spec = CallSpec(
            hunt_id="hello",
            wolf_id="probe",
            tier=tier,
            messages=[{"role": "user", "content": "Reply with the single word: pack"}],
        )
        r = await client.complete(spec)
        print(f"  {tier:5} ({TIER_REGISTRY[tier]}): {r.text!r}")
        print(f"        in={r.in_tokens} out={r.out_tokens} ${r.cost_usd}")

    # The gotcha: thinking ON requires streaming. Prove it works end to end.
    spec = CallSpec(
        hunt_id="hello",
        wolf_id="probe",
        tier="max",
        thinking=True,
        messages=[{"role": "user", "content": "Think briefly, then reply: ok"}],
    )
    r = await client.complete(spec)
    print(f"  thinking+stream ok: {r.text!r}  in={r.in_tokens} out={r.out_tokens}")


if __name__ == "__main__":
    asyncio.run(main())
