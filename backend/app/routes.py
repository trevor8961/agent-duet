"""API 路由。"""

import asyncio
import json

from fastapi import BackgroundTasks, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func, select

from .bus import bus
from .db import SessionLocal
from .models import Agent, Session, Turn
from .views import get_session_detail, list_sessions
from .runner import DEFAULT_INTENT, _cancel_flags, _running, build_command, execute_turn


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

    @app.post("/api/sessions/{sid}/cancel")
    async def cancel_session(sid: int):
        """中止运行中的 turn。无运行时幂等返回当前状态。"""
        entry = _running.get(sid)
        if not entry:
            async with SessionLocal() as db:
                from sqlalchemy import update

                result = await db.execute(
                    update(Turn).where(Turn.session_id == sid, Turn.status == "running")
                    .values(status="cancelled")
                )
                s = await db.get(Session, sid)
                if result.rowcount:  # 真有竞态窗口里的 running turn 才算取消成功
                    s.status = "cancelled"
                    await db.commit()
                    return {"status": "cancelled"}
                return {"status": s.status if s else "idle"}
        proc, _ = entry
        _cancel_flags.add(sid)
        proc.terminate()  # SIGTERM；claude 收到后退出，execute_turn 收尾时按 cancelled 落库
        return {"status": "cancelling"}

    @app.get("/api/sessions/{sid}/events")
    async def sse_events(sid: int, last_event_id: str | None = Header(default=None)):
        """SSE：turn 运行期间的实时事件流。

        职责边界：只推增量（总线内存态）；历史真相走 raw 文件与 messages 表。
        """

        async def gen():
            cursor = int(last_event_id) if last_event_id is not None else -1
            async for ev in bus.subscribe(sid, cursor):
                payload = json.dumps({"id": ev["id"], "kind": ev["kind"], "ts": ev["ts"], "data": ev["data"]})
                yield f"id: {ev['id']}\nevent: {ev['kind']}\ndata: {payload}\n\n"

        return StreamingResponse(gen(), media_type="text/event-stream")

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
            if s.status == "running":
                raise HTTPException(409, "该会话已有正在运行的 turn")
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
