from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import router as api_router
from .config import get_settings
from .db import init_db
from .repositories import seed_default_auth_data


app = FastAPI(title="企业知识库智能助手")
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_allowed_origins.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router)


@app.on_event("startup")
def startup() -> None:
    init_db()
    seed_default_auth_data()


@app.get("/")
def index() -> dict[str, str]:
    return {"name": settings.app_name, "status": "ok"}
