from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api import router as api_router
from .db import init_db


app = FastAPI(title="企业知识库智能助手")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(api_router)


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/")
def index() -> FileResponse:
    return FileResponse("app/static/index.html")
