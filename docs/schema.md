# agent-duet 数据 Schema 设计

> 依据：docs/samples/README.md 的事件流实测 + plan 中的分层决策。
> 三张表：agents(profile) / sessions / messages。

## 分层原则

1. **messages 是通用协议层**：任何 agent 的输出都翻译成统一结构落库，
   不含任何 profile 专属字段 → 检索与前端组件稳定
2. **agents 表是 profile 元数据**：调用方式、模式翻译、能力声明
3. **前端按 capabilities 渲染，不按 agent 身份渲染**

## agents（profile 表）

```sql
CREATE TABLE agents (
    id              INTEGER PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE,          -- 展示名，如 "claude-deepseek"
    type            TEXT NOT NULL,                 -- 适配器类型: claude_code / pi / ...
    command         TEXT NOT NULL,                 -- 可执行命令，如 "claude"
    model           TEXT,                          -- 模型名（透传给 agent）
    mode_map        TEXT NOT NULL DEFAULT '{}',    -- JSON: 通用档位 → 原生参数
    capabilities    TEXT NOT NULL DEFAULT '{}',    -- JSON: 能力声明
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
```

mode_map 示例（claude_code）：

```json
{
  "readonly":   {"permission-mode": "default"},
  "plan":       {"permission-mode": "plan"},
  "guided":     {"permission-mode": "default"},
  "autonomous": {"permission-mode": "acceptEdits"}
}
```

capabilities 示例（claude_code）：

```json
{
  "channels": ["text", "thinking", "tool_use", "tool_result"],
  "streaming": true,
  "resume": true,
  "cost_report": true
}
```

> 通用档位固定四档：readonly / plan / guided / autonomous。
> capabilities.channels 同时约束前端渲染和解析器的合法 channel 集合。

## sessions

```sql
CREATE TABLE sessions (
    id              INTEGER PRIMARY KEY,
    agent_session_id TEXT,                        -- claude 的 session_id（--resume 用）
    title           TEXT NOT NULL,                -- 用户拟的主题，模糊检索字段
    cwd             TEXT NOT NULL,                -- 工作目录（宿主机真实路径）
    agent_id        INTEGER NOT NULL REFERENCES agents(id),
    mode            TEXT NOT NULL DEFAULT 'guided',   -- 通用档位，可中途 PATCH
    status          TEXT NOT NULL DEFAULT 'idle', -- idle / running / done / error / cancelled
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
```

> status 由后端维护：发消息时置 running，收到 result 事件时按
> subtype(success/error) 置 done/error，cancel 接口置 cancelled。

## turns（一轮问答，意图与分析数据的拥有者）

```sql
CREATE TABLE turns (
    id             INTEGER PRIMARY KEY,
    session_id     INTEGER NOT NULL REFERENCES sessions(id),
    seq            INTEGER NOT NULL,          -- 第几轮
    intent         TEXT NOT NULL,             -- 询问/探索/验证/计划/实施（LLM 自动判定，用户可改）
    status         TEXT NOT NULL DEFAULT 'running',  -- running/done/error/cancelled
    effective_mode TEXT,                      -- 本次实际传给 agent 的原生模式（翻译历史审计）
    model          TEXT,                      -- 本轮实际模型（profile 以后会改，历史是事实）
    total_cost_usd REAL,                      -- 以下三项仅在 result 事件出现一次，不存即丢
    num_turns      INTEGER,
    duration_ms    INTEGER,
    raw_path       TEXT,                      -- 原始事件流文件路径 data/raw/<session>/<turn>.jsonl
    created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);
```

> intent 属于 turn 而非 message；创建 turn 时后端用廉价 LLM 调用对 prompt
> 自动分类，用户可在页面一键改（改写本列）。
> 热点分析：`SELECT intent, COUNT(*) FROM turns GROUP BY intent`。
> **原始优先原则**：raw_path 保存逐行原始 stream-json，任何未来新需求
> （如自省引擎）可重放解析补齐字段；派生数据（计数/预览）永不落库，读时算。

## messages（通用协议层，不含 profile 信息）

```sql
CREATE TABLE messages (
    id          INTEGER PRIMARY KEY,
    session_id  INTEGER NOT NULL REFERENCES sessions(id),
    turn_id     INTEGER NOT NULL REFERENCES turns(id),
    seq         INTEGER NOT NULL,             -- 会话内单调递增，排序依据
    role        TEXT NOT NULL,                -- user / assistant
    channel     TEXT NOT NULL,                -- text / thinking / tool_use / tool_result
    content     TEXT NOT NULL,                -- JSON，按 channel 有不同负载
    tool_use_id TEXT,                         -- channel=tool_result 时配对用
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_messages_session ON messages(session_id, seq);
CREATE INDEX idx_messages_turn ON messages(turn_id);
CREATE INDEX idx_sessions_cwd ON sessions(cwd);
```

content 按 channel 的负载约定：

| channel | content JSON |
|---|---|
| text (user) | `{"text": "用户输入原文"}` |
| text (assistant) | `{"text": "回复正文"}` |
| thinking | `{"text": "思考内容"}` |
| tool_use | `{"tool": "Bash", "input": {...}}` |
| tool_result | `{"content": "结果", "is_error": false}` |

## 事件流 → 协议的翻译规则（claude_code 适配器）

| 事件流 | 落库 |
|---|---|
| system/init | session.agent_session_id / cwd 回填（不落 messages） |
| system/thinking_tokens | 丢弃（仅供 SSE 推进度） |
| assistant 块 thinking | messages: role=assistant, channel=thinking |
| assistant 块 text | messages: role=assistant, channel=text |
| assistant 块 tool_use | messages: role=assistant, channel=tool_use, content 含 tool_use_id |
| user 块 tool_result | messages: role=user, channel=tool_result, tool_use_id 配对 |
| result | session.status / 成本信息；成本暂不单独建表，记日志 |
| （用户输入） | **事件流里没有，后端自行落 role=user, channel=text, intent=xx** |

## 读侧组装（pydantic-resolve 视图，非建表）

- SessionListView: message_count(post_*) / last_preview(loader) / updated_at
- SessionDetailView: messages 按 seq 流水；前端按 channel 分声部渲染，
  tool_use/tool_result 靠 tool_use_id 在前端配对（数据平铺存储，树在视图组装）
