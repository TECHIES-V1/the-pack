# Windows dev launcher — the `make dev` equivalent (Doc 05 §03).
# Starts infra, then opens the engine, gateway, and frontend each in its own terminal.
#
#   pwsh scripts/dev.ps1
#
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

Write-Host "Starting redis + postgres..." -ForegroundColor Cyan
docker compose -f "$root/docker-compose.yml" up -d redis postgres

function Start-Pane($title, $cwd, $cmd) {
  Start-Process pwsh -ArgumentList "-NoExit", "-Command", "cd '$cwd'; Write-Host '$title' -ForegroundColor Green; $cmd"
}

Start-Pane "engine (:8000)"   "$root/backend"  "if (Get-Command uv -ErrorAction SilentlyContinue) { uv run uvicorn app.main:app --reload --port 8000 } else { uvicorn app.main:app --reload --port 8000 }"
Start-Pane "gateway (:8080)"  "$root/gateway"  "cargo run"
Start-Pane "frontend (:5173)" "$root/frontend" "pnpm dev"

Write-Host "Three panes launched. Frontend: http://localhost:5173" -ForegroundColor Cyan
