# agent-duet 实施计划

## 意图与思路

做 agent 的体验层工具（不造 agent）。四大痛点按依赖顺序解决：
痛点 1（session 档案）是地基 → 痛点 2（分声部呈现）是核心价值 →
痛点 3（模式感知）在呈现层之上 → 痛点 4（多 agent 切换）最后做。

核心概念：「二重唱」= 正式回复（主旋律）与思考独白（低声部）分离。

远期愿景（痛点 5，产品级 North Star）：结构化会话数据不仅给人看（窥探 agent
工作流程），更让 agent 自己消费（自省）——离线冥想任务读自己的历史，
蒸馏踩坑经验、自己生成工作规范（替代用户手写 .claude 约束），注入后续
session。agent 借此获得记忆与成长。v1 不实现，但数据结构按此愿景设计
（通用协议层 / turns 表 / intent / thinking 链都为复盘服务）。

## 关键决策记录

- 名字：agent-duet（源自 bicameral mind / 二分心智概念的接地气表达）
- Non-goals：不造新 agent、不做云端、**不支持导入历史 session**（各家内部格式无底洞，
  边界定为"从用本工具起数据才结构化"）
- 架构：本地 Web 页面 + 后端 + SQLite；后端以 headless 模式调用 agent
  （claude code 的 `claude -p --output-format stream-json`，事件流自带
  thinking/text/tool_use 类型标记，分声部天然成立）
- v1 前提：用户在本工具页面内与 agent 对话（全量数据进库），
  不做"旁观终端 session"模式
- 交付形态：本地直跑；状态全部收敛到 data/ 单目录
- 首个目标 agent：claude code
- 技术栈：后端 Python + FastAPI，前端 Vite + Vue，DB 为 SQLite（WAL）
- 读侧视图组装采用 pydantic-resolve（仅 Core API：resolve_*/post_* + Loader，
  不用 ERD/MCP 模式）；理由：跨行聚合（计数/预览/tool 配对）声明式化，
  锁死风险低（loader 是普通 async 函数）。写路径（事件流解析）不用它
- **通用协议层**：数据层与 profile 解耦。
  messages 用规范 schema（role + channel 枚举 + content JSON），
  所有 agent 的输出都翻译进这套协议 → 检索/重组/前端组件均稳定
- **profile（agents 表）**：每个 agent 一条配置记录，含
  调用方式（command 模板）、mode_map（通用档位↔原生模式翻译表）、
  capabilities（有哪些 channel、是否流式、是否上报 cost）；
  前端按「能力声明」渲染，不按 agent 身份；供应商/模型名是 profile 的一部分
  （同一 agent + 不同模型 = 两条 profile）。v1 种子一条 claude code profile，
  不做 profile 管理界面
- **原始优先原则**：易逝数据（原始事件流文件、cost/耗时/实际模型）现在就存
  即使无人消费，保证未来可重放补齐；派生数据永不落库读时算
- **意图五分类**（询问/探索/验证/计划/实施）：挂在 turns 表；创建 turn 时
  LLM 自动判定，页面可一键改（不用户手选）；它是痛点 3 的抓手（不同意图不同
  信息结构），意图→模式的映射表是每个 profile 自带配置
- **模式双层**：页面上选的是通用档位（readonly/plan/guided/autonomous），
  后端按 profile 的 mode_map 翻译成具体 agent 参数；不把 claude 枚举硬编码进核心

## 步骤

- [x] 建 repo、README problem statement
- [x] 定架构：Web 页面 + 后端 + SQLite + headless 调 claude code
- [ ] 痛点 1+2 合并实现（该架构下同时解决）：
  - [x] 技术栈选型（Python/FastAPI + Vite/Vue）
  - [x] 实测 `claude -p --output-format stream-json` 事件流，采样存 docs/（见 docs/samples/README.md）
  - [ ] SQLite schema 设计（sessions / messages / agents(profile) 三张表，
        详见 docs/samples/README.md 草案 + plan 上述决策）
- [x] FastAPI 骨架跑通（建表+种子+health），测试策略落地 docs/testing.md
- [x] 持久层场景测试（首启建表/种子幂等/流水落库与配对不变量）3 passed
- [x] **解析器**：samples 实况 fixture 拟规格（含 04 权限拒绝/05 多工具补测样本）
      → 实现 app/parser.py 纯函数，全套 14 passed
- [ ] FastAPI 骨架 + 读接口（pydantic-resolve 组装 session 列表/详情）
      DoD 含：无 N+1 查询计数断言 + 过滤场景测试
  - [x] 编排层：runner.py（命令组装/模式翻译/raw 留档/落库）+ routes.py
        （agents/sessions/messages 增改查），假 claude 脚本回放采样测试，17 passed
  - [x] 语义判定（方案B）：app/judge.py 分层判定，机械规则零成本，
        歧义区（有拒绝+result成功）LLM 兜底；turns 增 denied_count/outcome_source；
        真机验证 guided 写文件被拒 → LLM 正确判 error
  - [x] 真机冒烟：真实 claude 全链路（建档→提问→分声部落库→--resume 续接）+ L4 模式对照 + L5 长任务（18轮/17工具/$0.64），
        data/raw/ 留有真实样本，session id 稳定复用
  - [x] SSE：app/bus.py 进程内事件总线 + runner 增量落盘/发布（顺带修复 L5 可观测性
        缺陷：raw 不再缓冲到底）+ GET /api/sessions/{id}/events（Last-Event-ID 游标重连），
        实时性/断线重连场景测试，31 passed
  - [ ] 最小页面：session 列表（时间/目录/话题/意图筛选）+ 对话页（分声部）
  - [ ] 接口增补：PATCH /sessions/{id}（改 mode/主题）、POST /sessions/{id}/cancel（中止子进程）
  - 验收标准：页面发起对话 → 思考与回复分开落库 → 重启后 session 可检索找回
- [ ] 痛点 3：模式感知呈现（形态待设计）
- [ ] 痛点 4：多 agent 选择入口
- [ ] 痛点 5（远期）：自省冥想引擎——agent 消费持久层蒸馏经验生成工作规范

## 待定问题

- 痛点 1 的「话题」怎么来：用户手填？LLM 自动总结？

## 开发纪律（agent 自主迭代规则）

提交条件（全部满足）：测试全绿 + 完整工作单元 + 冒烟过 + 文档同步。
绝不提交：红的测试 / 密钥凭证 / data/ 运行时状态 / 半成品。
绝不 push：force / 非 origin main / 有分歧未先 pull。
验收门禁（2026-xx 起）：UI 改动须用户验收合格后才 commit+push，
未验收的改动停留在工作区。
