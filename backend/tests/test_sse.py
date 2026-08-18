"""SSE 实时推送场景测试 —— docs/testing.md 第 6 层。

场景：用户在页面盯着一个正在跑的 turn。期望：
- SSE 能在 turn 运行期间逐条收到事件（实时性，不是收完一次性吐）
- 事件有序（thinking 在 text 前）
- turn_done 收尾事件最后到达，携带最终状态
- 断线重连：带 Last-Event-ID 游标可补发错过的事件
"""

import asyncio
import json
import sqlite3
from pathlib import Path

import httpx

SAMPLES = Path(__file__).resolve().parent.parent.parent / "docs" / "samples"
SLOW_FAKE = Path(__file__).resolve().parent / "fake_claude_slow.sh"


async def _setup_and_fire(client, tmp_path):
    agents = (await client.get("/api/agents")).json()
    agent_id = agents[0]["id"]
    await client.patch(f"/api/agents/{agent_id}", json={"command": f"{SLOW_FAKE} {SAMPLES / '01-plain.jsonl'}"})
    resp = await client.post(
        "/api/sessions",
        json={"title": "sse测试", "cwd": str(tmp_path), "agent_id": agent_id, "mode": "guided"},
    )
    sid = resp.json()["id"]
    # 先挂上 SSE 消费者，再发消息（保证能观察到运行中事件）
    return sid


async def _collect_events(client, sid, stop_at_done=True):
    events = []
    async with client.stream("GET", f"/api/sessions/{sid}/events") as resp:
        assert resp.status_code == 200
        async for line in resp.aiter_lines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
                if stop_at_done and events[-1].get("kind") == "turn_done":
                    break
    return events


async def test_sse_streams_events_in_realtime(client, tmp_path):
    """场景：turn 运行中，SSE 持续有产出（01 样本 39 行 × 0.2s ≈ 8s，
    若实现退化成「收完再吐」，收尾事件和内容事件会同时到——
    用 turn_done 与首个内容事件的时间差断言实时性）。"""
    sid = await _setup_and_fire(client, tmp_path)

    task = asyncio.create_task(_collect_events(client, sid))
    await asyncio.sleep(1.0)  # 让 SSE 先就位
    await client.post(f"/api/sessions/{sid}/messages", json={"text": "hi"})

    events = await task
    kinds = [e.get("kind") for e in events]
    assert "turn_done" in kinds
    assert kinds[-1] == "turn_done"
    assert kinds.count("line") > 0  # 有原始事件行推过来

    # 实时性：首个 line 事件到达时 turn_done 还没发生（时间戳单调）
    ts = [e["ts"] for e in events if e.get("ts")]
    assert ts == sorted(ts)
    first_line = next(e for e in events if e.get("kind") == "line")
    done = events[-1]
    assert done["ts"] - first_line["ts"] > 0.5  # 间隔显著大于 0（非一次性吐）


async def test_sse_replay_from_cursor(client, tmp_path):
    """场景：用户刷新页面（SSE 断开重连）。期望：带 Last-Event-ID 补发错过的事件。"""
    sid = await _setup_and_fire(client, tmp_path)
    await client.post(f"/api/sessions/{sid}/messages", json={"text": "hi"})

    # 第一段：只消费前几条就断开
    first_batch = []
    async with client.stream("GET", f"/api/sessions/{sid}/events") as resp:
        async for line in resp.aiter_lines():
            if line.startswith("id: "):
                first_batch.append(int(line[4:]))
            elif line.startswith("data: ") and line[6:].startswith('{"kind": "turn_done"'):
                break
            if len(first_batch) >= 3:
                break

    cursor = first_batch[-1]
    # 第二段：从游标续消费
    events = []
    async with client.stream(
        "GET", f"/api/sessions/{sid}/events", headers={"Last-Event-ID": str(cursor)}
    ) as resp:
        async for line in resp.aiter_lines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
                if events[-1].get("kind") == "turn_done":
                    break
    ids = [e["id"] for e in events]
    assert ids[0] == cursor + 1  # 从断点续上，不丢不重
    assert events[-1]["kind"] == "turn_done"
