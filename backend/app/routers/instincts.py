"""Instinct (saved plan preset) routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.db.repo import Repo
from app.dependencies import _accepted, get_repo
from app.engine.ids import new_instinct_id
from app.schemas import (
    InstinctCreatedResponse,
    InstinctDeleteResponse,
    InstinctItem,
    InstinctPatch,
    InstinctPatchResponse,
    InstinctsListResponse,
    SaveInstinct,
)

router = APIRouter(prefix="/instincts", tags=["instincts"])


@router.get("", response_model=InstinctsListResponse)
async def list_instincts(repo: Repo = Depends(get_repo)) -> dict:
    return {"instincts": await repo.list_instincts()}


@router.post("", status_code=202, response_model=InstinctCreatedResponse)
async def save_instinct(body: SaveInstinct, repo: Repo = Depends(get_repo)) -> JSONResponse:
    instinct_id = new_instinct_id()
    await repo.save_instinct(instinct_id, body.label, body.spec)
    return _accepted({"instinct_id": instinct_id, "accepted": True})


@router.get("/{instinct_id}", response_model=InstinctItem)
async def get_instinct(instinct_id: str, repo: Repo = Depends(get_repo)) -> JSONResponse:
    inst = await repo.get_instinct(instinct_id)
    if inst is None:
        return JSONResponse(status_code=404, content={"detail": "instinct not found"})
    return JSONResponse(content=inst)


@router.patch("/{instinct_id}", response_model=InstinctPatchResponse)
async def patch_instinct(
    instinct_id: str, body: InstinctPatch, repo: Repo = Depends(get_repo)
) -> JSONResponse:
    """Rename a saved instinct or replace its formation/spec."""
    ok = await repo.update_instinct(instinct_id, body.label, body.spec)
    if not ok:
        return JSONResponse(status_code=404, content={"detail": "instinct not found"})
    return JSONResponse({"instinct_id": instinct_id, "ok": True})


@router.delete("/{instinct_id}", response_model=InstinctDeleteResponse)
async def delete_instinct(instinct_id: str, repo: Repo = Depends(get_repo)) -> JSONResponse:
    ok = await repo.delete_instinct(instinct_id)
    if not ok:
        return JSONResponse(status_code=404, content={"detail": "instinct not found"})
    return JSONResponse({"instinct_id": instinct_id, "deleted": True})
