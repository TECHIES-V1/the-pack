"""Configuration — loaded from the environment, never hard-coded (Doc 04 §04).

Real model names, the region endpoint, and all secrets live in .env / the environment,
not in code. Verify the real Qwen model names in Model Studio on day 1 (F14).
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Qwen / Model Studio (OpenAI-compatible endpoint, region nearest Nigeria — D6).
    qwen_api_key: str = ""
    qwen_base_url: str = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    qwen_region: str = "ap-southeast-1"

    # Model-tier registry — pinned to what dashscope-intl serves, verified on a real key to accept
    # enable_thinking + prompt-JSON (Phase 1). The intl region exposes a dated snapshot for `plus`
    # but only floating aliases for `max`/`flash`, so those stay aliases. All are .env-overridable.
    qwen_model_max: str = "qwen-max"
    qwen_model_plus: str = "qwen-plus-2025-12-01"
    qwen_model_flash: str = "qwen-flash"
    qwen_model_vision: str = "qwen-vl-max"  # multimodal — reads images (Qwen-VL)

    # Voice (transcription) — access checked now, contract freezes Jun 16.
    qwen_voice_api_key: str = ""
    qwen_voice_base_url: str = ""
    qwen_voice_model: str = "paraformer-realtime-v2"

    # Seam + durable store.
    redis_url: str = "redis://localhost:6379/0"
    postgres_url: str = "postgresql://pack:pack@localhost:5432/pack"
    # Cloud Postgres (ApsaraDB RDS) usually wants TLS. Empty = no TLS (local Docker). Set to a
    # libpq sslmode — "require" (encrypt, no cert check) or "verify-full" (with a CA) — for prod.
    postgres_sslmode: str = ""

    # App.
    session_secret: str = "change-me-in-prod"
    engine_host: str = "0.0.0.0"
    engine_port: int = 8000

    # Boundary.
    first_hunt_cap_usd: float = 0.50

    # A wolf's single dispatch may not exceed this wall-clock before it's ruled a Stray and
    # rerouted (anomaly path — generous so only true hangs trip it).
    step_timeout_s: float = 120.0

    # Web search (real research). An empty key falls back to the deterministic canned
    # provider, so the whole engine still runs offline end to end (Doc 04 §07).
    search_provider: str = "tavily"
    search_api_key: str = ""  # Tavily (the primary web-search vendor)
    search_max_results: int = 8
    search_cache_ttl_s: float = 3600.0  # reuse identical searches/URL reads within the window

    # Multi-source research — every provider with a key present joins the fan-out; keyless ones
    # (Hacker News, Wikidata, DBpedia, OpenAlex) always run. ALL empty → canned offline provider.
    exa_api_key: str = ""
    serpapi_api_key: str = ""
    youcom_api_key: str = ""
    newsapi_key: str = ""
    gnews_api_key: str = ""
    newsdata_api_key: str = ""
    jina_api_key: str = ""
    firecrawl_api_key: str = ""
    apify_api_key: str = ""
    core_api_key: str = ""
    github_token: str = ""
    google_kg_api_key: str = ""
    openalex_mailto: str = ""

    # Research strategy — the selectable engine modes. ORTHOGONAL to the autonomy `mode`
    # (wild | on_signal | on_command): strategy shapes the plan, mode shapes execution.
    # One of: orchestrate | deep_dive | critique.
    default_strategy: str = "orchestrate"

    # Pricing — USD per 1M tokens (input, output) per tier. Placeholders in the right ballpark
    # for Qwen on Model Studio; confirm real numbers when the key lands and override via env.
    price_max_in_per_m: float = 1.60
    price_max_out_per_m: float = 6.40
    price_plus_in_per_m: float = 0.40
    price_plus_out_per_m: float = 1.20
    price_flash_in_per_m: float = 0.10
    price_flash_out_per_m: float = 0.40

    # LLM client resilience.
    qwen_max_retries: int = 3
    qwen_backoff_base_s: float = 0.5
    qwen_breaker_threshold: int = 5  # consecutive failures before the breaker opens
    qwen_breaker_cooldown_s: float = 30.0


settings = Settings()

# Tier name -> configured model id. The Qwen client resolves tiers through this.
TIER_REGISTRY = {
    "max": settings.qwen_model_max,
    "plus": settings.qwen_model_plus,
    "flash": settings.qwen_model_flash,
}
