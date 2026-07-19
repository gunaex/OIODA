import os

from dotenv import load_dotenv

# Must run before any of this app's modules are imported — auth.py reads
# JWT_SECRET_KEY at import time, so loading .env any later would be too late
# and it'd fall back to the ephemeral per-process secret regardless of what
# the file contains.
load_dotenv()

from fastapi import FastAPI, Request  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from slowapi.errors import RateLimitExceeded  # noqa: E402

from .database import MasterBase, master_engine, MasterSessionLocal, ensure_columns, MASTER_COLUMN_PATCHES  # noqa: E402
from .routers import (
    projects,
    functions,
    tasks,
    gantt,
    documents,
    comments,
    activity,
    search,
    notes,
    reports,
    board_items,
    whiteboards,
    auth,
    resources,
    resource_allocations,
    dashboard,
    slippage,
)
from .seed import seed_document_templates, seed_bootstrap_admin
from .rate_limit import limiter

MasterBase.metadata.create_all(bind=master_engine)
ensure_columns(master_engine, MASTER_COLUMN_PATCHES)

with MasterSessionLocal() as _db:
    seed_document_templates(_db)
    seed_bootstrap_admin(_db)

app = FastAPI(title="PM-Again API")

app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(status_code=429, content={"detail": "Too many requests — please slow down."})


# Comma-separated list of allowed CORS origins. Defaults to the local Vite
# dev server so `uvicorn` run locally behaves exactly as before; set
# ALLOWED_ORIGINS in production to include the deployed frontend's origin(s).
# allow_credentials=True + an explicit origin list (never "*") is required
# for the auth cookies to actually be sent cross-origin.
_allowed_origins = [
    o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173").split(",") if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    # HSTS only matters over HTTPS (Fly/Vercel terminate TLS for us); harmless
    # to always send. nosniff and DENY are safe defaults for a JSON API — this
    # backend never itself gets embedded in an iframe (the whiteboard is the
    # frontend embedding *drawio*, not anyone embedding us), so no carve-out
    # is needed here.
    response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    return response


# Fixed-literal-prefix routers (auth/projects/resources/dashboard-global)
# registered before the /{slug}/... parametrized routers below — Starlette
# matches routes in registration order, and a project literally slugged
# "resources" or "dashboard" would otherwise collide with these (see
# RESERVED_SLUGS in routers/projects.py, which prevents that slug from ever
# being assigned in the first place, belt-and-suspenders with this order).
app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(resources.router)
app.include_router(dashboard.global_router)
app.include_router(functions.router)
app.include_router(tasks.router)
app.include_router(gantt.router)
app.include_router(documents.router)
app.include_router(comments.router)
app.include_router(activity.router)
app.include_router(search.router)
app.include_router(notes.router)
app.include_router(reports.router)
app.include_router(board_items.router)
app.include_router(whiteboards.router)
app.include_router(resource_allocations.router)
app.include_router(dashboard.project_router)
app.include_router(slippage.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
