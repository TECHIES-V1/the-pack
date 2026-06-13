# Pack — one entry point for the dev loop (Doc 05 §03: `make dev` runs both halves).
#
# Windows note: `make` is not native. Use `pwsh scripts/dev.ps1` (see that file) or run the
# per-service targets in separate terminals. On macOS/Linux/WSL/git-bash, `make` works.

.PHONY: help dev infra backend gateway frontend test fixtures-check install hooks

help:
	@echo "Targets:"
	@echo "  make install   - install backend, frontend, gateway deps"
	@echo "  make infra      - start redis + postgres (docker compose)"
	@echo "  make dev        - infra + backend + gateway + frontend (needs 'make -j' or 3 terminals)"
	@echo "  make backend    - run the FastAPI engine (:8000)"
	@echo "  make gateway    - run the Rust gateway (:8080)"
	@echo "  make frontend   - run the Vite dev server (:5173)"
	@echo "  make test       - backend contract tests + frontend reducer tests + cargo check"
	@echo "  make hooks      - install pre-commit hooks"

install:
	cd backend && (uv sync --extra dev || python -m pip install -e ".[dev]")
	cd frontend && pnpm install
	cd gateway && cargo fetch

infra:
	docker compose up -d redis postgres

# Run these three in separate terminals, or `make -j3 dev-all`.
backend:
	cd backend && (uv run uvicorn app.main:app --reload --port 8000 || uvicorn app.main:app --reload --port 8000)

gateway:
	cd gateway && cargo run

frontend:
	cd frontend && pnpm dev

dev: infra
	@echo "Infra up. Now run, in three terminals:  make backend | make gateway | make frontend"
	@echo "Or on Windows:  pwsh scripts/dev.ps1"

test:
	cd backend && (uv run pytest -q || pytest -q)
	cd frontend && pnpm test
	cd gateway && cargo check

hooks:
	pre-commit install
