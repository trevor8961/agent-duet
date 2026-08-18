"""编排层场景测试 —— docs/testing.md 第 6 层。

进程边界 mock：tests/fake_claude.sh 回放 samples 实况数据扮演 claude code
（command 是 profile 数据，测试里直接把 profile 指到假脚本，不需要代码级 mock）。

场景：
- 建档 + 发问 → 后台跑完 → 分声部落库、turn 元数据、raw 文件留存
- 权限拒绝样本 → turn=error
- 续接（agent_session_id 已存在）→ 不新建 session、命令带 --resume
"""

import asyncio
import json
import sqlite3
from pathlib import Path

SAMPLES = Path(__file__).resolve().parent.parent.parent / "docs" / "samples"
FAKE_CLAUDE = Path(__file__).resolve().parent / "fake_claude.sh"


async def wait_turn_done(tmp_path, timeout=10.0):
    """轮询 DB 等 turn 收尾。编排是后台任务，测试用状态收敛代替 sleep。"""
    db = sqlite3.connect(tmp_path / "agent-duet.db")
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        row = db.execute("SELECT status FROM turns").fetchone()
        if row and row[0] in ("done", "error", "denied"):
            return row[0]
        await asyncio.sleep(0.05)
    raise TimeoutError("turn 未在时限内收尾")


async def create_session_with_fake_claude(client, tmp_path, sample="02-tool-use.jsonl"):
    """建档：profile 指向假脚本（回放指定采样）。返回 session id。"""
    agents = (await client.get("/api/agents")).json()
    agent_id = agents[0]["id"]
    await client.patch(f"/api/agents/{agent_id}", json={"command": f"{FAKE_CLAUDE} {SAMPLES / sample}"})
    resp = await client.post(
        "/api/sessions",
        json={"title": "编排测试", "cwd": str(tmp_path), "agent_id": agent_id, "mode": "guided"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


async def test_post_message_persists_full_turn(client, tmp_path):  # noqa: F811
    """场景：用户发问（回放 02 工具采样）。

    期望：session/turn/messages 全部落库；tool 配对；心跳零落库；
    raw 文件留存（原始优先原则）。
    """
    sid = await create_session_with_fake_claude(client, tmp_path)
    resp = await client.post(f"/api/sessions/{sid}/messages", json={"text": "当前目录下有哪些文件？"})
    assert resp.status_code == 202

    status = await wait_turn_done(tmp_path)
    assert status == "done"

    db = sqlite3.connect(tmp_path / "agent-duet.db")
    turn = db.execute("SELECT status, intent, raw_path FROM turns").fetchone()
    assert turn[0] == "done"
    assert turn[1]  # intent 有值（v1 占位「询问」，字段不可空）
    assert Path(turn[2]).exists()  # raw 事件流留档

    rows = db.execute("SELECT channel, role FROM messages ORDER BY seq").fetchall()
    channels = [r[0] for r in rows]
    assert channels.count("tool_use") == 1
    assert channels.count("tool_result") == 1
    assert "thinking" in channels and "text" in channels  # 分声部
    # 用户输入由编排层落库（事件流里没有）
    assert rows[0] == ("text", "user")

    # agent_session_id 已回填（后续 --resume 的依据）；id 从样本 init 事件动态提取，
    # 避免硬编码——样本重新采集时 id 会变（已经吃过一次亏）
    expected_sid = next(
        json.loads(l)["session_id"]
        for l in (SAMPLES / "02-tool-use.jsonl").read_text().splitlines()
        if l.startswith("{") and json.loads(l).get("subtype") == "init"
    )
    sid_db = db.execute("SELECT agent_session_id FROM sessions").fetchone()[0]
    assert sid_db == expected_sid


async def test_permission_denial_marks_error(client, tmp_path, monkeypatch):  # noqa: F811
    """场景：回放 04 权限拒绝采样。期望：turn=error。

    判定注入假 LLM（返回 error）——不依赖假脚本回放内容的碰巧解析。
    """
    import app.runner as runner_mod

    def fake_judge_factory(command):
        async def llm(inp):
            return "error"

        return llm

    monkeypatch.setattr(runner_mod, "_judge_factory", fake_judge_factory)

    sid = await create_session_with_fake_claude(client, tmp_path, "04-error.jsonl")
    await client.post(f"/api/sessions/{sid}/messages", json={"text": "读一个没权限的文件"})
    status = await wait_turn_done(tmp_path)
    assert status == "denied"  # 被拒且未完成：denied 而非 error（语义修正）

    import sqlite3

    db = sqlite3.connect(tmp_path / "agent-duet.db")
    src = db.execute("SELECT outcome_source, denied_count FROM turns").fetchone()
    assert src == ("llm", 1)  # 歧义区确实走了 LLM 判定


async def test_resume_passes_session_id(client, tmp_path):  # noqa: F811
    """场景：session 已有 agent_session_id，再次发问。

    期望：假脚本收到 --resume 参数（续接而非新开）。
    """
    sid = await create_session_with_fake_claude(client, tmp_path)
    db = sqlite3.connect(tmp_path / "agent-duet.db")
    db.execute("UPDATE sessions SET agent_session_id='abc-123' WHERE id=?", (sid,))
    db.commit()

    await client.post(f"/api/sessions/{sid}/messages", json={"text": "继续刚才的话题"})
    await wait_turn_done(tmp_path)

    # 命令行审计：raw 目录同级留有 invocations 记录（编排层写入）
    invoc = list((tmp_path / "raw").rglob("*.cmd"))
    assert invoc, "缺少命令行审计文件"
    cmd = invoc[0].read_text()
    assert "--resume" in cmd and "abc-123" in cmd
