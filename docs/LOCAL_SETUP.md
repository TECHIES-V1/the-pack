# Pack — Run It Locally (team setup)

How to get the whole thing running on your own machine. Two levels:

- **Quick (chat + REST):** infra + the Python engine + the frontend. You can talk to Alpha, create
  hunts, and use Postman. ~10 minutes.
- **Full (live hunts):** also run the Rust gateway, so the canvas/feed updates live.

> **The `.env` (with the Qwen key) is sent separately by Tobi — never committed.** Without it the
> engine still boots in an offline mode (canned replies) so you can test the UI, but Alpha won't be
> smart. Drop the file Tobi sends at `backend/.env`.

---

## Prerequisites — install these first

| Tool | Version | For | Get it |
|------|---------|-----|--------|
| **Docker Desktop** | latest | Postgres + Redis (one command) | docker.com/products/docker-desktop |
| **Python** | 3.12+ | the engine | python.org |
| **Node.js** | 18+ | the frontend | nodejs.org |
| **pnpm** | latest | frontend package manager | `npm install -g pnpm` |
| **Git** | latest | clone the repo | git-scm.com |
| **Rust** (cargo) | stable | the gateway (live hunts only) | rustup.rs |

Don't have Docker? You can install Postgres 16 and Redis 7 natively instead — but Docker is the
easy path and matches everyone else.

---

## 1. Get the code

```bash
git clone <repo-url> pack
cd pack
git checkout tobiloba/engine-spine
```

## 2. Start the infra (Postgres + Redis)

```bash
docker compose up -d            # starts postgres :5432 and redis :6379
docker compose ps               # both should be "healthy"
```

## 3. The engine (Python, port 8000)

```bash
cd backend
python -m venv .venv
# Windows:           .venv\Scripts\activate
# macOS/Linux:       source .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env            # then replace it with the .env Tobi sends you (has the Qwen key)

python -m uvicorn app.main:app --port 8000
```

The database schema is created automatically on boot (idempotent — safe every time). Check it's up:
open <http://localhost:8000/health> → `{"status":"ok"}`.

## 4. The frontend (React, port 5173)

In a new terminal:

```bash
cd frontend
pnpm install
cp .env.example .env.local      # defaults already point at localhost — no secrets here
pnpm dev
```

Open the URL it prints (usually <http://localhost:5173>). You can now chat with Alpha and create
hunts.

## 5. The gateway (Rust, port 8080) — for LIVE hunts

The gateway streams hunt events to the canvas/feed in real time. Skip it if you only need chat/REST.

```bash
cd gateway
cargo run                       # serves the WebSocket on :8080
```

> **Windows note:** clone the repo into a path **without spaces** before building the gateway (a
> known Rust/GNU linker bug trips on spaces). The MSVC toolchain (rustup default) needs Visual
> Studio "Desktop development with C++" build tools.

---

## Ports

| Port | Service | Needed for |
|------|---------|-----------|
| 5432 | Postgres (Docker) | always |
| 6379 | Redis (Docker) | always |
| 8000 | Python engine (REST) | always |
| 5173 | Frontend (Vite) | always |
| 8080 | Rust gateway (WebSocket) | live hunt streaming |

## Troubleshooting

- **Alpha gives canned/robotic replies** → the engine has no Qwen key; put Tobi's `.env` at
  `backend/.env` and restart the engine.
- **Canvas never updates during a hunt** → the gateway (`cargo run` in `gateway/`) isn't running.
- **Engine won't start / DB errors** → `docker compose ps` (is Postgres healthy?); confirm
  `POSTGRES_URL` in `backend/.env` is `postgresql://pack:pack@localhost:5432/pack`.
- **Frontend calls fail in the browser console** → engine not on :8000, or `VITE_ENGINE_URL` in
  `frontend/.env.local` is wrong.

## Test it with Postman

Import `docs/postman/Pack.postman_collection.json` + `Pack.postman_environment.json`, pick the
**Pack — Local** environment, and run **Intake → Create hunt → Approve plan**. See
`docs/postman/README.md`.
