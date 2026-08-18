# 事件流实测发现（claude code 2.1.234 + deepseek-v4-pro）

> 三个采样文件为原始 jsonl，本文档是对它们的解读，作为 schema 与解析器设计依据。
> 采集日期：2026-xx-xx，模型：deepseek-v4-pro（第三方接口）

## 采样文件

- `01-plain.jsonl` 纯对话（无工具）
- `02-tool-use.jsonl` 带一次工具调用
- `03-resume.jsonl` 用 session id 续接的多轮对话
- `04-error.jsonl` 工具被权限拒绝的调用
- `05-multi-tool.jsonl` 单次提问连续两次工具调用

### 04 的关键发现（影响状态机设计）

权限被拒的会话，`result` 事件仍是 `is_error=false, subtype=success`！
错误信号只在两处：tool_result.content 的拒绝文案、
`result.permission_denials` 数组。
→ **turn 的 error 判定必须结合 permission_denials，不能只看 result.is_error**。

### 05 的关键发现

多工具时事件严格交替：tool_use → tool_result → tool_use → tool_result →
最终 text。配对只认 tool_use_id、不依赖顺序假设的设计被验证。
num_turns 计的是 agent loop 轮次（2 工具 + 1 回答 = 3）。

## 核心发现

### 1. 命令与版本

- `claude -p "<prompt>" --output-format stream-json --verbose`
- **必须带 `--verbose`**，否则 print 模式下报错（"stream-json requires --verbose"）
- 事件流是 claude code 自己生成的，与模型供应商无关的外壳结构稳定

### 2. 事件类型总览（回答 Q1）

每行一个 JSON 对象，`type` 字段区分：

| type | 说明 |
|---|---|
| `system` (subtype=init) | 会话初始化，一次性吐出大量元信息（见下） |
| `system` (subtype=thinking_tokens) | 思考进度心跳（token 计数增量），**高频噪声，解析时可忽略** |
| `assistant` | 模型输出，content 为块数组 |
| `user` | 工具执行结果（tool_result 块），不是用户输入 |
| `result` | 整个 `-p` 调用的收尾汇总 |

### 3. 分声部落地（回答 Q2、Q6 ✅）

assistant 事件的 `message.content` 是块数组，每块有 `type`：

- `thinking` — 思考独白（低声部）✅ **第三方 DeepSeek 接口正确传递了 thinking**
- `text` — 正式回复（主旋律）
- `tool_use` — 工具调用，含 `name` / `input` / `id`

一次回复中多个块按序共存（02 样本：thinking → tool_use → [执行] → thinking → text），
**channel 字段直接用这三个值**。

### 4. 工具调用闭环（回答 Q3）

- `assistant` 事件里 `tool_use.id = call_xxx`
- 执行结果在随后的 `user` 事件里，`tool_result.tool_use_id` 与之配对
- 多轮 agent loop 通过 `result.num_turns` 体现（02 样本 = 2）
- tool_result 作为 user 角色落库，channel=`tool_result`，靠 tool_use_id 关联

### 5. init 事件白嫖字段（回答 Q4 一半）

`system/init` 包含：`session_id`、`cwd`、`model`、`permissionMode`、
`tools`、`mcp_servers`、`claude_code_version`、`output_style`、`agents`、`skills`
→ sessions 表的 cwd / agent 模型 / 权限模式可直接从这里取。

### 6. result 事件白嫖字段

`session_id`、`total_cost_usd`、`usage`（input/output tokens）、
`duration_ms`、`ttft_ms`、`num_turns`、`is_error`
→ 可落 sessions 或单独的 turns/cost 记录。

### 7. 多轮续接（回答 Q5 ✅）

- `claude -p --resume <session_id> "<prompt>"` 有效
- resume 后 init 的 session_id 与原来**相同**（03 样本验证）
- 上下文完整保留（正确回忆了上一轮问题）
- **注意：用户输入本身不出现在事件流里**，需由我们的后端自行记录

### 8. 工程坑

- stderr 会输出噪声（如 `[claude-code:unrecognized_model] ...`），
  **必须与 stdout 分开采集**；解析器只接受以 `{` 开头的行
- thinking_tokens 心跳事件极多（01 样本 39 行里占了 35 行），
  落库时直接丢弃，最多留个"思考中"的 UI 状态

## 对 schema 的直接推论

```
sessions: id(我们的), claude_session_id, title, cwd, model, permission_mode,
          agent_type, status, created_at, updated_at
messages: id, session_id, seq, role(user/assistant),
          channel(text/thinking/tool_use/tool_result),
          content(JSON), tool_use_id(可空,配对用), created_at
```

- 用户输入由后端自己落库（role=user, channel=text），事件流里没有
- content 用 JSON 存，兼容各 channel 不同的负载结构

## 真机冒烟 L4/L5 发现（2026-xx，data/raw/17-19 留档）

- **L4a/L4b 模式对照**：同一写文件任务，guided(default)→Write 被拒→turn=error；
  autonomous(acceptEdits)→成功落盘→turn=done。模式翻译链路真实验证。
- **空 thinking 块**：L4b 中出现 `{"text": ""}` 的空思考块（真实数据特有），
  parser 需决定过滤策略。
- **L5 揭示 error 语义缺陷**：18 轮 loop 任务中一次 Bash 被权限拒绝，
  agent 换方法后**成功完成了任务并给出完整统计表**，但按现行规则
  （permission_denials 非空 → error）turn 被标为 error。
  → "拒绝过" ≠ "失败"，语义需重新设计（待决策）。
- **可观测性缺陷**：raw 文件在进程结束后才一次性落盘，running 期间
  完全不可观测 → 佐证 SSE/增量落库的必要性。
- **测试污染事故**：早前晚绑定 bug 曾让测试数据写入真实库（已清理），
  教训：引擎绑定对象必须运行时取。
