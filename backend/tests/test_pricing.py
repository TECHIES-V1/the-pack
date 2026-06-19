"""Pricing math + the offline provider — both run with no key and no network."""

from __future__ import annotations

from app.qwen import pricing
from app.qwen.client import QwenClient
from app.qwen.types import CallSpec


def test_cost_is_tier_sensitive() -> None:
    # The same usage costs more on max than on flash.
    assert pricing.cost("max", 10_000, 5_000) > pricing.cost("flash", 10_000, 5_000)


def test_cost_zero_for_zero_tokens() -> None:
    assert pricing.cost("plus", 0, 0) == 0.0


def test_unknown_tier_falls_back_to_plus() -> None:
    assert pricing.cost("mystery", 1_000, 1_000) == pricing.cost("plus", 1_000, 1_000)


async def test_fake_provider_is_deterministic_and_priced() -> None:
    client = QwenClient()
    assert client.offline, "no QWEN_API_KEY in the test env, so the client must be offline"

    spec = CallSpec(hunt_id="h", wolf_id="scout-1", tier="flash", intent="search")
    r1 = await client.complete(spec)
    r2 = await client.complete(spec)

    assert r1 == r2, "the fake provider must be deterministic"
    assert r1.in_tokens > 0 and r1.out_tokens > 0
    assert r1.cost_usd > 0
    assert r1.cost_usd == pricing.cost("flash", r1.in_tokens, r1.out_tokens)
