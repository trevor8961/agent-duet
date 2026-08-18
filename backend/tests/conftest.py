"""测试夹具：每个测试用例一个全新服务实例（独立临时库）。

关键点：app 的 DB 引擎在 import 时确定路径，因此必须先注入环境变量
再（重新）加载 app 模块；lifespan 必须显式开启，startup 建表逻辑才会执行。
"""

import importlib

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture()
async def client(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_DUET_DATA_DIR", str(tmp_path))

    # app 各模块在 import 时绑定 DB 引擎，必须按依赖顺序全部 reload，
    # 否则 routes/runner 仍握着上一个测试的引擎（跨测试污染的根源）
    import importlib

    import app.db
    import app.main

    order = ["app.db", "app.parser", "app.bus", "app.runner", "app.views", "app.routes", "app.seed", "app.main"]
    for name in order:
        importlib.reload(importlib.import_module(name))

    transport = ASGITransport(app=app.main.app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        await app.main.startup()
        yield c
