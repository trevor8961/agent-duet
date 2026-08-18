# 测试策略

> 原则：测试拟自**使用场景**，不是凑覆盖率。每个测试先回答
> 「用户在什么场景下做了什么，期望系统表现什么行为」。
> mock 只用于隔离外部依赖（子进程 / LLM 判定），领域逻辑用真实数据测。

## 测试分层与场景清单

### 1. 持久层（models + db）——纯内存/临时库

| 场景 | 期望 |
|---|---|
| 首次启动 | data/ 创建、四张表存在、claude-code 种子入库 |
| 重复启动（回归） | 种子不重复插入 |
| 落一条完整 turn + messages 流水 | seq 连续、tool_use_id 配对可查 |

### 2. 事件流解析器（claude_code 适配器核心）——**用 docs/samples 实况数据**

这是测试资产的重中之重。三个采样文件各自对应一个真实场景：

| fixture | 场景 | 期望行为 |
|---|---|---|
| `01-plain.jsonl` | 用户问了个纯对话问题 | 产生 user.text + assistant.thinking + assistant.text 三条 message；无 tool 块；session.agent_session_id 回填；turn 状态 done、cost/duration 落 turns |
| `02-tool-use.jsonl` | 用户的问题需要 agent 用工具 | tool_use 与 tool_result 落库且 id 配对；思考心跳（thinking_tokens）**零落库**；num_turns=2 |
| `03-resume.jsonl` | 续接旧 session 提问 | 复用原 session 记录，不新建；seq 接续不重置 |
| 噪声注入 | stderr 噪声行混入流（实测发生过） | 非 `{` 开头的行被跳过，不崩溃 |
| 截断流 | 子进程中途被 kill | turn.status=cancelled，已解析部分保留（原始优先原则兜底） |

### 3. 模式翻译（profile.mode_map）

| 场景 | 期望 |
|---|---|
| session.mode=autonomous 调 claude code | 实际命令带 --permission-mode acceptEdits；turns.effective_mode 记录之 |
| mode_map 未定义的档位 | 报错（显式失败，不静默 fallback） |
| profile 能力声明不含 thinking | 前端数据里 thinking 通道被标记不渲染 |

### 4. 意图判定（mock LLM）

| 场景 | 期望 |
|---|---|
| "帮我看看这个目录结构" | 判定为探索（mock 返回），写入 turns.intent |
| LLM 调用失败 | 降级为「询问」并记日志，不阻塞 turn 创建 |
| 用户页面改意图 | turns.intent 被改写，分析查询反映新值 |

### 5. 读接口 / 视图组装（pydantic-resolve）

| 场景 | 期望 |
|---|---|
| 3 个 session 各若干消息 | 列表页 message_count/last_preview 正确；**SQL 查询次数 = loader 数**（验证无 N+1，用 echo 计数断言） |
| 空库 | 空列表，200 |
| 按 cwd / title 模糊过滤 | 命中预期行（痛点 1 的验收场景） |

### 6. 子进程编排（mock claude 可执行文件）

用一个 shell 脚本假扮 claude：回放 samples/*.jsonl、可控延时、可控退出码。
测：SSE 推进顺序、cancel 中止、result 收尾状态机。

## 工具链

- pytest + pytest-asyncio + httpx（ASGI 传输，不起真实端口）
- DB：每测试用例独立临时库（tmp_path），杜绝测试间污染
- mock 边界：**只 mock 进程边界和 LLM 边界，SQLite 用真库**
  （本地嵌入式组件 mock 掉会让测试失真）

## 节奏

- 解析器（层 2）在写解析器**之前**先写测试——samples 就是规格
- 其余模块随实现同步写；plan 中每个实现项的 DoD 含「场景测试通过」
