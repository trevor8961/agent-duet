"""编排层：把「用户发问」变成一次完整的 turn 落库。

职责（唯一）：
1. 建 turn（intent 占位「询问」，待意图判定模块）
2. 组装命令：profile.command + 模式翻译(mode_map) + --resume + --model
3. 子进程执行，stdout 逐行写 raw 文件（原始优先原则）
4. 进程结束后 parse_stream → 通用协议 → messages 落库，回填 turn/session

SSE 实时推送是下一步（本层先把数据收对）。
"""

import asyncio
import json
import shlex
from pathlib import Path

from sqlalchemy import func, select

from .bus import bus
from .db import DATA_DIR, SessionLocal
from .judge import JudgeInput, decide_outcome, make_claude_judge
from .models import Agent, Message, Session, Turn
from .parser import parse_stream

# 判定用的 LLM 工厂（注入点：测试换假实现，避免真调 claude）
_judge_factory = make_claude_judge

# 运行中进程注册表：session_id -> (proc, turn_id)，cancel 的作用对象
_running: dict[int, tuple] = {}
_cancel_flags: set[int] = set()  # 由 cancel 接口置位，execute_turn 收尾时消费

# 意图判定模块未落地前的占位（testing.md 第 4 层届时替换）
DEFAULT_INTENT = "询问"


def build_command(agent: Agent, session: Session, prompt: str) -> list[str]:
    """通用档位 → 原生参数的翻译发生在这里；返回值同时用于审计。"""
    mode_map = json.loads(agent.mode_map or "{}")
    if session.mode not in mode_map:
        # 显式失败，不静默 fallback（testing.md 第 3 层的场景之一）
        raise ValueError(f"mode '{session.mode}' 不在 profile '{agent.name}' 的 mode_map 中")

    cmd = shlex.split(agent.command)
    for flag, value in mode_map[session.mode].items():
        cmd += [f"--{flag}", value]
    if agent.model:
        cmd += ["--model", agent.model]
    if session.agent_session_id:
        cmd += ["--resume", session.agent_session_id]
    cmd += ["-p", prompt, "--output-format", "stream-json", "--verbose"]
    return cmd


async def execute_turn(session_id: int, turn_id: int, prompt: str, cmd: list[str], cwd: str) -> None:
    """跑子进程并把结果落库。作为后台任务被 fire，失败也要把 turn 置为 error。"""
    raw_dir = DATA_DIR / "raw" / str(session_id)
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / f"{turn_id}.jsonl"
    cmd_path = raw_dir / f"{turn_id}.cmd"  # 命令行审计（含 --resume 验证）

    lines: list[str] = []
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,  # stderr 是噪声源（实测），不进流水
    )
    _running[session_id] = (proc, turn_id)
    # 增量落盘 + 增量发布：running 期间即可观测（L5 冒烟发现的可观测性缺陷）
    with open(raw_path, "w") as f:
        async for raw_line in proc.stdout:
            line = raw_line.decode(errors="replace").rstrip("\n")
            lines.append(line)
            f.write(line + "\n")
            f.flush()
            if line.startswith("{"):
                await bus.publish(session_id, "line", line)
    await proc.wait()
    cancelled = session_id in _cancel_flags
    _running.pop(session_id, None)
    _cancel_flags.discard(session_id)

    cmd_path.write_text(" ".join(shlex.quote(c) for c in cmd))

    if cancelled:
        async with SessionLocal() as db:
            turn = await db.get(Turn, turn_id)
            turn.status = "cancelled"
            turn.raw_path = str(raw_path)
            session = await db.get(Session, session_id)
            session.status = "cancelled"
            await db.commit()
        await bus.publish(session_id, "turn_done", {"turn_id": turn_id, "status": "cancelled"})
        return

    result = parse_stream(lines)

    # 分层语义判定（docs/testing.md L5 发现）：拒绝过≠失败，歧义区 LLM 兜底
    final_text = next(
        (json.loads(m.content).get("text", "") for m in reversed(result.messages)
         if m.channel == "text" and m.role == "assistant"),
        "",
    )
    judge = _judge_factory(cmd[0])  # 判定用同一个 agent（cmd[0] 是可执行命令）
    status, source = await decide_outcome(
        JudgeInput(
            is_error=result.is_error,
            denied_count=len(result.permission_denials),
            user_prompt=prompt,
            final_text=final_text,
        ),
        llm=judge,
    )

    async with SessionLocal() as db:
        # seq 接续：取当前最大值（并发 turn 不存在——每 session 同时只跑一个）
        max_seq = (await db.scalar(select(func.max(Message.seq)).where(Message.session_id == session_id))) or 0
        rows = [
            Message(session_id=session_id, turn_id=turn_id, seq=max_seq + 1,
                    role="user", channel="text",
                    content=json.dumps({"text": prompt}, ensure_ascii=False))
        ]
        for m in result.messages:
            max_seq += 1
            rows.append(Message(session_id=session_id, turn_id=turn_id, seq=max_seq + 1,
                                role=m.role, channel=m.channel, content=m.content,
                                tool_use_id=m.tool_use_id))
        db.add_all(rows)

        turn = await db.get(Turn, turn_id)
        turn.status = status
        turn.outcome_source = source
        turn.denied_count = len(result.permission_denials)
        turn.total_cost_usd = result.total_cost_usd
        turn.num_turns = result.num_turns
        turn.duration_ms = result.duration_ms
        turn.raw_path = str(raw_path)

        await bus.publish(session_id, "turn_done", {"turn_id": turn_id, "status": status})

        if status == "error":
            session = await db.get(Session, session_id)
            session.status = "error"
        elif result.agent_session_id:
            session = await db.get(Session, session_id)
            session.agent_session_id = result.agent_session_id
            session.status = "done"
        await db.commit()
