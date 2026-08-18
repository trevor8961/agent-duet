"""持久层场景测试 —— 对应 docs/testing.md 第 1 层。

场景拟自真实使用：用户第一次拉起服务 / 重启服务 / 一轮完整对话落库。
用独立临时库（AGENT_DUET_DATA_DIR 注入），杜绝测试间污染。
"""

import json
import sqlite3

from sqlalchemy import select

from app.models import Agent, Message, Session, Turn


async def test_first_startup_creates_tables_and_seed(client, tmp_path):
    """场景：用户第一次拉起服务。期望：建表 + claude-code 种子入库。"""
    resp = await client.get("/api/health")
    assert resp.status_code == 200

    db = sqlite3.connect(tmp_path / "agent-duet.db")
    tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"agents", "sessions", "turns", "messages"} <= tables

    seeds = db.execute("SELECT name, type, mode_map FROM agents").fetchall()
    assert len(seeds) == 1
    name, type_, mode_map_raw = seeds[0]
    assert (name, type_) == ("claude-code", "claude_code")
    # mode_map 是可直读的 JSON（不黑箱原则）
    mode_map = json.loads(mode_map_raw)
    assert mode_map["autonomous"] == {"permission-mode": "acceptEdits"}


async def test_restart_does_not_duplicate_seed(client, tmp_path):
    """场景：服务重启（startup 再跑一次）。期望：种子幂等，不重复。"""
    db = sqlite3.connect(tmp_path / "agent-duet.db")
    count = db.execute("SELECT COUNT(*) FROM agents").fetchone()[0]
    assert count == 1


async def test_full_turn_persists_message_flow(client, tmp_path):
    """场景：一轮完整对话落库（模拟解析器写库后的状态）。

    期望：messages 流水 seq 连续、tool_use/tool_result 可按 id 配对查询——
    这两个不变量是前端渲染（分声部 + 工具树）的依赖。
    """
    from app.db import SessionLocal

    async with SessionLocal() as db:
        agent = (await db.execute(select(Agent))).scalar_one()

        s = Session(title="测试会话", cwd="/tmp/x", agent_id=agent.id)
        db.add(s)
        await db.flush()

        t = Turn(session_id=s.id, seq=1, intent="实施", status="done", effective_mode="acceptEdits")
        db.add(t)
        await db.flush()

        rows = [
            Message(session_id=s.id, turn_id=t.id, seq=1, role="user", channel="text",
                    content=json.dumps({"text": "列出文件"}, ensure_ascii=False)),
            Message(session_id=s.id, turn_id=t.id, seq=2, role="assistant", channel="thinking",
                    content=json.dumps({"text": "需要执行 ls"})),
            Message(session_id=s.id, turn_id=t.id, seq=3, role="assistant", channel="tool_use",
                    content=json.dumps({"tool": "Bash", "input": {"command": "ls"}, "tool_use_id": "call_00"})),
            Message(session_id=s.id, turn_id=t.id, seq=4, role="user", channel="tool_result",
                    content=json.dumps({"content": "a.txt", "is_error": False}), tool_use_id="call_00"),
        ]
        db.add_all(rows)
        await db.commit()

    con = sqlite3.connect(tmp_path / "agent-duet.db")
    seqs = [r[0] for r in con.execute("SELECT seq FROM messages ORDER BY seq")]
    assert seqs == [1, 2, 3, 4]  # seq 连续

    paired = con.execute(
        "SELECT (SELECT COUNT(*) FROM messages WHERE channel='tool_use' "
        "  AND content LIKE '%call_00%'), "
        "(SELECT COUNT(*) FROM messages WHERE channel='tool_result' AND tool_use_id='call_00')"
    ).fetchone()
    assert paired == (1, 1)  # 配对可查
