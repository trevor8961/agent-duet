"""claude code 事件流解析器 —— 把 stream-json 逐行翻译成通用协议。

规格见 tests/test_parser.py（先于本文件编写的场景测试），
事件形态的依据是 docs/samples/README.md 的实测发现。

设计约束：
- 纯函数：行列表进、ParseResult 出，不碰数据库（落库属编排层）
- 永不因未知事件类型崩溃：未知行跳过（噪声场景 + 未来新事件类型兼容）
- 错误判定不信 result.is_error，信 permission_denials（samples 04 的实测发现）
"""

import json
from dataclasses import dataclass, field


@dataclass
class ParsedMessage:
    """通用协议层的一条流水（与 models.Message 字段语义一一对应，但无 DB 依赖）。"""

    role: str  # user / assistant
    channel: str  # text / thinking / tool_use / tool_result
    content: str  # JSON 字符串
    tool_use_id: str | None = None  # channel=tool_result 时配对用


@dataclass
class ParseResult:
    messages: list[ParsedMessage] = field(default_factory=list)
    agent_session_id: str | None = None
    turn_status: str = "done"  # done / error
    permission_denials: list = field(default_factory=list)
    # 以下字段只在 result 事件出现一次，不取即丢（原始优先原则的传递侧）
    total_cost_usd: float | None = None
    num_turns: int | None = None
    duration_ms: int | None = None
    cwd: str | None = None
    model: str | None = None


def parse_stream(lines: list[str]) -> ParseResult:
    result = ParseResult()

    for line in lines:
        line = line.strip()
        if not line.startswith("{"):
            continue  # stderr 噪声行（如 unrecognized_model 警告），跳过
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        etype = event.get("type")

        if etype == "system" and event.get("subtype") == "init":
            # init 一次性携带会话元信息，白嫖进 ParseResult
            result.agent_session_id = event.get("session_id")
            result.cwd = event.get("cwd")
            result.model = event.get("model")

        elif etype == "assistant":
            # 一条 assistant 事件的 content 是块数组，逐块翻译（分声部的落点）
            for block in event.get("message", {}).get("content", []):
                btype = block.get("type")
                if btype == "thinking":
                    result.messages.append(
                        ParsedMessage(role="assistant", channel="thinking",
                                      content=json.dumps({"text": block.get("thinking", "")}, ensure_ascii=False))
                    )
                elif btype == "text":
                    result.messages.append(
                        ParsedMessage(role="assistant", channel="text",
                                      content=json.dumps({"text": block.get("text", "")}, ensure_ascii=False))
                    )
                elif btype == "tool_use":
                    result.messages.append(
                        ParsedMessage(role="assistant", channel="tool_use",
                                      content=json.dumps({"tool": block.get("name"),
                                                          "input": block.get("input", {}),
                                                          "tool_use_id": block.get("id")},
                                                         ensure_ascii=False))
                    )
                # 未知块类型跳过（如未来的新块），保住"永不崩溃"不变量

        elif etype == "user":
            # user 事件在事件流里只承载 tool_result（用户输入由编排层自行落库）
            for block in event.get("message", {}).get("content", []):
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    content = block.get("content", "")
                    # content 可能是字符串或块数组，统一序列化存 JSON
                    if not isinstance(content, str):
                        content = json.dumps(content, ensure_ascii=False)
                    result.messages.append(
                        ParsedMessage(role="user", channel="tool_result",
                                      content=json.dumps({"content": content,
                                                          "is_error": bool(block.get("is_error"))},
                                                         ensure_ascii=False),
                                      tool_use_id=block.get("tool_use_id"))
                    )

        elif etype == "result":
            result.total_cost_usd = event.get("total_cost_usd")
            result.num_turns = event.get("num_turns")
            result.duration_ms = event.get("duration_ms")
            result.permission_denials = event.get("permission_denials") or []
            # 关键：is_error=false 不代表没出错（权限拒绝场景），
            # permission_denials 非空必须视为 error turn
            result.turn_status = (
                "error" if event.get("is_error") or result.permission_denials else "done"
            )

        # system/thinking_tokens 等心跳事件：显式丢弃（不落任何结构）

    return result
