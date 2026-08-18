"""turn 结果语义判定测试 —— L5 冒烟发现的设计修正。

规则（分层判定）：
1. is_error=true          → error   （机械）
2. 无 permission_denials  → done    （机械）
3. 有拒绝 + result 成功   → LLM 判定（唯一花钱的分支）
4. LLM 调用失败           → 保守降级 error
"""

import pytest

from app.judge import JudgeInput, decide_outcome


async def test_is_error_is_mechanical_error():
    """场景：result 明确报错。期望：error，不调 LLM。"""
    verdict = await decide_outcome(
        JudgeInput(is_error=True, denied_count=0, user_prompt="p", final_text="x"),
        llm=lambda _: pytest.fail("不应调 LLM"),
    )
    assert verdict == ("error", "mechanical")


async def test_no_denials_is_mechanical_done():
    """场景：干净完成（L1-L4b 形态）。期望：done，不调 LLM。"""
    verdict = await decide_outcome(
        JudgeInput(is_error=False, denied_count=0, user_prompt="p", final_text="x"),
        llm=lambda _: pytest.fail("不应调 LLM"),
    )
    assert verdict == ("done", "mechanical")


async def test_denials_but_success_goes_to_llm():
    """场景：L5 形态——被拒一次但换方法完成了。期望：交给 LLM，LLM 说了算。"""
    calls = []

    def fake_llm(inp):
        calls.append(inp)
        return "done"

    verdict = await decide_outcome(
        JudgeInput(is_error=False, denied_count=1, user_prompt="统计事件分布", final_text="统计完成..."),
        llm=fake_llm,
    )
    assert verdict == ("done", "llm")
    assert len(calls) == 1
    assert "统计事件分布" in calls[0].judge_prompt  # 判定必须看到原始任务


async def test_denied_when_llm_error_with_denials():
    """场景：04/用户实测形态——被拒导致没完成。期望：denied（需授权），不是 error。"""
    verdict = await decide_outcome(
        JudgeInput(is_error=False, denied_count=1, user_prompt="删文档", final_text="我无法删除..."),
        llm=lambda _: "error",
    )
    assert verdict == ("denied", "llm")



async def test_llm_failure_falls_back_conservative():
    """场景：LLM 边界故障。期望：保守 error，不抛异常（判定层永不阻塞落库）。"""
    def broken_llm(_):
        raise RuntimeError("llm down")

    verdict = await decide_outcome(
        JudgeInput(is_error=False, denied_count=1, user_prompt="p", final_text="x"),
        llm=broken_llm,
    )
    assert verdict == ("error", "mechanical-fallback")


async def test_no_final_text_with_denials_is_error_without_llm():
    """场景：被拒且连最终回复都没有。期望：机械 error（没有任何完成迹象）。"""
    verdict = await decide_outcome(
        JudgeInput(is_error=False, denied_count=1, user_prompt="p", final_text=""),
        llm=lambda _: pytest.fail("不应调 LLM"),
    )
    assert verdict == ("error", "mechanical")
