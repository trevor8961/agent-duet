"""读侧视图组装（pydantic-resolve Core API）。

为什么用 resolve_* 而不是手拼 GROUP BY：跨行聚合（计数/末条预览）声明式化，
loader 由框架自动批处理，N+1 免疫（tests/test_read_api.py 有 SQL 计数断言守护）。
"""

import json
from typing import Optional

from pydantic import BaseModel
from pydantic_resolve import Loader, Resolver
from sqlalchemy import func, select

from .db import SessionLocal
from .models import Message, Session, Turn


async def session_stats_loader(session_ids: list[int]) -> list[Optional[dict]]:
    """一次批量取每个 session 的消息数与最后一条 assistant 回复的预览。

    返回顺序与入参 session_ids 一一对应（pydantic-resolve loader 契约）。
    """
    if not session_ids:
        return []
    async with SessionLocal() as db:
        counts = dict(
            (await db.execute(
                select(Message.session_id, func.count(Message.id))
                .where(Message.session_id.in_(session_ids))
                .group_by(Message.session_id)
            )).all()
        )
        last_text_seq = dict(
            (await db.execute(
                select(Message.session_id, func.max(Message.seq))
                .where(
                    Message.channel == "text",
                    Message.role == "assistant",
                    Message.session_id.in_(session_ids),
                )
                .group_by(Message.session_id)
            )).all()
        )
        previews = {}
        if last_text_seq:
            rows = (await db.execute(
                select(Message.session_id, Message.seq, Message.content).where(
                    Message.channel == "text",
                    Message.role == "assistant",
                    Message.session_id.in_(session_ids),
                )
            )).all()
            for sid, seq, content in rows:
                if seq == last_text_seq[sid]:
                    previews[sid] = content

    return [
        {
            "message_count": counts.get(sid, 0),
            "last_preview": _preview(previews.get(sid)),
        }
        for sid in session_ids
    ]


def _preview(content: str | None, limit: int = 60) -> str:
    if not content:
        return ""
    try:
        return json.loads(content).get("text", "")[:limit]
    except json.JSONDecodeError:
        return ""


class SessionListItem(BaseModel):
    id: int
    title: str
    cwd: str
    mode: str
    status: str
    agent_session_id: Optional[str] = None
    created_at: str
    updated_at: str

    stats: dict = {}  # loader 一次批量取回的聚合数据
    message_count: int = 0
    last_preview: str = ""

    def resolve_stats(self, loader=Loader(session_stats_loader)):
        return loader.load(self.id)

    def post_message_count(self):
        return self.stats.get("message_count", 0)

    def post_last_preview(self):
        return self.stats.get("last_preview", "")


async def list_sessions(q: str | None = None) -> list[SessionListItem]:
    async with SessionLocal() as db:
        stmt = select(Session).order_by(Session.updated_at.desc())
        if q:
            stmt = stmt.where(Session.title.contains(q) | Session.cwd.contains(q))
        rows = (await db.execute(stmt)).scalars().all()
        items = [
            SessionListItem(
                id=s.id, title=s.title, cwd=s.cwd, mode=s.mode, status=s.status,
                agent_session_id=s.agent_session_id,
                created_at=str(s.created_at), updated_at=str(s.updated_at),
            )
            for s in rows
        ]
    return await Resolver().resolve(items)


async def get_session_detail(session_id: int) -> dict | None:
    """详情：turns（分析单元）+ messages（通用协议流水，前端按 channel 分声部渲染）。"""
    async with SessionLocal() as db:
        s = await db.get(Session, session_id)
        if not s:
            return None
        turns = (await db.execute(
            select(Turn).where(Turn.session_id == session_id).order_by(Turn.seq)
        )).scalars().all()
        messages = (await db.execute(
            select(Message).where(Message.session_id == session_id).order_by(Message.seq)
        )).scalars().all()

    return {
        "id": s.id, "title": s.title, "cwd": s.cwd, "mode": s.mode, "status": s.status,
        "agent_session_id": s.agent_session_id,
        "created_at": str(s.created_at),
        "turns": [
            {"id": t.id, "seq": t.seq, "intent": t.intent, "status": t.status,
             "effective_mode": t.effective_mode, "total_cost_usd": t.total_cost_usd,
             "num_turns": t.num_turns, "duration_ms": t.duration_ms}
            for t in turns
        ],
        "messages": [
            {"seq": m.seq, "turn_id": m.turn_id, "role": m.role, "channel": m.channel,
             "content": m.content, "tool_use_id": m.tool_use_id}
            for m in messages
        ],
    }
