"""Generate docs/postman/Pack.postman_collection.json from the live FastAPI OpenAPI spec.
Run: python -m scripts.gen_postman
"""
from __future__ import annotations
import json
from pathlib import Path
from app.main import app

_OUT = Path(__file__).resolve().parents[2] / "docs" / "postman" / "Pack.postman_collection.json"

def _url(path: str) -> dict:
    segs = [s for s in path.strip("/").split("/") if s]
    return {"raw": "{{baseUrl}}" + path, "host": ["{{baseUrl}}"], "path": segs}

def build() -> dict:
    spec = app.openapi()
    groups: dict[str, list] = {}
    for path, methods in sorted(spec["paths"].items()):
        for method, op in methods.items():
            if method not in {"get", "post", "patch", "delete", "put"}:
                continue
            tag = (op.get("tags") or ["misc"])[0]
            req: dict = {"method": method.upper(), "url": _url(path)}
            if method in {"post", "put", "patch"} and "requestBody" in op:
                req["body"] = {"mode": "raw", "raw": "{}", "options": {"raw": {"language": "json"}}}
                req["header"] = [{"key": "Content-Type", "value": "application/json"}]
            groups.setdefault(tag, []).append({"name": f"{method.upper()} {path}", "request": req})
    return {
        "info": {
            "name": "Pack Engine",
            "description": "Auto-generated from the FastAPI OpenAPI spec — do not hand-edit.",
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "item": [{"name": tag, "item": items} for tag, items in sorted(groups.items())],
        "variable": [{"key": "baseUrl", "value": "http://localhost:8000"}],
    }

def main() -> None:
    collection = build()
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(collection, indent=2) + "\n", encoding="utf-8")
    count = sum(len(g["item"]) for g in collection["item"])
    print(f"wrote {count} endpoints across {len(collection['item'])} groups -> {_OUT}")

if __name__ == "__main__":
    main()
