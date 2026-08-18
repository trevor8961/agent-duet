"""崩溃恢复场景测试。

场景：服务在 turn 运行中崩溃/被杀。期望：重启后该 turn 被标 error
（outcome_source=orphaned），session 状态同步——用户面对的是可重试的
明确失败，不是永远 running。
"""

import sqlite3


async def test_startup_recovers_orphaned_running_turn(client, tmp_path):
    """场景：库里遗留 status=running 的 turn（进程已死），服务重启。"""
    # 先让 startup 正常跑一遍（建表+种子）
    await client.get("/api/health")

    # 模拟崩溃现场：手动造一个 running turn
    import sqlite3

    db = sqlite3.connect(tmp_path / "agent-duet.db")
    db.execute(
        "INSERT INTO sessions (title, cwd, agent_id, mode, status) "
        "SELECT '崩溃现场', '/tmp/x', id, 'guided', 'running' FROM agents LIMIT 1"
    )
    db.execute(
        "INSERT INTO turns (session_id, seq, intent, status) "
        "SELECT id, 1, '询问', 'running' FROM sessions LIMIT 1"
    )
    db.commit()
    db.close()

    # 再次触发 startup（等价于重启）
    from app.main import startup

    await startup()

    db = sqlite3.connect(tmp_path / "agent-duet.db")
    row = db.execute("SELECT status, outcome_source FROM turns WHERE status!='done'").fetchone()
    assert row == ("error", "orphaned")
    assert db.execute("SELECT status FROM sessions").fetchone()[0] == "error"
