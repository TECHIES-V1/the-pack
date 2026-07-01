"""System routes — health probes and strategy catalog."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.config import settings
from app.dependencies import get_bus, get_pool
from app.engine.strategies import strategy_catalog
from app.schemas import HealthResponse, ReadyResponse, StrategiesResponse

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
async def health(pool=Depends(get_pool), bus=Depends(get_bus)) -> JSONResponse:
    """Liveness + dependency probe: pings Postgres and Redis so a probe sees 'degraded', not a
    false 'ok', when a backing service is down."""
    detail: dict = {"status": "ok", "service": "pack-engine"}
    try:
        await pool.fetchval("SELECT 1")
    except Exception as exc:  # noqa: BLE001
        detail.update(status="degraded", postgres=f"down: {exc}")
    try:
        await bus.ping()
    except Exception as exc:  # noqa: BLE001
        detail.update(status="degraded", redis=f"down: {exc}")
    code = 200 if detail["status"] == "ok" else 503
    return JSONResponse(status_code=code, content=detail)


@router.get("/ready", response_model=ReadyResponse)
async def ready(pool=Depends(get_pool)) -> JSONResponse:
    """Readiness probe — 503 until Postgres answers (the engine can't serve without it)."""
    try:
        await pool.fetchval("SELECT 1")
    except Exception:  # noqa: BLE001
        return JSONResponse(status_code=503, content={"ready": False})
    return JSONResponse({"ready": True})


@router.get("/strategies", response_model=StrategiesResponse)
async def strategies() -> dict:
    """The selectable research strategies (the Door's mode picker)."""
    return {"strategies": strategy_catalog(), "default": settings.default_strategy}
