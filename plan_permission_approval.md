# 计划：事中授权（interactive permission approval）

## 意图与思路（防断读）

当前痛点：agent 在 guided/readonly 下遇到权限请求时，headless 模式**自动拒绝**，
用户只能事后看到 denied 状态再点「授权并继续」——多一轮交互、且用户无法在
危险操作发生前把关。

目标：agent 运行中遇到权限请求 → 页面弹出授权卡片（工具名 + 输入 + 倒计时）→
用户点批准/拒绝 → agent 继续或放弃。技术路径 A：调用层从 `claude -p` 子进程
换成 **claude-agent-sdk**（其 `can_use_tool` 异步回调天然支持阻塞等待）。

关键事实（已实测 SDK 0.2.140）：
- `can_use_tool: async (tool_name, tool_input, context) -> PermissionResultAllow|Deny`
- `permission_mode` 取值含 'default'/'plan'/'acceptEdits'/'bypassPermissions'/'dontAsk'/'auto'
- `session_id`/`resume` 字段直接续接（替代 CLI 的 --resume）
- PermissionResultDeny 带 `interrupt: bool`（拒绝时是否打断 agent 继续尝试）

## 用户已拍板的决策

- 超时策略：**3 分钟**无响应默认拒绝，UI 上显示倒计时
- 前端待决交互：状态机独立隔离
- 其余（3/4/5 号问题）遇到再讨论

## 设计：权限请求的状态机

```
permission 状态: idle → pending → (approved | denied | timeout)
```

- runner 内 `can_use_tool` 回调被调用时：发布 `permission_request` 事件（含 request_id、
  tool_name、tool_input、timeout_at=now+180s）到总线，然后 `await` 一个 asyncio.Event
- 用户响应走新接口 `POST /api/sessions/{sid}/permission/{request_id}`，body={decision}
  → resolve 那个 Event → 回调返回 Allow/Deny
- 超时：`asyncio.wait_for(event, timeout=180)` 超时即 Deny（message="timeout"）
- request_id 与 session 关联；页面重开能恢复 pending 状态（见下）

## 模式融合（四档语义重定义）

| 通用档位 | 翻译（SDK permission_mode） | 权限请求行为 |
|---|---|---|
| readonly | 'default' + 全拒绝回调 | 立即 deny（现状等价） |
| guided | 'default' | **弹窗等待用户**（新主场） |
| plan | 'plan' | SDK 内 plan 语义 |
| autonomous | 'acceptEdits' | 不弹（现状） |

> 注意：can_use_tool 回调只在权限系统判定"需要询问"时触发；
> readonly/autonomous 仍需回调兜底（统一返回 deny/allow），保持单一代码路径。

## 步骤（可独立验证）

- [ ] 1. 加 `claude-agent-sdk` 依赖，写 `app/sdk_runner.py`：
      用 SDK query 取代子进程；`output_format="stream-json"` 事件流复用现有 parser
      （验证点：跑一个真实 turn，落库结果与旧 runner 一致）
- [ ] 2. `can_use_tool` 回调 + 权限状态机 + 总线事件 `permission_request`
      （验证点：单测——假回调触发，pending → 外部 resolve → allow/deny 生效）
- [ ] 3. 接口 `POST /api/sessions/{sid}/permission/{rid}` + 3 分钟超时
      （验证点：单测——resolve 成功、超时返回 deny、无效 rid 报错）
- [ ] 4. 前端授权卡片（倒计时、批准/拒绝按钮）+ SSE 订阅 permission_request 事件
      （验证点：Playwright 真机/假 agent——卡片出现、点批准后 agent 继续）
- [ ] 5. 页面重开恢复 pending 权限（persist pending 到 DB，onMounted 拉取重建）
      （验证点：pending 中刷新页面，卡片仍出现）
- [ ] 6. 迁移旧的子进程 runner 到 SDK runner，跑通全量测试 + 真机冒烟
      （验收：41+ 测试全绿，真实会话里 guided 模式触发一次授权弹窗全流程）

## 风险与对策（读者视角自审）

1. **SDK 与 DeepSeek 代理兼容性未知**——最大风险。对策：步骤 1 先用真实 turn
   验证事件流/续接，任何异常立刻回退（SDK 失败不影响已提交的 CLI 版本）。
2. **回调阻塞期间事件循环/连接**——can_use_tool await 时，SSE 推送必须走独立
   任务（不阻塞总线发布）。对策：permission 事件发布用 `asyncio.create_task`。
3. **并发权限请求**——同一 turn 理论上可能出现多个并行 tool_use 同时要权限。
   v1 假设串行（一次一个 pending），多个则排队；若真实出现并行再升级。
4. **超时与用户刚好点击的竞态**——响应接口和超时同时到。对策：用 asyncio.Event
   + 单次消费（先到先得），后到的返回"已处理"。
5. **页面关闭再打开**——pending 必须持久化到 DB（不重蹈"内存态孤儿"覆辙），
   重启服务也要能恢复（对账时 pending → 超时拒绝）。

## 明确不做（v1）

- 不做"权限策略记忆"（"本会话永远允许 Bash"）——那是 PermissionUpdate 的高级用法
- 不做并行权限请求的多卡片 UI——串行假设
- 不改 CLI 路径（保留可回退）

## 待定（遇到再议）

- readonly 档位是否也需要弹窗（只读提示而非授权）？
- 拒绝时是否允许 agent 继续尝试（PermissionResultDeny.interrupt 的语义）
