"""数据库表定义 —— 唯一权威来源是 docs/schema.md，本文件是它的 SQLAlchemy 实现。

分层纪律：
- Message 是通用协议层，不含任何 profile 信息；各 agent 的输出由适配器翻译进来
- 原始事件流存文件（turn.raw_path），DB 只存路径；派生数据（计数/预览）永不落库
"""

import json

from sqlalchemy import (
    ForeignKey,
    Index,
    Integer,
    REAL,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class JsonText:
    """mode_map / capabilities 等 JSON 列的读写辅助：TEXT 存取，属性级 dict 访问。

    为什么不用 SQLAlchemy 的 JSON 类型：SQLite 下 TEXT + 手动 dumps 的数据
    在 .db 文件里可直接读，符合"不黑箱"原则，行为也更可预期。
    """

    @staticmethod
    def load(raw: str | None, default):
        if not raw:
            return default
        return json.loads(raw)


class Agent(Base):
    """profile 表：一个「agent × 供应商模型」组合一条记录。"""

    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)  # 展示名，如 claude-deepseek
    type: Mapped[str]  # 适配器类型: claude_code / pi / ...
    command: Mapped[str]  # 可执行命令，如 claude
    model: Mapped[str | None]  # 模型名，透传给 agent
    mode_map: Mapped[str] = mapped_column(default="{}")  # JSON: 通用档位 -> 原生参数
    capabilities: Mapped[str] = mapped_column(default="{}")  # JSON: 能力声明
    created_at: Mapped[str] = mapped_column(default="datetime('now')")


class Session(Base):
    __tablename__ = "sessions"
    __table_args__ = (Index("idx_sessions_cwd", "cwd"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_session_id: Mapped[str | None]  # claude 的 session_id，--resume 用
    title: Mapped[str]  # 用户拟的主题，模糊检索字段
    cwd: Mapped[str]  # 宿主机真实路径
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"))
    # 通用档位: readonly / plan / guided / autonomous，具体 agent 参数由 profile 翻译
    mode: Mapped[str] = mapped_column(default="guided")
    status: Mapped[str] = mapped_column(default="idle")  # idle/running/done/error/cancelled
    created_at: Mapped[str] = mapped_column(default="datetime('now')")
    updated_at: Mapped[str] = mapped_column(default="datetime('now')")


class Turn(Base):
    """一轮问答。意图、运行状态、成本等易逝数据都在这层。"""

    __tablename__ = "turns"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"))
    seq: Mapped[int]  # 第几轮
    intent: Mapped[str]  # 询问/探索/验证/计划/实施（LLM 判定，用户可改）
    status: Mapped[str] = mapped_column(default="running")  # running/done/error/cancelled
    effective_mode: Mapped[str | None]  # 实际传给 agent 的原生模式（审计用）
    model: Mapped[str | None]  # 本轮实际模型（profile 以后会改，历史是事实）
    # 以下三项只在 result 事件出现一次，不存即丢（原始优先原则）
    total_cost_usd: Mapped[float | None] = mapped_column(REAL)
    num_turns: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    raw_path: Mapped[str | None]  # 原始 stream-json 文件路径
    created_at: Mapped[str] = mapped_column(default="datetime('now')")


class Message(Base):
    """通用协议层流水。channel 取值: text / thinking / tool_use / tool_result。"""

    __tablename__ = "messages"
    __table_args__ = (
        Index("idx_messages_session", "session_id", "seq"),
        Index("idx_messages_turn", "turn_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"))
    turn_id: Mapped[int] = mapped_column(ForeignKey("turns.id"))
    seq: Mapped[int]  # 会话内单调递增
    role: Mapped[str]  # user / assistant
    channel: Mapped[str]  # text / thinking / tool_use / tool_result
    content: Mapped[str]  # JSON 字符串，按 channel 有不同负载
    tool_use_id: Mapped[str | None]  # channel=tool_result 时与 tool_use 配对
    created_at: Mapped[str] = mapped_column(default="datetime('now')")
