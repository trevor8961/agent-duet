"""事件流解析器场景测试 —— docs/testing.md 第 2 层。

先于解析器实现编写（TDD）：本文件就是解析器的行为规格。
fixture 用 docs/samples/ 的真实事件流，不造假数据。

设计约束：parse_stream 是纯函数（行列表进、ParseResult 出），
不碰数据库——落库属于编排层职责，这里只测翻译正确性。
"""

import json

import pytest
from pathlib import Path

from app import parser as pm  # 晚绑定：conftest 会 reload app.parser，取属性须在运行时

SAMPLES = Path(__file__).resolve().parent.parent.parent / "docs" / "samples"


def parse(name: str):
    return pm.parse_stream((SAMPLES / name).read_text().splitlines())


def test_plain_conversation():
    """场景 01：用户问了个纯对话问题。

    期望：thinking/text 分声部；无 tool 块；session id 回填；turn 元数据落 ParseResult。
    """
    result = parse("01-plain.jsonl")

    assert isinstance(result, pm.ParseResult)
    channels = [m.channel for m in result.messages]
    assert channels == ["thinking", "text"]
    assert result.agent_session_id == "3a0ac14d-b1ce-40e8-8b07-50fc100ed6c6"
    assert result.turn_status == "done"
    assert result.total_cost_usd is not None and result.total_cost_usd > 0
    assert result.num_turns == 1


def test_tool_use_pairing():
    """场景 02：问题需要工具。期望：tool_use/tool_result 配对；心跳零落库。"""
    result = parse("02-tool-use.jsonl")

    channels = [m.channel for m in result.messages]
    assert "thinking_tokens" not in channels  # 心跳一条都不许进来
    assert channels.count("tool_use") == 1
    assert channels.count("tool_result") == 1

    use = next(m for m in result.messages if m.channel == "tool_use")
    res = next(m for m in result.messages if m.channel == "tool_result")
    payload = json.loads(use.content)
    assert payload["tool_use_id"] == res.tool_use_id
    assert payload["tool"] == "Bash"
    assert result.num_turns == 2


def test_resume_reuses_session():
    """场景 03：续接。期望：agent_session_id 与原 session 相同（不新建）。"""
    result = parse("03-resume.jsonl")
    assert result.agent_session_id == "83b4b9e0-4a07-4161-8392-8598d3235d3b"
    assert result.turn_status == "done"


def test_permission_denial_is_error_turn():
    """场景 04：权限拒绝。

    期望：turn 状态为 error——尽管 result.is_error=false（samples README 的关键发现：
    错误信号在 permission_denials，不在 result.is_error）。
    """
    result = parse("04-error.jsonl")
    assert result.turn_status == "error"
    assert result.permission_denials  # 拒绝明细可供 UI 呈现


def test_multi_tool_sequence():
    """场景 05：连续两次工具调用。期望：各配各的对，不串。"""
    result = parse("05-multi-tool.jsonl")

    uses = [m for m in result.messages if m.channel == "tool_use"]
    results_ = [m for m in result.messages if m.channel == "tool_result"]
    assert len(uses) == 2 and len(results_) == 2

    use_ids = {json.loads(u.content)["tool_use_id"] for u in uses}
    result_ids = {r.tool_use_id for r in results_}
    assert use_ids == result_ids  # 双向无孤儿
    assert len(use_ids) == 2  # 且不是同一个 id


def test_noise_lines_skipped():
    """场景：stderr 噪声混入流（实测发生过 unrecognized_model 警告行）。

    期望：非 JSON 行被跳过，不崩溃，正常产出。
    """
    noisy = ["[claude-code:unrecognized_model] blah", *(SAMPLES / "01-plain.jsonl").read_text().splitlines(), "not json at all"]
    result = pm.parse_stream(noisy)
    assert result.turn_status == "done"


@pytest.mark.parametrize("name", ["01-plain", "02-tool-use", "03-resume", "04-error", "05-multi-tool"])
def test_raw_lines_all_json_or_skipped(name):
    """不变量：五个实况样本逐行解析，要么产出有效事件、要么显式跳过，永不抛异常。"""
    result = parse(f"{name}.jsonl")
    assert result.messages  # 每个样本都至少有产出


def test_empty_blocks_skipped():
    """场景：真实数据形态——空思考块 {"text": ""}（turn8 seq72 实测）。

    期望：不产出空消息（否则前端渲染出空纸卡）。
    """
    lines = [
        json.dumps({"type": "assistant", "message": {"content": [
            {"type": "thinking", "thinking": "有内容的思考"},
            {"type": "thinking", "thinking": ""},
            {"type": "text", "text": ""},
            {"type": "text", "text": "正文"},
        ]}}),
    ]
    result = pm.parse_stream(lines)
    texts = [json.loads(m.content)["text"] for m in result.messages]
    assert texts == ["有内容的思考", "正文"]  # 空块全部被过滤
