import os

from dotenv import load_dotenv

# Must run before any of this app's modules are imported — auth.py reads
# JWT_SECRET_KEY at import time, so loading .env any later would be too late.
load_dotenv()

from fastapi import FastAPI, Request  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from slowapi.errors import RateLimitExceeded  # noqa: E402

from .database import MasterBase, master_engine, MasterSessionLocal, ensure_columns, MASTER_COLUMN_PATCHES  # noqa: E402
from .routers import auth, projects, suites, revisions, cases, cycles, cycle_results, runner_tokens, hybrid  # noqa: E402
from .seed import seed_bootstrap_admin  # noqa: E402
from .rate_limit import limiter  # noqa: E402

MasterBase.metadata.create_all(bind=master_engine)
ensure_columns(master_engine, MASTER_COLUMN_PATCHES)

with MasterSessionLocal() as _db:
    seed_bootstrap_admin(_db)

app = FastAPI(title="QA-Again API")

app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(status_code=429, content={"detail": "Too many requests — please slow down."})


# Comma-separated list of allowed CORS origins. Defaults to the local Vite
# dev server so `uvicorn` run locally behaves exactly as before; set
# ALLOWED_ORIGINS in production to the deployed Cloudflare Pages origin(s).
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
    response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    return response


app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(suites.router)
app.include_router(revisions.router)
app.include_router(cases.router)
app.include_router(cycles.router)
app.include_router(cycle_results.router)
app.include_router(runner_tokens.router)
app.include_router(hybrid.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
