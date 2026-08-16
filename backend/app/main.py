from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .routers.api import router
from .routers.deps import tenant_scope
from .services import DomainError

app = FastAPI(title="Document Again", version="0.1.0", dependencies=[Depends(tenant_scope)])

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5175", "http://127.0.0.1:5175"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(DomainError)
async def domain_error_handler(_: Request, exc: DomainError):
    return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})


app.include_router(router)


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "document-again"}
