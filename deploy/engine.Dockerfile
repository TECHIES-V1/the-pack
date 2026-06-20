# Pack engine — FastAPI/uvicorn. Build context: repo root.
#   docker build -f deploy/engine.Dockerfile -t pack-engine .
FROM python:3.12-slim

WORKDIR /app

# Runtime dependencies. Kept in sync with backend/pyproject.toml [project.dependencies].
RUN pip install --no-cache-dir \
    "fastapi>=0.115" \
    "uvicorn[standard]>=0.30" \
    "pydantic>=2.7" \
    "pydantic-settings>=2.3" \
    "redis>=5.0" \
    "openai>=1.40" \
    "asyncpg>=0.29" \
    "jsonschema>=4.22" \
    "python-ulid>=2.7"

# App source: app/, schema/ (frozen event schema, loaded at runtime), prompts/, scripts/.
# Secrets are NOT baked in — they arrive via env (.env.prod). .dockerignore drops .env/.venv.
COPY backend/ /app/

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
