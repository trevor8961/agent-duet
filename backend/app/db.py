"""数据库连接与建库。

启动时自动建表（SQLite 场景下不引入 alembic，schema 变更初期直接
改 models + 手动迁移，表结构稳定后再考虑迁移工具）。

数据目录可用环境变量 AGENT_DUET_DATA_DIR 覆盖——主要供测试注入
临时目录，生产路径不变。
"""

import os
from pathlib import Path

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

DATA_DIR = Path(os.environ.get("AGENT_DUET_DATA_DIR") or (Path(__file__).resolve().parent.parent.parent / "data"))
DB_PATH = DATA_DIR / "agent-duet.db"

engine = create_async_engine(f"sqlite+aiosqlite:///{DB_PATH}")
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
