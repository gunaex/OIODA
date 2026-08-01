# QA-Again local dev launcher (PowerShell) -- starts backend
# (FastAPI/uvicorn) and frontend (Vite) each in their own window,
# installing dependencies on first run only if missing. ADMIN_EMAIL/
# ADMIN_PASSWORD only take effect if the user database is completely
# empty (fresh bootstrap) -- ignored once an account already exists.
# Never touches backend/data -- existing local projects/evidence are
# left alone.

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "python was not found on PATH. Install Python 3.11+ and re-run."
    exit 1
}
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Write-Error "npm was not found on PATH. Install Node.js and re-run."
    exit 1
}

$env:ADMIN_EMAIL = "***REMOVED-CREDENTIAL***"
$env:ADMIN_PASSWORD = "***REMOVED-CREDENTIAL***"
$env:ALLOWED_ORIGINS = "http://localhost:5173"
$env:JWT_SECRET_KEY = "dev-local-secret-change-me"

$backendVenv = Join-Path $root "backend\.venv"
if (-not (Test-Path $backendVenv)) {
    Write-Host "Setting up backend virtual environment..."
    python -m venv $backendVenv
    & "$backendVenv\Scripts\pip" install -r (Join-Path $root "backend\requirements-dev.txt")
}

$frontendModules = Join-Path $root "frontend\node_modules"
if (-not (Test-Path $frontendModules)) {
    Write-Host "Installing frontend dependencies..."
    Push-Location (Join-Path $root "frontend")
    npm install
    Pop-Location
}

Write-Host "Starting backend on http://127.0.0.1:8000 ..."
Start-Process cmd -ArgumentList "/k", "cd /d `"$root\backend`" && set ADMIN_EMAIL=$($env:ADMIN_EMAIL)&& set ADMIN_PASSWORD=$($env:ADMIN_PASSWORD)&& set ALLOWED_ORIGINS=$($env:ALLOWED_ORIGINS)&& set JWT_SECRET_KEY=$($env:JWT_SECRET_KEY)&& .venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000"

Write-Host "Starting frontend on http://localhost:5173 ..."
Start-Process cmd -ArgumentList "/k", "cd /d `"$root\frontend`" && npm run dev"

Start-Sleep -Seconds 3
Start-Process "http://localhost:5173/login"

Write-Host ""
Write-Host "Backend:  http://127.0.0.1:8000"
Write-Host "Frontend: http://localhost:5173"
