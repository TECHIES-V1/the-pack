# Pack Engine — Postman

Complete REST surface for the Pack engine (17 endpoints).

## Files
- `Pack.postman_collection.json` — all endpoints, grouped into folders with example bodies.
- `Pack.postman_environment.json` — `baseUrl` (default `http://localhost:8000`) + `huntId`,
  `holdId`, `instinctId`.

Regenerate after adding routes: `backend/.venv/Scripts/python backend/scripts/gen_postman.py`.

## Import
1. Postman → Import → both JSON files.
2. Select the **Pack — Local** environment.
3. Start the engine: `uvicorn app.main:app --port 8000` (from `backend/`).

## The model
Commands return **202 Accepted** with a tiny ack — the *result* is never in the HTTP response, it
arrives on the event stream (WS/SSE via the gateway). The synchronous exceptions are the `GET`
reads and the conversational `POST /hunts/intake` and `POST /hunts/{id}/ask`.

## Happy path
1. **Conversation → Intake** — chat until `ready:true` with a `brief`.
2. **Hunts → Create hunt** — uses that brief; auto-saves `{{huntId}}`.
3. Watch the stream for `plan_proposed`.
4. **Run lifecycle → Approve plan** — set the Boundary; the hunt runs.
5. When a Hold opens, set `{{holdId}}` and **Resolve a Hold**.
6. On `returned` → **Get final artifact**, or **Export tracks** for the full log.
