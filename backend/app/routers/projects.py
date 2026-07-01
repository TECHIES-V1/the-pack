"""Project (workspace) routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.db.repo import Repo
from app.dependencies import get_repo
from app.engine.ids import new_project_id
from app.schemas import (
    ProjectCreatedResponse,
    ProjectDeleteResponse,
    ProjectIn,
    ProjectPatch,
    ProjectPatchResponse,
    ProjectResponse,
    ProjectsListResponse,
)

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=ProjectsListResponse)
async def list_projects(repo: Repo = Depends(get_repo)) -> dict:
    """All projects with their (non-archived) hunt counts — powers the Den's project switcher."""
    return {"projects": await repo.list_projects()}


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str, repo: Repo = Depends(get_repo)) -> JSONResponse:
    proj = await repo.get_project(project_id)
    if proj is None:
        return JSONResponse(status_code=404, content={"detail": "project not found"})
    return JSONResponse(content=proj)


@router.post("", status_code=202, response_model=ProjectCreatedResponse)
async def create_project(body: ProjectIn, repo: Repo = Depends(get_repo)) -> JSONResponse:
    pid = new_project_id()
    label = body.label.strip()[:120] or "Untitled project"
    await repo.create_project(pid, label, (body.instructions or "").strip() or None)
    return JSONResponse(status_code=202, content={"project_id": pid, "label": label})


@router.patch("/{project_id}", response_model=ProjectPatchResponse)
async def patch_project(
    project_id: str, body: ProjectPatch, repo: Repo = Depends(get_repo)
) -> JSONResponse:
    await repo.update_project(
        project_id,
        body.label.strip()[:120] if body.label else None,
        body.instructions,
    )
    return JSONResponse({"project_id": project_id, "ok": True})


@router.delete("/{project_id}", response_model=ProjectDeleteResponse)
async def delete_project(project_id: str, repo: Repo = Depends(get_repo)) -> JSONResponse:
    """Drop the project; its hunts survive (just unassigned)."""
    await repo.delete_project(project_id)
    return JSONResponse({"project_id": project_id, "deleted": True})
