"""轮次级一次性授权测试。

场景：agent 被拒（denied），用户点「授权并继续」。
期望：本轮以 autonomous 执行（session.mode 不变），
授权链 granted_from 落库；无效 override 被拒。
"""

import sqlite3
from pathlib import Path

FAKE = Path(__file__).resolve().parent / "fake_claude.sh"
SAMPLES = Path(__file__).resolve().parent.parent.parent / "docs" / "samples"


async def test_mode_override_one_turn_only(client, tmp_path):
    agents = (await client.get("/api/agents")).json()
    agent_id = agents[0]["id"]
    await client.patch(f"/api/agents/{agent_id}", json={"command": f"{FAKE} {SAMPLES / '01-plain.jsonl'}"})
    resp = await client.post("/api/sessions", json={
        "title": "授权", "cwd": str(tmp_path), "agent_id": agent_id, "mode": "guided",
    })
    sid = resp.json()["id"]

    resp = await client.post(f"/api/sessions/{sid}/messages", json={
        "text": "继续执行被拒的文件操作",
        "mode_override": "autonomous",
        "granted_from": 123,
    })
    assert resp.status_code == 202, resp.text

    import asyncio

    for _ in range(60):
        db = sqlite3.connect(tmp_path / "agent-duet.db")
        row = db.execute("SELECT status FROM turns").fetchone()
        if row and row[0] in ("done", "error", "denied"):
            break
        await asyncio.sleep(0.1)

    db = sqlite3.connect(tmp_path / "agent-duet.db")
    eff_mode, granted = db.execute("SELECT effective_mode, granted_from FROM turns").fetchone()
    assert eff_mode == "acceptEdits"  # 本轮实际用 autonomous 翻译后的原生模式
    assert granted == 123  # 授权链留痕

    # 会话模式不被永久更改（一次性授权的核心约束）
    mode = db.execute("SELECT mode FROM sessions").fetchone()[0]
    assert mode == "guided"


async def test_invalid_mode_override_rejected(client, tmp_path):
    agents = (await client.get("/api/agents")).json()
    resp = await client.post("/api/sessions", json={
        "title": "x", "cwd": str(tmp_path), "agent_id": agents[0]["id"], "mode": "guided",
    })
    sid = resp.json()["id"]
    resp = await client.post(f"/api/sessions/{sid}/messages", json={
        "text": "hi", "mode_override": "yolo",
    })
    assert resp.status_code == 400
