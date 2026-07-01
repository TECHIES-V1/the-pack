# Pack Engine — Postman

Complete REST surface for the Pack engine (52 endpoints).

## Public workspace

**[postman.com/tobiloba-sulaimon-s-team/pack-engine](https://www.postman.com/tobiloba-sulaimon-s-team/pack-engine)**

Fork the collection and environment from there — no download needed.

## Run in Postman

[![Run in Postman](https://run.pstmn.io/button.svg)](https://god.postman.co/run-collection/47914215-a0354501-f14a-4ff5-ad12-9194c7dd42f7)

## Files
- `Pack.postman_collection.json` — all 52 endpoints, grouped into folders with example bodies.
- `Pack.postman_environment.json` — `baseUrl` (default `http://localhost:8000`) + `huntId`,
  `holdId`, `instinctId`.

Regenerate after adding routes: `backend/.venv/Scripts/python backend/scripts/gen_postman.py`.

## Import (alternative)
1. Postman → Import → Link → paste:
   `https://raw.githubusercontent.com/TECHIES-V1/the-pack/main/docs/postman/Pack.postman_collection.json`
2. Repeat for the environment file (same path, `Pack.postman_environment.json`).
3. Select the **Pack — Local** environment.
4. Start the engine: `uvicorn app.main:app --port 8000` (from `backend/`).

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
