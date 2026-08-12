"""
Conductor Again — FastAPI Application
Project Control Plane + Skill & AI Capability Distributor
"""

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.rate_limit import limiter

load_dotenv()

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    from app.database import ensure_master_db
    ensure_master_db()
    yield
    # Shutdown
    from app.database import dispose_all_engines
    dispose_all_engines()


app = FastAPI(
    title="Conductor Again",
    description="Project Control Plane + Skill & AI Capability Distributor",
    version="0.1.0",
    lifespan=lifespan,
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health_check():
    return {"status": "ok", "app": "Conductor Again"}


# Register routers
from app.routers import auth, projects, ai_resources, skills, deliberation, intake, golden_flow, integration, multi_ai

app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(ai_resources.router)
app.include_router(skills.router)
app.include_router(deliberation.router)
app.include_router(intake.router)
app.include_router(golden_flow.router)
app.include_router(integration.router)
app.include_router(multi_ai.router)
