<div align="center">

[中文](README.md) | [English](README.en.md)

</div>

# agent-duet

> 你和 agent 的二重唱 —— 把瀑布流变成分声部的乐谱。

agent-duet 是一个**本地自托管的 agent 会话工作台**：把 agent 的思考过程、
工具调用、正式回复结构化地分开呈现，并给每一次会话留档、每一个授权留痕。

![会话视图](docs/images/session.png)

## 它解决什么问题

| 痛点 | agent-duet 的做法 |
|---|---|
| 长会话忘了在哪开的、难找回 | 每场会话一份档案：目录 + 话题 + 状态，随时检索 |
| 终端瀑布流信息密度低 | 分声部呈现：主旋律（回复）/ 低声部（思考）/ 动作（工具）分开 |
| 不同模式无差别呈现 | 模式感知：引导模式下每个写操作弹授权卡，批准/拒绝/超时永久记录 |
| 多 agent 割裂 | profile 体系：接新 agent = 加一条配置 + 一个适配器 |

## 快速开始

```bash
# 后端
cd backend && uv sync && uv run uvicorn app.main:app --port 8300

# 前端
cd frontend && npm install && npm run dev
```

打开 **http://localhost:5173**。详见 [快速上手](docs/getting-started.md)。

## 界面

![首页](docs/images/home.png)

三栏布局：

- **左栏**：会话列表（按标题搜索、按目录分组、当前会话高亮）
- **中栏**：对话本体——你的提问、幕后工作（折叠）、最终答复（纸卡）
- **右栏**：会话上下文——模式切换、基本信息、Git 状态、节目单（Requests）

## 核心概念

- **二重唱 / 三声部**：agent 的输出天然分三层——对你说的（主旋律）、
  自己想的（低声部）、动手做的（动作）。agent-duet 让它们各归其位。
- **原始优先**：每轮对话的原始事件流落盘（`data/raw/`），派生数据读时算，
  未来任何新需求都能重放补齐。
- **授权即数据**：每一次批准/拒绝/超时都是结构化记录，挂在对应的工具调用上。
- **事务状态 vs 交互结论**：完成/未完成/失败/已终止 是事务状态；
  批准/拒绝/超时是每次授权的交互结论，两者正交。

## 愿景

结构化会话数据的终极消费者不止是用户，还有 agent 自己：通过离线「冥想」
复盘自己的思考链与踩坑记录，agent 自己蒸馏并维护工作规范——从被约束，
走向自我约束。

## 文档

- [快速上手](docs/getting-started.md) — 从零到第一次对话
- [FAQ](docs/faq.md) — 常见问题与已知限制
- [开发日志](docs/devlog/) — 每日工作记录与决策

## 技术栈

Python + FastAPI · SQLite · claude-agent-sdk · Vue 3 + Vite

## License

（补充你的许可证）
