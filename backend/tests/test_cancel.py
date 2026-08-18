"""cancel 场景测试 —— docs/testing.md 第 6 层（截断流）。

场景：用户在 agent 跑到一半时点停止。期望：
- 子进程被终止，turn 状态 cancelled
- 已产出的部分保留（原始优先原则兜底）

注：不用 SSE 断言活性——ASGITransport 会缓冲流式响应（假实时），
turn 状态以 DB 为准。
"""

import asyncio
import sqlite3
from pathlib import Path

SAMPLES = Path(__file__).resolve().parent.parent.parent / "docs" / "samples"
SLOW_FAKE = Path(__file__).resolve().parent / "fake_claude_slow.sh"


async def _turn_status(tmp_path) -> str | None:
    db = sqlite3.connect(tmp_path / "agent-duet.db")
    try:
        row = db.execute("SELECT status FROM turns ORDER BY id DESC LIMIT 1").fetchone()
        return row[0] if row else None
    finally:
        db.close()


async def test_cancel_mid_run(client, tmp_path):
    agents = (await client.get("/api/agents")).json()
    agent_id = agents[0]["id"]
    await client.patch(f"/api/agents/{agent_id}", json={"command": f"{SLOW_FAKE} {SAMPLES / '01-plain.jsonl'}"})
    resp = await client.post(
        "/api/sessions",
        json={"title": "cancel测试", "cwd": str(tmp_path), "agent_id": agent_id, "mode": "guided"},
    )
    sid = resp.json()["id"]

    # ASGITransport 下 post 会等 BackgroundTasks 完成才返回，必须并发发
    poster = asyncio.create_task(
        client.post(f"/api/sessions/{sid}/messages", json={"text": "长任务"})
    )

    # 等 turn 进入 running
    for _ in range(50):
        if await _turn_status(tmp_path) == "running":
            break
        await asyncio.sleep(0.1)
    assert await _turn_status(tmp_path) == "running"

    resp = await client.post(f"/api/sessions/{sid}/cancel")
    assert resp.status_code == 200

    await asyncio.wait_for(poster, timeout=10)
    assert await _turn_status(tmp_path) == "cancelled"

    # 已产出部分保留：raw 文件存在且非空（原始优先原则）
    raw = list((tmp_path / "raw").rglob("*.jsonl"))
    assert raw and raw[0].stat().st_size > 0

    # 回看场景（用户实测踩坑）：取消的 turn 也必须有 messages 落库，
    # 否则点开历史会话一片空白
    db = sqlite3.connect(tmp_path / "agent-duet.db")
    rows = db.execute("SELECT role, channel FROM messages ORDER BY seq").fetchall()
    channels = [r[1] for r in rows]
    assert ("user", "text") in rows, "用户输入必须落库"
    assert "thinking" in channels or "text" in channels, "已产出的 agent 输出必须落库"


async def test_cancel_without_running_turn(client, tmp_path):
    """场景：没有在跑的 turn 时点停止。期望：幂等成功，不炸。"""
    agents = (await client.get("/api/agents")).json()
    resp = await client.post(
        "/api/sessions",
        json={"title": "空", "cwd": str(tmp_path), "agent_id": agents[0]["id"], "mode": "guided"},
    )
    sid = resp.json()["id"]
    resp = await client.post(f"/api/sessions/{sid}/cancel")
    assert resp.status_code == 200
    assert resp.json()["status"] == "idle"
