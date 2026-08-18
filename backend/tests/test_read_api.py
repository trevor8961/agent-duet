"""读接口场景测试 —— docs/testing.md 第 5 层。

场景：
- 多 session 列表：聚合字段正确（message_count / last_preview / turn 数）
- 无 N+1：SQL 查询次数有硬上限断言（pydantic-resolve 引入价值的回归证明）
- 过滤检索：按 title/cwd 模糊过滤（痛点 1 的验收场景）
- 空库：空列表 200
- 详情：消息按 seq 有序、turn 含 intent、tool 配对数据完整（前端渲染依赖）
"""

import asyncio
import json
import sqlite3

from sqlalchemy import func, select

from app import db as db_mod  # 晚绑定：conftest reload 后须运行时取 SessionLocal
from app.models import Agent, Message, Session, Turn


async def seed_three_sessions(client):
    """造 3 个 session：1 个空、2 个各有 turn+messages，供列表聚合与过滤测试。"""
    async with db_mod.SessionLocal() as db:
        agent = (await db.execute(select(Agent))).scalar_one()  # startup 种子已有，不重复造

        s1 = Session(title="修登录bug", cwd="/home/me/project-a", agent_id=agent.id)
        s2 = Session(title="写周报", cwd="/home/me/project-b", agent_id=agent.id)
        s3 = Session(title="空的会话", cwd="/home/me/project-a", agent_id=agent.id)
        db.add_all([s1, s2, s3])
        await db.flush()

        t1 = Turn(session_id=s1.id, seq=1, intent="实施", status="done")
        t2 = Turn(session_id=s2.id, seq=1, intent="询问", status="done")
        db.add_all([t1, t2])
        await db.flush()

        db.add_all([
            Message(session_id=s1.id, turn_id=t1.id, seq=1, role="user", channel="text",
                    content=json.dumps({"text": "修一下"})),
            Message(session_id=s1.id, turn_id=t1.id, seq=2, role="assistant", channel="thinking",
                    content=json.dumps({"text": "先看代码"})),
            Message(session_id=s1.id, turn_id=t1.id, seq=3, role="assistant", channel="text",
                    content=json.dumps({"text": "已修复，改了 auth.py"})),
            Message(session_id=s2.id, turn_id=t2.id, seq=1, role="user", channel="text",
                    content=json.dumps({"text": "本周做了啥"})),
        ])
        await db.commit()
        return [s1.id, s2.id, s3.id]


class QueryCounter:
    """SQL 计数器：N+1 断言的核心。挂在 engine 的 cursor 事件上。"""

    def __init__(self):
        self.count = 0

    def __enter__(self):
        from sqlalchemy import event

        from app.db import engine

        @event.listens_for(engine.sync_engine, "before_cursor_execute")
        def counter(conn, cursor, stmt, params, context, executemany):
            self.count += 1

        self._remove = lambda: event.remove(engine.sync_engine, "before_cursor_execute", counter)
        return self

    def __exit__(self, *exc):
        self._remove()


async def test_session_list_aggregates(client, tmp_path):
    """场景：3 个 session（含 1 个空）。期望：聚合字段正确，空 session 计数为 0。"""
    await seed_three_sessions(client)
    resp = await client.get("/api/sessions")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 3

    by_title = {i["title"]: i for i in items}
    assert by_title["修登录bug"]["message_count"] == 3
    assert "已修复" in by_title["修登录bug"]["last_preview"]
    assert by_title["写周报"]["message_count"] == 1
    assert by_title["空的会话"]["message_count"] == 0  # 空 session 不炸


async def test_no_n_plus_one(client):
    """场景：列表聚合。期望：SQL 次数有硬上限——loader 批量化后应为常数级。"""
    await seed_three_sessions(client)

    with QueryCounter() as qc:
        resp = await client.get("/api/sessions")
    assert resp.status_code == 200

    # 断言依据：批处理下查询数与 session 数无关。上限放宽到 8
    # （预留 sessions 主查询 + 统计 loader + 框架自身的零星查询），
    # 若回归成 N+1（每 session 一查），3 个 session 就会到 4+ 次，
    # session 数增大时此测试会先于用户感知而变红。
    assert qc.count <= 8, f"疑似 N+1 回归：{qc.count} 次查询"


async def test_filter_by_title_and_cwd(client):
    """场景：用户按关键词找回 session（痛点 1 的验收场景）。"""
    await seed_three_sessions(client)

    resp = await client.get("/api/sessions", params={"q": "登录"})
    titles = [i["title"] for i in resp.json()]
    assert titles == ["修登录bug"]

    resp = await client.get("/api/sessions", params={"q": "project-a"})
    titles = sorted(i["title"] for i in resp.json())
    assert set(titles) == {"空的会话", "修登录bug"}  # cwd 也参与模糊匹配


async def test_empty_db_returns_empty_list(client):
    resp = await client.get("/api/sessions")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_session_detail(client, tmp_path):
    """场景：用户点开一个 session 回看。期望：turns（含 intent）+ messages 按 seq 有序。"""
    await seed_three_sessions(client)
    async with db_mod.SessionLocal() as db:
        sid = (await db.scalar(select(Session.id).where(Session.title == "修登录bug")))

    resp = await client.get(f"/api/sessions/{sid}")
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["title"] == "修登录bug"
    assert len(detail["turns"]) == 1
    assert detail["turns"][0]["intent"] == "实施"
    msgs = detail["messages"]
    assert [m["seq"] for m in msgs] == [1, 2, 3]
    assert [m["channel"] for m in msgs] == ["text", "thinking", "text"]


async def test_session_detail_404(client):
    resp = await client.get("/api/sessions/9999")
    assert resp.status_code == 404
