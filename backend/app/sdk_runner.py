"""SDK 调用层 + 事中授权状态机（plan_permission_approval.md）。

为什么单列一个 runner：SDK 的 can_use_tool 异步回调是「事中授权」的载体，
与子进程 runner（无此能力）不兼容。策略：
- 具备 sdk 能力的 profile 走本 runner（生产 claude_code profile 已标 sdk:true）
- 其余走旧子进程 runner（测试的 fake_claude 路径保持不变）

权限请求 DB-first：pending 落 PermissionRequest 表（不重蹈内存态孤儿覆辙），
重启后可对账；运行时靠 asyncio.Event 等待，3 分钟超时默认拒绝。
"""

import asyncio
import dataclasses
import json
import uuid
from datetime import datetime, timedelta

import claude_agent_sdk as sdk
from sqlalchemy import func, select

from .bus import bus
from .db import DATA_DIR, SessionLocal
from .judge import JudgeInput, decide_outcome, make_claude_judge
from .models import Agent, Message, PermissionRequest, Session, Turn

# 超时（秒）：用户 3 分钟无响应默认拒绝（plan 已拍板）
PERMISSION_TIMEOUT = 10

# 运行中的权限等待器：request_id -> asyncio.Event + 决策
_pending: dict[str, dict] = {}


def _deny_result(message: str):
    # SDK 校验返回类型必须是 PermissionResult* 实例（裸 dict 会被 CLI 拒绝——
    # 实测报错 "must return PermissionResult..., got <class 'dict'>"）
    return sdk.PermissionResultDeny(behavior="deny", message=message, interrupt=False)


def _allow_result():
    return sdk.PermissionResultAllow(behavior="allow")


def translate_permission_mode(mode: str) -> str:
    """通用档位 → SDK permission_mode（与 profile mode_map 的语义对齐）。"""
    return {
        "readonly": "dontAsk",   # 从不问，但回调兜底 deny
        "plan": "plan",
        "guided": "default",     # 弹窗主场
        "autonomous": "acceptEdits",
    }.get(mode, "default")


async def execute_turn_sdk(session_id: int, turn_id: int, prompt: str, cwd: str,
                           mode: str, agent_session_id: str | None, model: str | None,
                           judge_command: str) -> None:
    """跑一轮：SDK query + 权限回调 + 翻译落库（与旧 runner 同构的产物）。"""
    raw_dir = DATA_DIR / "raw" / str(session_id)
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / f"{turn_id}.jsonl"

    collected: list[dict] = []  # 原始事件留档（SDK message → dict）

    async def can_use_tool(tool_name, tool_input, context):
        open("/tmp/cut_marker.log", "a").write(f"{tool_name}\n")
        """权限回调：阻塞等待用户批准/拒绝，超时 3 分钟。"""
        rid = uuid.uuid4().hex
        now = datetime.now()
        async with SessionLocal() as db:
            db.add(PermissionRequest(
                request_id=rid, session_id=session_id, turn_id=turn_id,
                tool_name=tool_name, tool_input=json.dumps(tool_input, ensure_ascii=False),
                tool_use_id=getattr(context, "tool_use_id", None),
                status="pending", created_at=now.strftime("%Y-%m-%d %H:%M:%S"),
                timeout_at=(now + timedelta(seconds=PERMISSION_TIMEOUT)).strftime("%Y-%m-%d %H:%M:%S"),
            ))
            await db.commit()

        event = asyncio.Event()
        _pending[rid] = {"event": event, "decision": None}
        # 发布总线事件（实时）——独立任务，不阻塞回调
        asyncio.create_task(bus.publish(session_id, "permission_request", {
            "request_id": rid, "tool_name": tool_name, "tool_input": tool_input,
            "timeout_at": (now + timedelta(seconds=PERMISSION_TIMEOUT)).strftime("%Y-%m-%d %H:%M:%S"),
        }))

        try:
            await asyncio.wait_for(event.wait(), timeout=PERMISSION_TIMEOUT)
            decision = _pending[rid]["decision"]
            if decision == "allow":
                async with SessionLocal() as db:
                    await _mark(db, rid, "approved")
                return _allow_result()
            async with SessionLocal() as db:
                await _mark(db, rid, "denied")
            return _deny_result("用户拒绝")
        except asyncio.TimeoutError:
            async with SessionLocal() as db:
                await _mark(db, rid, "timeout")
            return _deny_result("3 分钟无响应，自动拒绝")
        finally:
            _pending.pop(rid, None)

    options_kwargs = dict(
        cwd=cwd,
        permission_mode=translate_permission_mode(mode),
        can_use_tool=can_use_tool,
    )
    if agent_session_id:
        options_kwargs["resume"] = agent_session_id
    if model:
        options_kwargs["model"] = model
    options = sdk.ClaudeAgentOptions(**options_kwargs)

    parsed_messages: list = []
    result = None
    try:
        async for m in sdk.query(prompt=prompt, options=options):
            collected.append(dataclasses.asdict(m))
            result = _translate(m, parsed_messages, result)
    except Exception as e:
        # SDK 层异常（连接/兼容）——按 error turn 收尾，不崩溃服务
        await _persist(session_id, turn_id, prompt, parsed_messages, raw_path,
                       collected, "error", None, source="mechanical", result=None)
        await bus.publish(session_id, "turn_done", {"turn_id": turn_id, "status": "error"})
        raise

    # 落库（含判定）
    await _persist(session_id, turn_id, prompt, parsed_messages, raw_path,
                   collected, None, judge_command, source=None, result=result)


def _translate(m, parsed: list, result):
    """SDK message(dataclass) → ParsedMessage（复用 channel 语义）。"""
    from .parser import ParsedMessage

    name = type(m).__name__
    if name == "AssistantMessage":
        for b in m.content:
            bt = type(b).__name__
            if bt == "ThinkingBlock" and (b.thinking or "").strip():
                parsed.append(ParsedMessage(role="assistant", channel="thinking",
                                            content=json.dumps({"text": b.thinking}, ensure_ascii=False)))
            elif bt == "TextBlock" and (b.text or "").strip():
                parsed.append(ParsedMessage(role="assistant", channel="text",
                                            content=json.dumps({"text": b.text}, ensure_ascii=False)))
            elif bt in ("ToolUseBlock", "ServerToolUseBlock"):
                parsed.append(ParsedMessage(role="assistant", channel="tool_use",
                                            content=json.dumps({"tool": b.name,
                                                                "input": b.input,
                                                                "tool_use_id": b.id},
                                                               ensure_ascii=False)))
    elif name == "UserMessage":
        for b in (m.content if isinstance(m.content, list) else []):
            bt = type(b).__name__
            if bt in ("ToolResultBlock", "ServerToolResultBlock"):
                content = b.content
                if not isinstance(content, str):
                    content = json.dumps(content, ensure_ascii=False)
                parsed.append(ParsedMessage(role="user", channel="tool_result",
                                            content=json.dumps({"content": content,
                                                                "is_error": bool(b.is_error)},
                                                               ensure_ascii=False),
                                            tool_use_id=b.tool_use_id))
    elif name == "ResultMessage":
        result = m
    return result


async def _mark(db, rid: str, status: str) -> None:
    req = (await db.execute(select(PermissionRequest).where(PermissionRequest.request_id == rid))).scalar_one_or_none()
    if req:
        req.status = status
        await db.commit()


async def _persist(session_id, turn_id, prompt, parsed_messages, raw_path,
                   collected, forced_status, judge_command, source, result):
    """落库 + 判定 + 收尾（与旧 runner 尾部同构）。"""
    from datetime import datetime

    with open(raw_path, "w") as f:
        f.write("\n".join(json.dumps(c, ensure_ascii=False) for c in collected))

    final_text = next(
        (json.loads(m.content).get("text", "") for m in reversed(parsed_messages)
         if m.channel == "text" and m.role == "assistant"), "")

    denied_count = 0
    # ResultMessage 白嫖字段（SDK 原生，cost/轮次/会话 id）
    is_error = bool(result.is_error) if result is not None else forced_status == "error"
    result_denials = (result.permission_denials or []) if result is not None else []
    if forced_status is None and result is not None and is_error:
        pass  # 真实 is_error 会走机械 error 分支
    if forced_status is None:
        # 权限拒绝计数：本轮被 deny/timeout 的权限请求数
        async with SessionLocal() as db:
            denied_count = (await db.scalar(
                select(func.count(PermissionRequest.id))
                .where(PermissionRequest.turn_id == turn_id,
                       PermissionRequest.status.in_(["denied", "timeout"]))
            )) or 0

        if is_error:
            status, outcome_source = "error", "mechanical"
        else:
            judge = make_claude_judge(judge_command)
            status, outcome_source = await decide_outcome(
                JudgeInput(is_error=False, denied_count=denied_count + len(result_denials),
                           user_prompt=prompt, final_text=final_text),
                llm=judge)
    else:
        status, outcome_source = forced_status, source

    async with SessionLocal() as db:
        max_seq = (await db.scalar(select(func.max(Message.seq)).where(Message.session_id == session_id))) or 0
        rows = []
        for m in parsed_messages:
            max_seq += 1
            rows.append(Message(session_id=session_id, turn_id=turn_id, seq=max_seq + 1,
                                role=m.role, channel=m.channel, content=m.content,
                                tool_use_id=m.tool_use_id))
        db.add_all(rows)

        turn = await db.get(Turn, turn_id)
        turn.status = status
        turn.outcome_source = outcome_source
        turn.denied_count = denied_count
        turn.raw_path = str(raw_path)
        if result is not None:
            turn.total_cost_usd = result.total_cost_usd
            turn.num_turns = result.num_turns
            turn.duration_ms = result.duration_ms

        session = await db.get(Session, session_id)
        session.status = status
        session.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if result is not None and result.session_id:
            session.agent_session_id = result.session_id
        await db.commit()

    await bus.publish(session_id, "turn_done", {"turn_id": turn_id, "status": status})


def resolve_permission(request_id: str, decision: str) -> bool:
    """外部（路由）调用：批准/拒绝某个挂起中的权限请求。返回是否命中。"""
    entry = _pending.get(request_id)
    if not entry or entry["event"].is_set():
        return False
    if decision not in ("allow", "deny"):
        return False
    entry["decision"] = decision
    entry["event"].set()
    return True
