"""Token → USD pricing (Doc 04 §04).

The Boundary enforces a *dollar* budget, so every call's token usage must become a cost.
Rates are per-tier, per 1M tokens, sourced from config (env-overridable) — never hard-coded,
because the real Qwen numbers get confirmed in Model Studio when the key lands.
"""

from __future__ import annotations

from app.config import settings

# tier -> (input USD per 1M tokens, output USD per 1M tokens)
RATES: dict[str, tuple[float, float]] = {
    "max": (settings.price_max_in_per_m, settings.price_max_out_per_m),
    "plus": (settings.price_plus_in_per_m, settings.price_plus_out_per_m),
    "flash": (settings.price_flash_in_per_m, settings.price_flash_out_per_m),
}


def cost(tier: str, in_tokens: int, out_tokens: int) -> float:
    """USD for one call. Unknown tiers fall back to 'plus' (the safe middle)."""
    in_rate, out_rate = RATES.get(tier, RATES["plus"])
    usd = in_tokens / 1_000_000 * in_rate + out_tokens / 1_000_000 * out_rate
    return round(usd, 6)


# Typical per-call token footprint per tier, for the Boundary's PRE-dispatch estimate (it
# must project spend before the call, when the real usage isn't known yet).
_EST_TOKENS: dict[str, tuple[int, int]] = {
    "max": (40_000, 9_000),
    "plus": (85_000, 17_000),
    "flash": (60_000, 12_000),
}


def estimate(tier: str) -> float:
    """Projected USD for one call on this tier — what the gate checks before dispatch."""
    in_tokens, out_tokens = _EST_TOKENS.get(tier, _EST_TOKENS["plus"])
    return cost(tier, in_tokens, out_tokens)
