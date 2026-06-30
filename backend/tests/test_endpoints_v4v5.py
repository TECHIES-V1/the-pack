"""Review Md3 — coverage for the new P4/P5 surface: the /documents, /memory, /spend endpoints, the
knowledge selector, and a guard that the download allowlist can't drift from the forge renderers.

The endpoints read `app.state.repo`; we inject a FakeRepo and build a TestClient WITHOUT the context
manager so the DB-backed lifespan never runs (hermetic, no Postgres needed).
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.engine import forge
from app.main import _DOWNLOADABLE, app
from app.tools.knowledge import select_relevant

_POSTMAN = Path(__file__).resolve().parents[2] / "docs" / "postman" / "Pack.postman_collection.json"

from ._fakes import FakeRepo


def _client() -> TestClient:
    app.state.repo = FakeRepo()
    return TestClient(app)


def test_postman_collection_matches_openapi_routes() -> None:
    # A5: collection must list the same (method, path) pairs as the live FastAPI spec.
    # If it drifts, re-run `python -m scripts.gen_postman` to sync it.
    assert _POSTMAN.exists(), "docs/postman/Pack.postman_collection.json not found — run scripts/gen_postman.py"
    collection = json.loads(_POSTMAN.read_text(encoding="utf-8"))
    postman_routes = {
        (item["request"]["method"], item["request"]["url"]["raw"].replace("{{baseUrl}}", ""))
        for group in collection["item"]
        for item in group["item"]
    }
    spec = app.openapi()
    openapi_routes = {
        (method.upper(), path)
        for path, methods in spec["paths"].items()
        for method in methods
        if method in {"get", "post", "patch", "delete", "put"}
    }
    missing_from_postman = openapi_routes - postman_routes
    assert not missing_from_postman, (
        f"These live routes are absent from the Postman collection "
        f"(run scripts/gen_postman.py to fix):\n"
        + "\n".join(f"  {m} {p}" for m, p in sorted(missing_from_postman))
    )


def test_downloadable_allowlist_matches_forge_renderers() -> None:
    # If a format is rendered but not downloadable (or vice-versa) the Reward tabs break silently.
    assert _DOWNLOADABLE == set(forge._RENDERERS)


def test_documents_crud_roundtrip() -> None:
    client = _client()
    files = {"file": ("notes.txt", b"solid state battery notes", "text/plain")}
    r = client.post("/documents", files=files)
    assert r.status_code == 202
    doc_id = r.json()["id"]

    listed = client.get("/documents").json()["documents"]
    assert [d["name"] for d in listed] == ["notes.txt"]
    assert "text" not in listed[0]  # list is metadata only

    assert client.delete(f"/documents/{doc_id}").json()["deleted"] is True
    assert client.get("/documents").json()["documents"] == []


def test_upload_over_cap_is_rejected_413(monkeypatch) -> None:
    # B1: a file over max_upload_mb must 413 before being buffered into memory.
    from app.config import settings

    monkeypatch.setattr(settings, "max_upload_mb", 0)  # cap = 0 → any non-empty upload is too large
    client = _client()
    r = client.post("/documents", files={"file": ("big.txt", b"x" * 2048, "text/plain")})
    assert r.status_code == 413


def test_bad_request_bodies_are_422() -> None:
    # B5: invalid enums/shapes are rejected at the door, before reaching the engine.
    client = _client()
    assert client.post("/hunts", json={"input": "x", "strategy": "bogus"}).status_code == 422
    assert client.post("/hunts", json={"input": "x", "source": "carrier-pigeon"}).status_code == 422
    assert (
        client.post("/hunts/h1/plan/approve", json={"mode": "yolo", "boundary_usd": 1}).status_code
        == 422
    )
    assert (
        client.post("/hunts/h1/plan/approve", json={"mode": "wild", "boundary_usd": -5}).status_code
        == 422
    )


def test_instinct_full_crud() -> None:
    # A1: save -> get -> patch -> delete, with 404s on a missing one.
    client = _client()
    body = {"label": "Deep Research", "spec": {"strategy": "deep_dive"}}
    sid = client.post("/instincts", json=body).json()["instinct_id"]
    assert client.get(f"/instincts/{sid}").json()["label"] == "Deep Research"
    assert client.patch(f"/instincts/{sid}", json={"label": "Renamed"}).json()["ok"] is True
    assert client.get(f"/instincts/{sid}").json()["label"] == "Renamed"
    assert client.delete(f"/instincts/{sid}").json()["deleted"] is True
    assert client.get(f"/instincts/{sid}").status_code == 404
    assert client.patch(f"/instincts/{sid}", json={"label": "x"}).status_code == 404
    assert client.delete(f"/instincts/{sid}").status_code == 404


def test_feedback_is_readable() -> None:
    # A2: votes were write-only; now they read back with tallies.
    client = _client()
    client.post("/hunts/h1/feedback", json={"turn_index": 0, "vote": "up"})
    client.post("/hunts/h1/feedback", json={"turn_index": 2, "vote": "down"})
    fb = client.get("/hunts/h1/feedback").json()
    assert fb["up"] == 1 and fb["down"] == 1 and len(fb["votes"]) == 2


def test_single_get_document_and_project() -> None:
    # A4: CRUD symmetry — single-resource reads.
    client = _client()
    up = client.post("/documents", files={"file": ("n.txt", b"hello pack", "text/plain")})
    doc_id = up.json()["id"]
    got = client.get(f"/documents/{doc_id}").json()
    assert got["name"] == "n.txt" and "hello pack" in got["text"]
    assert client.get("/documents/9999").status_code == 404

    pid = client.post("/projects", json={"label": "Research"}).json()["project_id"]
    assert client.get(f"/projects/{pid}").json()["label"] == "Research"
    assert client.get("/projects/nope").status_code == 404


def test_documents_rejects_empty_text() -> None:
    client = _client()
    r = client.post("/documents", files={"file": ("blank.txt", b"   ", "text/plain")})
    assert r.status_code == 400


def test_memory_and_spend_and_clear_endpoints() -> None:
    client = _client()
    assert client.get("/memory").json()["memory"] == []
    spend = client.get("/spend").json()
    assert spend["total_usd"] == 0 and spend["hunts"] == []
    assert client.delete("/memory").json()["cleared"] is True
    assert client.delete("/documents").json()["cleared"] is True


def test_select_relevant_picks_matching_and_respects_caps() -> None:
    docs = [
        {"id": 1, "name": "battery.md", "text": "solid state battery supplier roadmap and costs"},
        {"id": 2, "name": "poetry.md", "text": "medieval european poetry and verse"},
        {"id": 3, "name": "cells.md", "text": "battery cell chemistry and energy density"},
    ]
    picks = select_relevant(docs, "the solid-state battery market")
    urls = [p["url"] for p in picks]
    assert "lib://1" in urls and "lib://3" in urls  # battery docs picked
    assert "lib://2" not in urls  # the unrelated poetry doc is not
    assert all(p["by"] == "your library" and p["url"].startswith("lib://") for p in picks)

    assert select_relevant(docs, "") == []  # no topic signal → nothing, not noise
    assert select_relevant([], "anything") == []
