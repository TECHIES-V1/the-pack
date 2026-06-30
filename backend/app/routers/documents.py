"""Knowledge-base (document) routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import JSONResponse

from app.db.repo import Repo
from app.dependencies import _accepted, _read_capped, get_repo
from app.schemas import (
    ClearedResponse,
    DocumentDeleteResponse,
    DocumentDetailResponse,
    DocumentResponse,
    DocumentsListResponse,
)
from app.tools.file_parse import detect_kind, parse_bytes
from app.tools.vision import describe_image

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", status_code=202, response_model=DocumentResponse)
async def add_document(
    file: UploadFile = File(...), repo: Repo = Depends(get_repo)
) -> JSONResponse:
    """Add a document to your local knowledge base — parsed to text and researchable by the pack."""
    data = await _read_capped(file)
    kind = detect_kind(file.filename or "", file.content_type or "")
    if kind == "image":
        text = await describe_image(data, file.content_type or "", file.filename or "")
    elif kind == "video":
        return JSONResponse(
            status_code=400, content={"detail": "video can't go in the knowledge base"}
        )
    else:
        text = parse_bytes(data, kind)
    text = (text or "").strip()
    if not text:
        return JSONResponse(
            status_code=400, content={"detail": "couldn't read any text from that file"}
        )
    doc_id = await repo.save_document(file.filename or "document", kind, text)
    return _accepted({"id": doc_id, "name": file.filename, "kind": kind, "chars": len(text)})


@router.get("", response_model=DocumentsListResponse)
async def list_documents(repo: Repo = Depends(get_repo)) -> dict:
    """Your knowledge-base documents (metadata only, no full text)."""
    return {"documents": await repo.list_documents()}


@router.get("/{doc_id}", response_model=DocumentDetailResponse)
async def get_document(doc_id: int, repo: Repo = Depends(get_repo)) -> JSONResponse:
    """One knowledge-base document including its extracted text."""
    doc = await repo.get_document(doc_id)
    if doc is None:
        return JSONResponse(status_code=404, content={"detail": "document not found"})
    return JSONResponse(content=doc)


@router.delete("", response_model=ClearedResponse)
async def clear_documents(repo: Repo = Depends(get_repo)) -> JSONResponse:
    """Wipe the whole knowledge base (wired to Settings → Clear all saved data)."""
    await repo.clear_documents()
    return JSONResponse({"cleared": True})


@router.delete("/{doc_id}", response_model=DocumentDeleteResponse)
async def delete_document(doc_id: int, repo: Repo = Depends(get_repo)) -> JSONResponse:
    await repo.delete_document(doc_id)
    return JSONResponse({"id": doc_id, "deleted": True})
