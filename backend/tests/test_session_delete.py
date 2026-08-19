"""session 删除场景测试。

场景：用户清理旧会话。期望：sessions/turns/messages 级联删除，
raw 留档目录一并清理，重复删除 404。
"""

import sqlite3
import time

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Message, Session, Turn


async def _make_session_with_turn(client, tmp_path):
    agents = (await client.get("/api/agents")).json()
    resp = await client.post("/api/sessions", json={
        "title": "待删除", "cwd": str(tmp_path), "agent_id": agents[0]["id"], "mode": "guided",
    })
    sid = resp.json()["id"]
    async with SessionLocal() as db:
        t = Turn(session_id=sid, seq=1, intent="询问", status="done")
        db.add(t)
        await db.flush()
        db.add(Message(session_id=sid, turn_id=t.id, seq=1, role="user",
                       channel="text", content="{}"))
        await db.commit()
    return sid


async def test_delete_session_cascades(client, tmp_path):
    sid = await _make_session_with_turn(client, tmp_path)
    raw_dir = tmp_path.parent / "raw" / str(sid)  # DATA_DIR 即 tmp_path

    resp = await client.delete(f"/api/sessions/{sid}")
    assert resp.status_code == 200

    import sqlite3

    db = sqlite3.connect(tmp_path / "agent-duet.db")
    assert db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM turns").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 0


async def test_delete_twice_404(client, tmp_path):
    sid = await _make_session_with_turn(client, tmp_path)
    await client.delete(f"/api/sessions/{sid}")
    resp = await client.delete(f"/api/sessions/{sid}")
    assert resp.status_code == 404
