"""Generate docs/postman/Pack.postman_collection.json from the live FastAPI OpenAPI spec.

Run:  python -m scripts.gen_postman

Produces a Postman v2.1 collection with:
- Endpoints grouped by tag, named from their OpenAPI summary
- Real example JSON bodies derived from Pydantic schemas (enums use first value, etc.)
- multipart/form-data endpoints use Postman's formdata body mode (not JSON)
- Query parameters listed with description/required flag from the spec
- Path variables in Postman :variable syntax
- Each request carries a description from the OpenAPI operation
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from app.main import app

_OUT = Path(__file__).resolve().parents[2] / "docs" / "postman" / "Pack.postman_collection.json"


# ---------------------------------------------------------------------------
# Schema → example value
# ---------------------------------------------------------------------------

def _example_scalar(schema: dict) -> object:
    """Return a plausible example for a primitive schema node."""
    if "enum" in schema:
        return schema["enum"][0]
    t = schema.get("type")
    if t == "boolean":
        return False
    if t in ("number", "integer"):
        lo = schema.get("minimum", 0)
        hi = schema.get("maximum")
        if hi is not None:
            return round(min(lo + (hi - lo) * 0.1, hi), 2) if lo != hi else lo
        return lo
    if t == "string":
        fmt = schema.get("format", "")
        if fmt == "uuid":
            return "00000000-0000-0000-0000-000000000000"
        if fmt == "date-time":
            return "2024-01-01T00:00:00Z"
        desc = schema.get("description") or schema.get("title") or ""
        slug = re.sub(r"[^a-z0-9_]", "_", desc.lower())[:30].strip("_") or "value"
        return f"<{slug}>"
    if t == "array":
        return [_example_value(schema.get("items", {}), {})]
    if t == "object":
        return {}
    return None


def _resolve(spec: dict, schema: dict) -> dict:
    """Follow a single $ref one level deep."""
    ref = schema.get("$ref", "")
    if not ref:
        return schema
    parts = ref.lstrip("#/").split("/")
    node = spec
    for p in parts:
        node = node.get(p, {})
    return node


def _example_value(schema: dict, spec: dict) -> object:
    schema = _resolve(spec, schema)
    # anyOf / oneOf — pick the first non-null branch
    for key in ("anyOf", "oneOf"):
        branches = schema.get(key, [])
        non_null = [b for b in branches if b.get("type") != "null"]
        if non_null:
            return _example_value(non_null[0], spec)
    if schema.get("type") == "object" or "properties" in schema:
        return {
            field: _example_value(fschema, spec)
            for field, fschema in (schema.get("properties") or {}).items()
        }
    return _example_scalar(schema)


def _example_body(spec: dict, op: dict) -> str | None:
    """Return a pretty-printed JSON example body, or None if no JSON body."""
    rb = op.get("requestBody") or {}
    content = rb.get("content") or {}
    json_schema = (content.get("application/json") or {}).get("schema")
    if not json_schema:
        return None
    return json.dumps(_example_value(json_schema, spec), indent=2)


# ---------------------------------------------------------------------------
# URL construction
# ---------------------------------------------------------------------------

def _postman_url(path: str, query_params: list[dict]) -> dict:
    """Build a Postman URL object from an OpenAPI path string."""
    pm_path = re.sub(r"\{(\w+)\}", r":\1", path)
    segs = [s for s in pm_path.strip("/").split("/") if s]
    url: dict = {
        "raw": "{{baseUrl}}" + path,
        "host": ["{{baseUrl}}"],
        "path": segs,
    }
    if query_params:
        url["query"] = [
            {
                "key": p["name"],
                "value": "",
                "description": p.get("description") or "",
                "disabled": not p.get("required", False),
            }
            for p in query_params
        ]
    return url


# ---------------------------------------------------------------------------
# Main builder
# ---------------------------------------------------------------------------

def build(spec: dict) -> dict:
    groups: dict[str, list] = {}

    for path in sorted(spec["paths"]):
        methods = spec["paths"][path]
        for method, op in methods.items():
            if method not in {"get", "post", "patch", "delete", "put"}:
                continue

            tag = (op.get("tags") or ["misc"])[0]
            summary = op.get("summary") or f"{method.upper()} {path}"
            description = op.get("description") or ""

            query_params = [p for p in (op.get("parameters") or []) if p.get("in") == "query"]

            rb = op.get("requestBody") or {}
            content_types = list((rb.get("content") or {}).keys())
            is_form = any("multipart" in ct or "form" in ct for ct in content_types)

            request: dict = {
                "method": method.upper(),
                "url": _postman_url(path, query_params),
                "description": description,
            }

            if is_form:
                form_schema: dict = {}
                for ct, ct_obj in (rb.get("content") or {}).items():
                    if "multipart" in ct or "form" in ct:
                        form_schema = _resolve(spec, ct_obj.get("schema") or {})
                        break
                props = form_schema.get("properties") or {"file": {}}
                request["body"] = {
                    "mode": "formdata",
                    "formdata": [
                        {"key": fname, "type": "file" if fname == "file" else "text", "value": ""}
                        for fname in props
                    ],
                }
            elif method in {"post", "put", "patch"}:
                example = _example_body(spec, op)
                if example:
                    request["body"] = {
                        "mode": "raw",
                        "raw": example,
                        "options": {"raw": {"language": "json"}},
                    }
                    request["header"] = [{"key": "Content-Type", "value": "application/json"}]

            groups.setdefault(tag, []).append({
                "name": f"{summary}  [{method.upper()}]",
                "request": request,
            })

    return {
        "info": {
            "name": "Pack Engine",
            "description": (
                "Auto-generated from the FastAPI OpenAPI spec — do not hand-edit.\n\n"
                "Re-generate after adding routes:  `python -m scripts.gen_postman`\n\n"
                "Set the `baseUrl` collection variable to `http://localhost:8000` (default)."
            ),
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "item": [{"name": tag, "item": items} for tag, items in sorted(groups.items())],
        "variable": [{"key": "baseUrl", "value": "http://localhost:8000"}],
    }


def main() -> None:
    spec = app.openapi()
    collection = build(spec)
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(collection, indent=2) + "\n", encoding="utf-8")
    count = sum(len(g["item"]) for g in collection["item"])
    print(f"wrote {count} endpoints across {len(collection['item'])} groups -> {_OUT}")


if __name__ == "__main__":
    main()
