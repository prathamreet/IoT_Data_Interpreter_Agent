# ── One-command launcher (Windows / PowerShell) ──────────────────────
# Usage:  .\run.ps1
$ErrorActionPreference = "Stop"

Write-Host "IoT Data Interpreter Agent — setup & launch" -ForegroundColor Cyan

if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment (.venv)..." -ForegroundColor Yellow
    python -m venv .venv
}

# Activate the venv for this session.
. .\.venv\Scripts\Activate.ps1

Write-Host "Installing dependencies..." -ForegroundColor Yellow
python -m pip install --upgrade pip | Out-Null
pip install -r requirements.txt

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env (no API key required — runs in offline mode)." -ForegroundColor Green
}

Write-Host "`nStarting server at http://127.0.0.1:8000  (Ctrl+C to stop)`n" -ForegroundColor Green
uvicorn backend.main:app --host 127.0.0.1 --port 8000
