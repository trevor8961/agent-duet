"""turn 结果语义判定 —— L5 冒烟发现的设计修正。

「拒绝过」≠「失败」：agent 可能被拒后换方法完成了任务（L5 实况），
也可能被拒后彻底干不了（04 实况）。机械信号无法区分，歧义区交给 LLM。

分层省钱：机械规则能定的零成本，只有「有拒绝 + result 成功」才调 LLM。
"""

import asyncio
import inspect
import json
import shlex
from dataclasses import dataclass

DONE, ERROR = "done", "error"


@dataclass
class JudgeInput:
    is_error: bool
    denied_count: int
    user_prompt: str
    final_text: str

    @property
    def judge_prompt(self) -> str:
        return (
            "你是任务结果审计员。判断 agent 是否完成了用户交给它的原始任务。\n"
            f"用户原始任务：{self.user_prompt}\n"
            f"agent 的最终回复：{self.final_text[:500]}\n"
            "过程中有权限拒绝，agent 可能换了方法。只依据最终回复判断任务是否完成。\n"
            '只回答一个词：done（完成了）或 error（没完成）。'
        )


async def decide_outcome(inp: JudgeInput, llm) -> tuple[str, str]:
    """返回 (status, outcome_source)。llm: async (JudgeInput) -> 'done'|'error'。

    注入式设计：测试传假 llm（不花钱），线上用 make_claude_judge 构造真实调用。
    """
    if inp.is_error:
        return ERROR, "mechanical"
    if not inp.final_text.strip():
        return ERROR, "mechanical"  # 被拒且无任何完成迹象
    if inp.denied_count == 0:
        return DONE, "mechanical"

    # 歧义区：花钱兜底；LLM 故障时保守降级 error
    try:
        verdict = llm(inp)
        if inspect.isawaitable(verdict):
            verdict = await verdict
        return (verdict if verdict in (DONE, ERROR) else ERROR), "llm"
    except Exception:
        return ERROR, "mechanical-fallback"


def make_claude_judge(command: str):
    """用 agent 自己做判定（廉价调用：一句话进出，无工具）。"""

    async def llm(inp: JudgeInput) -> str:
        proc = await asyncio.create_subprocess_exec(
            *shlex.split(command),
            "-p", inp.judge_prompt,
            "--max-turns", "1",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        out, _ = await proc.communicate()
        text = out.decode(errors="replace").strip().lower()
        # 输出可能是裸词或含 JSON，取包含判定词的兜底解析
        if "done" in text and "error" not in text:
            return DONE
        return ERROR

    return llm
