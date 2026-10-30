# Start the FIREWATCH X development servers (Windows PowerShell).
# API on :8200, frontend on :5273. Both windows stay attached to this terminal.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

if (-not (Test-Path (Join-Path $root ".env"))) {
    Copy-Item (Join-Path $root ".env.example") (Join-Path $root ".env")
    Write-Host "Created .env from .env.example — set FIRMS_MAP_KEY when you have one." -ForegroundColor Yellow
}

Write-Host "Applying migrations..." -ForegroundColor Cyan
Push-Location (Join-Path $root "backend")
uv run alembic upgrade head
uv run python -m scripts.seed_sources
Pop-Location

Write-Host "Starting API on http://127.0.0.1:8200" -ForegroundColor Cyan
Start-Process -FilePath "uv" -ArgumentList "run","uvicorn","app.main:app","--reload","--port","8200" -WorkingDirectory (Join-Path $root "backend")

if (-not (Test-Path (Join-Path $root "frontend/node_modules"))) {
    Write-Host "Installing frontend dependencies..." -ForegroundColor Cyan
    Push-Location (Join-Path $root "frontend")
    npm install --no-audit --no-fund
    Pop-Location
}

Write-Host "Starting frontend on http://localhost:5273" -ForegroundColor Cyan
Push-Location (Join-Path $root "frontend")
npm run dev
