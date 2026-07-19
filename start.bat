@echo off
cd /d "%~dp0"

start "PM-Again Backend" cmd /k "cd backend && call venv\Scripts\activate && uvicorn app.main:app --reload --port 8000"
start "PM-Again Frontend" cmd /k "cd frontend && npm run dev"

echo Backend  -^> http://localhost:8000
echo Frontend -^> http://localhost:5173
