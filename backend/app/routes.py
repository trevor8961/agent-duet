"""API 路由。"""

import asyncio
import json
import subprocess

from fastapi import BackgroundTasks, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func, select

from .bus import bus
from .db import DATA_DIR, SessionLocal
from .models import Agent, Message, Session, Turn
from .views import get_session_detail, list_sessions
from .runner import DEFAULT_INTENT, _cancel_flags, _running, build_command, execute_turn, profile_supports_sdk


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
    mode_override: str | None = None  # 轮次级一次性授权：仅本轮生效
    granted_from: int | None = None  # 授权链：化解了哪次拒绝


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

    @app.get("/api/sessions/{sid}/permissions")
    async def pending_permissions(sid: int):
        """返回该会话仍挂起中的权限请求（页面重开恢复用）。"""
        from sqlalchemy import select as sa_select

        from .models import PermissionRequest

        async with SessionLocal() as db:
            rows = (await db.execute(
                sa_select(PermissionRequest).where(
                    PermissionRequest.session_id == sid,
                    PermissionRequest.status == "pending",
                )
            )).scalars().all()
            return [
                {"request_id": r.request_id, "tool_name": r.tool_name,
                 "tool_input": json.loads(r.tool_input), "timeout_at": r.timeout_at}
                for r in rows
            ]

    @app.post("/api/sessions/{sid}/permission/{request_id}")
    async def resolve_permission(sid: int, request_id: str, body: dict):
        """用户批准/拒绝挂起中的权限请求（body={"decision": "allow"|"deny"}）。"""
        from .sdk_runner import resolve_permission as _resolve

        decision = (body or {}).get("decision")
        if decision not in ("allow", "deny"):
            raise HTTPException(400, "decision 必须是 allow 或 deny")
        ok = _resolve(request_id, decision)
        if not ok:
            raise HTTPException(410, "请求不存在或已处理")
        return {"ok": True}

    @app.delete("/api/sessions/{sid}")
    async def delete_session(sid: int):
        """级联删除：session + turns + messages + raw 留档目录。"""
        import shutil

        from sqlalchemy import delete as sa_delete

        async with SessionLocal() as db:
            s = await db.get(Session, sid)
            if not s:
                raise HTTPException(404)
            await db.execute(sa_delete(Message).where(Message.session_id == sid))
            await db.execute(sa_delete(Turn).where(Turn.session_id == sid))
            await db.delete(s)
            await db.commit()
        raw_dir = DATA_DIR / "raw" / str(sid)
        shutil.rmtree(raw_dir, ignore_errors=True)
        return {"ok": True}

    @app.get("/api/sessions")
    async def get_sessions(q: str | None = None):
        return await list_sessions(q)

    @app.get("/api/sessions/{sid}/git")
    async def session_git_status(sid: int):
        """工作区 git 状态：DB 说 agent 说了什么，git 说世界变成了什么样。"""
        async with SessionLocal() as db:
            s = await db.get(Session, sid)
            cwd = s.cwd if s else None
        if not cwd:
            raise HTTPException(404)

        def run(*args):
            return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)

        # git 的并发/超时风险在本地单用户场景可接受；命令白名单固定三条
        if run("rev-parse", "--is-inside-work-tree").stdout.strip() != "true":
            return {"is_repo": False}

        branch = run("branch", "--show-current").stdout.strip() or "(detached)"

        # 远端跟踪与 ahead/behind：status -sb 首行形如 "## mcp...origin/mcp [ahead 2]"
        upstream, ahead, behind = None, 0, 0
        head_line = run("status", "-sb").stdout.splitlines()[:1]
        if head_line and "..." in head_line[0]:
            tracking = head_line[0][3:].split(" ")
            upstream = tracking[0].split("...")[-1] or None
            if len(tracking) > 1 and "ahead" in tracking[1]:
                ahead = int(tracking[1].split("ahead ")[-1])
            if len(tracking) > 1 and "behind" in tracking[1]:
                behind = int(tracking[1].split("behind ")[-1])

        changes = []
        for line in run("status", "--porcelain").stdout.splitlines():
            if len(line) >= 4:
                changes.append({
                    "status": line[:2].strip(),
                    "staged": line[0] not in (" ", "?"),
                    "path": line[3:],
                })
        return {"is_repo": True, "branch": branch, "upstream": upstream,
                "ahead": ahead, "behind": behind, "changes": changes}

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
            # 只有客户端带 Last-Event-ID（断线重连）才回放历史；首次订阅只看实时
            cursor = int(last_event_id) if last_event_id is not None else None
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

            # 一次性授权：本轮用 override 模式跑，session.mode 不动
            turn_mode = body.mode_override or s.mode
            try:
                cmd = build_command(agent, s, body.text, mode=turn_mode)
            except ValueError as e:
                raise HTTPException(400, str(e))

            # 模式翻译的历史审计：turn 落库时就记录实际原生模式
            native = cmd[cmd.index("--permission-mode") + 1] if "--permission-mode" in cmd else None

            next_seq = (await db.scalar(
                select(func.max(Turn.seq)).where(Turn.session_id == sid)
            )) or 0
            turn = Turn(session_id=sid, seq=next_seq + 1, intent=DEFAULT_INTENT,
                        status="running", effective_mode=native, model=agent.model,
                        granted_from=body.granted_from)
            db.add(turn)
            await db.flush()

            # 消息在 turn 创建时立即落库（崩溃安全；刷新页面也能看到）。
            # 授权重跑（granted_from 非空）是系统代发的指令，role=system 不冒充用户提问
            msg_role = "system" if body.granted_from is not None else "user"
            msg_seq = (await db.scalar(
                select(func.max(Message.seq)).where(Message.session_id == sid)
            )) or 0
            db.add(Message(session_id=sid, turn_id=turn.id, seq=msg_seq + 1,
                           role=msg_role, channel="text",
                           content=json.dumps({"text": body.text}, ensure_ascii=False)))
            s.status = "running"
            await db.commit()
            turn_id = turn.id
            cwd = s.cwd

        if profile_supports_sdk(agent):
            from .sdk_runner import execute_turn_sdk

            background.add_task(
                execute_turn_sdk, sid, turn_id, body.text, cwd,
                turn_mode, s.agent_session_id, agent.model, agent.command,
            )
        else:
            background.add_task(execute_turn, sid, turn_id, body.text, cmd, cwd)
        return {"turn_id": turn_id, "status": "running"}
