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

    # Model-tier registry (placeholders; confirm real names on day 1).
    qwen_model_max: str = "qwen-max"
    qwen_model_plus: str = "qwen-plus"
    qwen_model_flash: str = "qwen-flash"

    # Voice (transcription) — access checked now, contract freezes Jun 16.
    qwen_voice_api_key: str = ""
    qwen_voice_base_url: str = ""

    # Seam + durable store.
    redis_url: str = "redis://localhost:6379/0"
    postgres_url: str = "postgresql://pack:pack@localhost:5432/pack"

    # App.
    session_secret: str = "change-me-in-prod"
    engine_host: str = "0.0.0.0"
    engine_port: int = 8000

    # Boundary.
    first_hunt_cap_usd: float = 0.50


settings = Settings()

# Tier name -> configured model id. The Qwen client resolves tiers through this.
TIER_REGISTRY = {
    "max": settings.qwen_model_max,
    "plus": settings.qwen_model_plus,
    "flash": settings.qwen_model_flash,
}
