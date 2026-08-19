# 研究原料 · subagent 并发样本

## 样本

`subagent-parallel-turn66.jsonl` —— 一次真实会话的原始事件流（SDK dataclass asdict 序列化）。

- 会话：autonomous 模式，让 claude 用 Agent 工具**并行**统计两个目录的文件数
- 触发：`请用 Task 工具并行完成两件事：1) 统计 docs/samples 下 jsonl 数 2) 统计 backend/app 下 py 数`
- 结果：claude 用 `Agent` 工具派生了 **2 个 subagent 并发执行**

## 关键发现（当前设计的缺陷）

1. **归属丢失**：subagent 产出的消息在 raw 里带 `parent_tool_use_id`（指向派生的 Agent 调用），
   但当前 `sdk_runner._translate` 忽略该字段——落库后 subagent 消息与主 agent 消息拍平，无法区分
2. **主从混淆**：subagent 的思考/工具/最终答复被当作主 agent 的消息，
   前端会把 subagent 的答复（text 块）误渲染成主 agent 的旁白/答复
3. **并发结构丢失**：两个 subagent 的产物交错排列，无法还原"两个并行子任务"的结构

## 样本中的证据（seq 摘录）

```
seq 4   tool_use Agent (subagent 1)  ── 派生
seq 6   tool_use Agent (subagent 2)  ── 派生
seq 8-21 subagent 1/2 的 thinking/tool_use/tool_result/text 交错拍平
```

## 关联 backlog

见 docs/devlog 中的 backlog 条目：「subagent 并发数据建模」。
