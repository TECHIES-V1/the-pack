"""Memory and spend routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.db.repo import Repo
from app.dependencies import get_repo
from app.schemas import ClearedResponse, MemoryResponse, SpendResponse

router = APIRouter(tags=["memory"])


@router.get("/memory", response_model=MemoryResponse)
async def get_memory(repo: Repo = Depends(get_repo)) -> dict:
    """What the pack remembers across hunts (the Elder's takeaways), most recent first."""
    rows = await repo.recent_memory(10)
    return {
        "memory": [
            {"text": str(r.get("text") or ""), "hunt_id": r.get("hunt_id")}
            for r in rows
            if str(r.get("text") or "").strip()
        ]
    }


@router.delete("/memory", response_model=ClearedResponse)
async def clear_memory(repo: Repo = Depends(get_repo)) -> JSONResponse:
    """Forget everything the pack learned (wired to Settings → Clear all saved data)."""
    await repo.clear_memory()
    return JSONResponse({"cleared": True})


@router.get("/spend", tags=["hunts"], response_model=SpendResponse)
async def get_spend(repo: Repo = Depends(get_repo)) -> dict:
    """Total spend across all hunts + a per-hunt breakdown, read from each hunt's final totals."""
    items = await repo.spend_summary()
    return {"total_usd": round(sum(i["cost_usd"] for i in items), 4), "hunts": items}
