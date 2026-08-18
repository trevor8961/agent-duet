"""工作区 git 状态接口测试。

场景：用户点开会话，右侧面板要显示工作区是不是 git 仓库、
分支、未提交文件——判断 agent 干了什么的世界状态。
"""

import subprocess


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


async def test_git_status_of_repo(client, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "checkout", "-q", "-b", "feature-x")
    (repo / "a.txt").write_text("hello")
    _git(repo, "add", "a.txt")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init")
    (repo / "b.txt").write_text("uncommitted")
    # 无远端仓库：upstream 为 None，ahead/behind 为 0（不因缺远端而报错）

    agents = (await client.get("/api/agents")).json()
    resp = await client.post("/api/sessions", json={
        "title": "git", "cwd": str(repo), "agent_id": agents[0]["id"], "mode": "guided",
    })
    sid = resp.json()["id"]

    r = await client.get(f"/api/sessions/{sid}/git")
    assert r.status_code == 200
    data = r.json()
    assert data["is_repo"] is True
    assert data["branch"] == "feature-x"
    assert data["upstream"] is None  # 本地裸仓库无远端
    assert data["ahead"] == 0 and data["behind"] == 0
    assert {"path": "b.txt", "status": "??", "staged": False} in data["changes"]


async def test_git_status_of_non_repo(client, tmp_path):
    agents = (await client.get("/api/agents")).json()
    resp = await client.post("/api/sessions", json={
        "title": "非repo", "cwd": str(tmp_path), "agent_id": agents[0]["id"], "mode": "guided",
    })
    sid = resp.json()["id"]
    r = await client.get(f"/api/sessions/{sid}/git")
    assert r.status_code == 200
    assert r.json() == {"is_repo": False}
