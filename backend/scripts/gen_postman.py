"""Generate the Postman collection + environment for the Pack engine REST surface.

Run from the repo root: backend/.venv/Scripts/python.exe backend/scripts/gen_postman.py
Writes docs/postman/Pack.postman_collection.json and Pack.postman_environment.json.
"""

from __future__ import annotations

import json
import os


def url(path: str) -> dict:
    segs = [s for s in path.split("/") if s != ""]
    return {"raw": "{{baseUrl}}" + path, "host": ["{{baseUrl}}"], "path": segs}


def req(name, method, path, desc, body=None, tests=None) -> dict:
    r = {
        "name": name,
        "request": {"method": method, "header": [], "url": url(path), "description": desc},
        "response": [],
    }
    if body is not None:
        r["request"]["header"].append({"key": "Content-Type", "value": "application/json"})
        r["request"]["body"] = {
            "mode": "raw",
            "raw": json.dumps(body, indent=2),
            "options": {"raw": {"language": "json"}},
        }
    if tests:
        r["event"] = [{"listen": "test", "script": {"type": "text/javascript", "exec": tests}}]
    return r


capture_hunt = [
    "const j = pm.response.json();",
    "if (j && j.hunt_id) { pm.collectionVariables.set('huntId', j.hunt_id); }",
]

collection = {
    "info": {
        "name": "Pack Engine API",
        "_postman_id": "pack-engine-collection",
        "description": (
            "Pack -- multi-agent hunt orchestrator. REST command surface for the Python engine.\n\n"
            "Model: commands return 202 Accepted with a small ack; the result is never in the HTTP "
            "response -- it arrives on the event stream (WS/SSE via the gateway). The exceptions are "
            "the read endpoints (GET) and the conversational POST /hunts/intake and "
            "POST /hunts/{id}/ask, which reply synchronously.\n\n"
            "Typical flow: POST /hunts/intake (clarify) -> POST /hunts (create) -> watch stream -> "
            "POST /hunts/{id}/plan/approve -> (/holds/{hold_id}/resolve when a Hold opens) -> "
            "returned -> GET /hunts/{id}/artifact.\n\n"
            "Set {{baseUrl}} in the environment. 'Create hunt' auto-saves {{huntId}}."
        ),
        "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
    },
    "variable": [
        {"key": "baseUrl", "value": "http://localhost:8000"},
        {"key": "huntId", "value": ""},
        {"key": "holdId", "value": ""},
        {"key": "instinctId", "value": ""},
    ],
    "item": [
        {
            "name": "System",
            "item": [req("Health", "GET", "/health", "Liveness probe. Returns {status, service}.")],
        },
        {
            "name": "Conversation (front door)",
            "item": [
                req(
                    "Intake -- talk to Alpha (clarify-gate)",
                    "POST",
                    "/hunts/intake",
                    "Alpha holds a normal conversation and decides if there's a real task yet. "
                    "Synchronous reply {reply, ready, brief}. ready=false means keep chatting (no "
                    "hunt, no cost); ready=true means brief is an actionable task -- create a hunt "
                    "with it. Send the whole conversation so far in messages.",
                    body={
                        "messages": [
                            {
                                "role": "user",
                                "content": "research the BNPL market in Nigeria and write me a brief",
                            }
                        ]
                    },
                ),
                req(
                    "Ask Alpha (about a hunt)",
                    "POST",
                    "/hunts/{{huntId}}/ask",
                    "Ask Alpha a question about the running/finished hunt. Synchronous on-voice "
                    "reply {reply}. Does not change hunt state.",
                    body={"question": "How's it going so far?"},
                ),
            ],
        },
        {
            "name": "Hunts -- create & inspect",
            "item": [
                req(
                    "Create hunt",
                    "POST",
                    "/hunts",
                    "Open a hunt (202). The Supervisor starts planning immediately; watch "
                    "hunt_created -> plan_proposed on the stream. Provide input (free text, usually "
                    "Alpha's brief) OR instinct_id to start from a saved Instinct. source is one of "
                    "typed | spoken | dropped. Saves {{huntId}}.",
                    body={
                        "input": "Research the BNPL market in Nigeria and write a brief.",
                        "source": "typed",
                    },
                    tests=capture_hunt,
                ),
                req("List hunts", "GET", "/hunts", "All hunts (newest first) for the Den."),
                req(
                    "Get hunt snapshot",
                    "GET",
                    "/hunts/{{huntId}}",
                    "Current state snapshot {hunt_id, state, last_seq, task} -- used to resume the "
                    "stream.",
                ),
                req(
                    "Get final artifact",
                    "GET",
                    "/hunts/{{huntId}}/artifact",
                    "The deliverable once the hunt has returned (the Return document).",
                ),
                req(
                    "Export tracks (event log)",
                    "GET",
                    "/hunts/{{huntId}}/tracks/export",
                    "Full, ordered event log {hunt_id, events[], redacted} -- powers Tracks.",
                ),
            ],
        },
        {
            "name": "Hunts -- run lifecycle",
            "item": [
                req(
                    "Approve plan (set Boundary, launch)",
                    "POST",
                    "/hunts/{{huntId}}/plan/approve",
                    "Approve the proposed plan and set the spend Boundary -- the hunt begins (202). "
                    "mode is one of wild | on_signal | on_command. edits optionally overrides plan "
                    "assumptions.",
                    body={"mode": "on_signal", "boundary_usd": 1.0, "edits": None},
                ),
                req(
                    "Resolve a Hold",
                    "POST",
                    "/hunts/{{huntId}}/holds/{{holdId}}/resolve",
                    "Answer the one open Hold so the pack resumes (202). resolution is the chosen "
                    "option; edited_text optionally supplies corrected text.",
                    body={"resolution": "Use the regulator's figure", "edited_text": None},
                ),
                req(
                    "Add input mid-hunt",
                    "POST",
                    "/hunts/{{huntId}}/inputs",
                    "Feed new material to a running hunt (202).",
                ),
                req(
                    "Stop hunt",
                    "POST",
                    "/hunts/{{huntId}}/stop",
                    "Stop the hunt by the Packmaster's command (202).",
                ),
                req(
                    "Resume after Boundary halt",
                    "POST",
                    "/hunts/{{huntId}}/resume",
                    "Lift a Boundary halt with a new cap and continue (202).",
                    body={"boundary_usd": 2.0},
                ),
                req(
                    "Benchmark -- Lone Wolf vs Pack",
                    "POST",
                    "/hunts/{{huntId}}/benchmark",
                    "Run the same task single-agent for the Scorecard comparison (202). Stub today.",
                ),
            ],
        },
        {
            "name": "Den -- Instincts",
            "item": [
                req("List instincts", "GET", "/instincts", "Saved Instincts (reusable hunt templates)."),
                req(
                    "Save instinct",
                    "POST",
                    "/instincts",
                    "Save a hunt setup as a one-tap Instinct. Copy instinct_id from the response.",
                    body={"label": "The Newsroom", "spec": {"pattern": "research", "voice": "briefing"}},
                ),
            ],
        },
        {
            "name": "Uploads",
            "item": [
                req(
                    "Signed upload URL",
                    "POST",
                    "/uploads",
                    "Get a pre-signed object-store URL for a file drop {upload_url, object_key} (202).",
                )
            ],
        },
    ],
}

environment = {
    "name": "Pack -- Local",
    "values": [
        {"key": "baseUrl", "value": "http://localhost:8000", "enabled": True},
        {"key": "huntId", "value": "", "enabled": True},
        {"key": "holdId", "value": "", "enabled": True},
        {"key": "instinctId", "value": "", "enabled": True},
    ],
    "_postman_variable_scope": "environment",
}

root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
out = os.path.join(root, "docs", "postman")
os.makedirs(out, exist_ok=True)
with open(os.path.join(out, "Pack.postman_collection.json"), "w", encoding="utf-8") as f:
    json.dump(collection, f, indent=2)
    f.write("\n")
with open(os.path.join(out, "Pack.postman_environment.json"), "w", encoding="utf-8") as f:
    json.dump(environment, f, indent=2)
    f.write("\n")

count = sum(len(folder["item"]) for folder in collection["item"])
print(f"wrote {count} requests across {len(collection['item'])} folders to {out}")
