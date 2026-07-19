# PM-Again — Project Management Web Platform (MVP)

FastAPI + SQLite backend, React (Vite) + Tailwind frontend. One SQLite file per project, provisioned on "New Project".

## Modules

- Function / Requirement List
- Gantt Chart (frappe-gantt, drag/resize, milestones, dependencies)
- Task List + Follow-up Tasks
- Excel import/export for all three (with strict column-header validation)

## Backend

```bash
cd backend
python -m venv venv
./venv/Scripts/activate        # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

API docs at http://localhost:8000/docs. Per-project SQLite files live in `backend/data/projects/{slug}.db`; the project registry lives in `backend/data/master.db`.

## Frontend

```bash
cd frontend
npm install
npm run dev
```

Opens at http://localhost:5173. The Vite dev server proxies `/api` to `http://127.0.0.1:8000`, so run the backend first.

## Notes

- Excel import validates column headers against the template exactly (`.../import-template`) — mismatched or missing columns are rejected with a detailed error instead of being guessed.
- To move a project, copy its `backend/data/projects/{slug}.db` file; to move everything, copy `backend/data/`.
