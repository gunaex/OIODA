@echo off
setlocal

rem QA-Again local dev launcher: starts backend (FastAPI/uvicorn) and
rem frontend (Vite) each in their own window, installing dependencies on
rem first run if missing. ADMIN_EMAIL/ADMIN_PASSWORD only take effect if
rem the user database is completely empty (fresh bootstrap) -- they are
rem ignored once an account already exists.

set "ROOT=%~dp0"
set "ADMIN_EMAIL=***REMOVED-CREDENTIAL***"
set "ADMIN_PASSWORD=***REMOVED-CREDENTIAL***"
set "ALLOWED_ORIGINS=http://localhost:5173"
set "JWT_SECRET_KEY=dev-local-secret-change-me"

where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: "python" was not found on PATH. Install Python 3.11+ and re-run.
    exit /b 1
)
where npm >nul 2>nul
if errorlevel 1 (
    echo ERROR: "npm" was not found on PATH. Install Node.js and re-run.
    exit /b 1
)

if not exist "%ROOT%backend\.venv" (
    echo Setting up backend virtual environment...
    python -m venv "%ROOT%backend\.venv"
    "%ROOT%backend\.venv\Scripts\pip" install -r "%ROOT%backend\requirements-dev.txt"
)

if not exist "%ROOT%frontend\node_modules" (
    echo Installing frontend dependencies...
    pushd "%ROOT%frontend"
    call npm install
    popd
)

echo Starting backend on http://127.0.0.1:8000 ...
start "QA-Again Backend" cmd /k "cd /d %ROOT%backend && set ADMIN_EMAIL=%ADMIN_EMAIL%&& set ADMIN_PASSWORD=%ADMIN_PASSWORD%&& set ALLOWED_ORIGINS=%ALLOWED_ORIGINS%&& set JWT_SECRET_KEY=%JWT_SECRET_KEY%&& .venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000"

echo Starting frontend on http://localhost:5173 ...
start "QA-Again Frontend" cmd /k "cd /d %ROOT%frontend && npm run dev"

timeout /t 3 >nul
start "" http://localhost:5173/login

endlocal
