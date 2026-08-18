"""agent-duet 后端入口。

启动: cd backend && uv run uvicorn app.main:app --reload --port 8300
"""

import json

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import models  # noqa: F401  确保建表前模型已注册
from .db import DATA_DIR, SessionLocal, engine
from .routes import register_routes
from .seed import seed_if_empty
from .views import get_session_detail, list_sessions

app = FastAPI(title="agent-duet")

register_routes(app)

# 本地工具，前端 dev server 跨端口访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    async with engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)
    await seed_if_empty()


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok"}
