"""Account Again — FastAPI Application."""

from fastapi import FastAPI
from account_again.config import API_PREFIX, PROJECT_NAME, VERSION
from account_again.database import create_all
from account_again.api.routes import router

app = FastAPI(title=PROJECT_NAME, version=VERSION)
app.include_router(router, prefix=API_PREFIX)


@app.on_event("startup")
def on_startup():
    create_all()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("account_again.main:app", host="0.0.0.0", port=8001, reload=True)
