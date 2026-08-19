"""种子数据：claude code 默认 profile。

mode_map / capabilities 的依据是 docs/samples/README.md 的实测发现。
"""

import json

from sqlalchemy import select

from .db import SessionLocal
from .models import Agent

CLAUDE_CODE_PROFILE = {
    "name": "claude-code",
    "type": "claude_code",
    "command": "claude",
    "model": None,  # 用 claude 自身的当前配置，页面可改
    "mode_map": {
        "readonly": {"permission-mode": "default"},
        "plan": {"permission-mode": "plan"},
        "guided": {"permission-mode": "default"},
        "autonomous": {"permission-mode": "acceptEdits"},
    },
    "capabilities": {
        "channels": ["text", "thinking", "tool_use", "tool_result"],
        "streaming": True,
        "resume": True,
        "cost_report": True,
        "sdk": True,
    },
}


async def seed_if_empty() -> None:
    async with SessionLocal() as db:
        existing = await db.scalar(select(Agent).where(Agent.name == CLAUDE_CODE_PROFILE["name"]))
        if existing:
            return
        db.add(
            Agent(
                name=CLAUDE_CODE_PROFILE["name"],
                type=CLAUDE_CODE_PROFILE["type"],
                command=CLAUDE_CODE_PROFILE["command"],
                model=CLAUDE_CODE_PROFILE["model"],
                mode_map=json.dumps(CLAUDE_CODE_PROFILE["mode_map"]),
                capabilities=json.dumps(CLAUDE_CODE_PROFILE["capabilities"]),
            )
        )
        await db.commit()
