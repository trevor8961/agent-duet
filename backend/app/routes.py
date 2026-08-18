"""API 路由。"""

import asyncio
import json

from fastapi import BackgroundTasks, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select

from .db import SessionLocal
from .models import Agent, Session, Turn
from .views import get_session_detail, list_sessions
from .runner import DEFAULT_INTENT, build_command, execute_turn


class SessionCreate(BaseModel):
    title: str
    cwd: str
    agent_id: int
    mode: str = "guided"


class SessionPatch(BaseModel):
    title: str | None = None
    mode: str | None = None


class AgentPatch(BaseModel):
    command: str | None = None
    model: str | None = None


class MessageCreate(BaseModel):
    text: str


def register_routes(app):
    @app.get("/api/agents")
    async def list_agents():
        async with SessionLocal() as db:
            agents = (await db.execute(select(Agent))).scalars().all()
            return [
                {
                    "id": a.id, "name": a.name, "type": a.type,
                    "command": a.command, "model": a.model,
                    "mode_map": json.loads(a.mode_map or "{}"),
                    "capabilities": json.loads(a.capabilities or "{}"),
                }
                for a in agents
            ]

    @app.patch("/api/agents/{agent_id}")
    async def patch_agent(agent_id: int, body: AgentPatch):
        async with SessionLocal() as db:
            agent = await db.get(Agent, agent_id)
            if not agent:
                raise HTTPException(404)
            if body.command is not None:
                agent.command = body.command
            if body.model is not None:
                agent.model = body.model
            await db.commit()
        return {"ok": True}

    @app.post("/api/sessions")
    async def create_session(body: SessionCreate):
        async with SessionLocal() as db:
            agent = await db.get(Agent, body.agent_id)
            if not agent:
                raise HTTPException(400, "agent 不存在")
            s = Session(title=body.title, cwd=body.cwd, agent_id=body.agent_id, mode=body.mode)
            db.add(s)
            await db.commit()
            return {"id": s.id, "title": s.title, "mode": s.mode}

    @app.get("/api/sessions")
    async def get_sessions(q: str | None = None):
        return await list_sessions(q)

    @app.get("/api/sessions/{sid}")
    async def get_session(sid: int):
        detail = await get_session_detail(sid)
        if not detail:
            raise HTTPException(404)
        return detail

    @app.patch("/api/sessions/{sid}")
    async def patch_session(sid: int, body: SessionPatch):
        async with SessionLocal() as db:
            s = await db.get(Session, sid)
            if not s:
                raise HTTPException(404)
            if body.title is not None:
                s.title = body.title
            if body.mode is not None:
                s.mode = body.mode
            await db.commit()
        return {"ok": True}

    @app.post("/api/sessions/{sid}/messages", status_code=202)
    async def post_message(sid: int, body: MessageCreate, background: BackgroundTasks):
        async with SessionLocal() as db:
            s = await db.get(Session, sid)
            if not s:
                raise HTTPException(404)
            agent = await db.get(Agent, s.agent_id)

            try:
                cmd = build_command(agent, s, body.text)
            except ValueError as e:
                raise HTTPException(400, str(e))

            # 模式翻译的历史审计：turn 落库时就记录实际原生模式
            native = cmd[cmd.index("--permission-mode") + 1] if "--permission-mode" in cmd else None

            next_seq = (await db.scalar(
                select(func.max(Turn.seq)).where(Turn.session_id == sid)
            )) or 0
            turn = Turn(session_id=sid, seq=next_seq + 1, intent=DEFAULT_INTENT,
                        status="running", effective_mode=native, model=agent.model)
            db.add(turn)
            s.status = "running"
            await db.commit()
            turn_id = turn.id
            cwd = s.cwd

        background.add_task(execute_turn, sid, turn_id, body.text, cmd, cwd)
        return {"turn_id": turn_id, "status": "running"}
