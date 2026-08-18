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
    await recover_orphaned_turns()


async def recover_orphaned_turns() -> None:
    """崩溃恢复：上次运行遗留的 running turn 是孤儿（进程已死，无人收尾）。

    统一标 error/orphaned——用户得到明确的可重试失败，而不是永远 running。
    """
    from sqlalchemy import update

    from .db import SessionLocal
    from .models import Session, Turn

    async with SessionLocal() as db:
        result = await db.execute(
            update(Turn).where(Turn.status == "running")
            .values(status="error", outcome_source="orphaned")
        )
        if result.rowcount:
            await db.execute(update(Session).where(Session.status == "running").values(status="error"))
        await db.commit()


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok"}
