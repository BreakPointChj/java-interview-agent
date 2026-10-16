# Java 全栈面试 Agent 设计说明

## 1. 设计目标

系统将“出题—作答—评价—记忆更新—下一题—报告”实现为可重复、可恢复的业务闭环。题库提供事实锚点，大模型负责语义理解，结构化模型负责约束输出，持久化层负责上下文延续。各部分通过接口和领域模型解耦，方便把 OpenAI、SQLite 或题库替换为企业内部实现。

所有源码、提示词、文档均使用 UTF-8，代码中的核心类、方法和非显然逻辑均有中文注释或文档字符串。

## 2. 目录结构

```text
langchain-test/
├─ interview_agent/
│  ├─ api.py             # FastAPI 路由、参数校验与错误映射
│  ├─ bootstrap.py       # 配置、仓储、题库、评估器的依赖装配
│  ├─ cli.py             # 中文交互式命令行
│  ├─ config.py          # .env 配置读取和运行前校验
│  ├─ evaluator.py       # LangChain 在线评分器与离线评分器
│  ├─ graph.py           # LangGraph 状态、节点和条件路由
│  ├─ knowledge.py       # TF-IDF 稀疏向量索引与余弦检索
│  ├─ memory.py          # SQLite 会话、问答和候选人画像
│  ├─ models.py          # Pydantic 领域模型与枚举
│  ├─ question_bank.py   # 八领域三级题库及自适应选题
│  ├─ service.py         # 核心业务编排和报告聚合
│  ├─ study.py           # 多轮技术复习问答与离线知识检索
│  ├─ data/
│  │  ├─ knowledge_base.json            # 通用基础问答
│  │  ├─ knowledge_base_practical.json  # 项目实战问答与验证步骤
│  │  └─ knowledge_base_supplement.json # 微服务、前端与补充实战问答
│  └─ web/               # 原生 HTML/CSS/JS 响应式单页界面
├─ tests/                # 题库、记忆、工作流端到端测试
├─ docs/DESIGN.md        # 本设计文档
├─ .env.example          # 可提交的配置模板
├─ environment.yml       # Conda Python 3.11 隔离环境
├─ requirements.txt      # 最小运行依赖
├─ requirements-dev.txt  # 测试和代码检查依赖
├─ pyproject.toml        # 打包、pytest、ruff 配置
└─ main.py               # CLI/API 统一入口
```

## 3. 核心数据流

```text
Web / CLI / HTTP 请求
      │
      ▼
LangGraph 条件路由 ── start ──► 创建画像与会话 ──► 选择第一题
      │
      └──────────── answer ────► 读取当前题和近期上下文
                                      │
                                      ▼
                            LangChain 结构化评分
                                      │
                       ┌──────────────┴──────────────┐
                       ▼                             ▼
              保存问答与更新画像             判断是否达到题数
                       │                       │             │
                       └── 自适应选择下一题 ◄──否           是──► 聚合报告
```

`InterviewState` 是图节点间的瞬时状态。业务真相写入 SQLite，因此服务重启后仍可通过 `session_id` 找回会话。LangGraph 的 `InMemorySaver` 保存当前进程内的执行快照；生产部署可替换为官方数据库 Checkpointer。

## 4. 记忆与上下文设计

### 4.1 短期记忆

`turns` 表按顺序保存每轮题目、原始回答和结构化评价。评分前只加载 `CONTEXT_WINDOW_TURNS` 条最近记录，默认 8 条，防止对话持续增长造成 token 和延迟失控。传入提示词的历史是摘要形式：题目、得分和改进点，不重复传入长篇原始回答。

### 4.2 长期记忆

`profiles` 表按 `candidate_id` 保存姓名、目标级别、累计答题数、历史均分和薄弱领域计数。低于 70 分会增强该领域权重，后续会话选题时更可能再次练习；达到 70 分会逐步降低薄弱计数。这是一种透明、可解释且无需向量库的长期记忆。

### 4.3 会话记忆

`sessions` 表保存题目范围、目标难度、已出题 ID、当前题、进度、分数和状态。每次变化都会整体写入 JSON 快照，避免多个字段部分更新产生不一致。SQLite 启用 WAL 与外键，仓储使用短连接和锁来适应 FastAPI 的线程池执行方式。

### 4.4 复习对话记忆

`study_messages` 表按 `conversation_id` 追加用户问题与助手回答。在线复习助手会读取有限窗口的最近消息和候选人长期画像，实现“继续解释”“举个例子”等上下文追问。助手回答同时保存领域、核心知识点和推荐追问，页面刷新后仍能恢复完整结构。

复习检索不是简单字符计数：系统对问题、别名、关键词和核心要点建立 TF-IDF 稀疏向量，使用余弦相似度召回，并以别名精确命中、关键词和领域提示作有限加权。当前问题权重高于领域提示，因此用户误选领域时，明确的问题语义仍可命中正确答案。低于置信度阈值时系统明确表示未匹配，不再拼接多个无关题目的要点。

项目实战知识使用结构化字段保存：`project_context` 说明业务场景，`practical_steps` 给出
实施顺序，`example` 保存代码/SQL/配置，`verification` 描述如何证明结果正确，`pitfalls`
记录边界和错误做法。`render_answer()` 在返回页面或注入在线 RAG 前统一组合这些内容，保证
问题与答案严格对应，也让回答能够落到具体工作动作。

## 5. 评分与提示词设计

在线评分由 `ChatPromptTemplate | ChatOpenAI.with_structured_output(Evaluation)` 组成。Pydantic 将分数限制在 0 到 100，并固定优势、弱点、遗漏点、反馈和建议答案字段。提示词包含：

1. 固定评分等级和面试官角色；
2. 当前题目、难度与参考要点；
3. 候选人目标级别、历史均分与薄弱领域；
4. 有上限的最近问答摘要；
5. 明确标记为不可信数据的候选人回答。

这使评价既关注当前技术准确性，也保持跨轮一致性。模型请求设置 60 秒超时与两次重试。离线评估器实现相同协议，以关键词覆盖、回答长度生成确定性结果，用于无网络测试。

## 6. 选题与自适应难度

题目结构包含领域、难度、题干、参考点和深入追问。题目 ID 会写入 `asked_question_ids`，确保一个会话中不重复。

- 默认按用户目标难度出题；该难度题目不足时从同领域其他级别回退。
- 最近两题均分达到 85，下一题上调一级；低于 50，下一题下调一级。
- 候选人的长期薄弱领域计数会成为随机选择权重。
- 题库数量不足时在创建会话前失败，不生成做不完的会话。

参考点绝不会通过 API 题目响应发送给候选人，只在服务端评分使用。

## 7. 涉及的主要技术点

- **LangChain LCEL**：提示模板、聊天模型、结构化输出解析组成 Runnable 管道。
- **LangGraph**：TypedDict 状态、节点、条件边、开始/结束节点、Checkpointer。
- **Pydantic v2**：请求校验、领域约束、JSON 序列化与 LLM 输出校验。
- **FastAPI**：同步领域服务、OpenAPI/Swagger、HTTP 错误语义。
- **原生 Web 前端**：响应式布局、Fetch API、会话恢复和模型内容安全转义，无 Node 构建依赖。
- **本地向量检索**：中文 2/3-gram、英文技术词、TF-IDF、L2 归一化和余弦相似度，无外部向量服务依赖。
- **SQLite**：WAL、外键、索引、UPSERT、JSON 快照与增量问答记录。
- **依赖倒置**：`AnswerEvaluator` Protocol 允许替换模型；领域服务不依赖 CLI 或 HTTP。
- **环境隔离**：Conda 固定 Python 3.11，pip 文件仅列直接依赖，开发依赖单独维护。
- **安全性**：密钥只从 `.env` 读取且被 Git 忽略；候选人文本按不可信数据处理；查询接口不返回参考答案评分点。

## 8. 数据库表

| 表 | 主键/索引 | 用途 |
|---|---|---|
| `profiles` | `candidate_id` | 跨会话长期画像 |
| `sessions` | `session_id` | 可恢复的面试状态快照 |
| `turns` | 自增 `id`，`session_id + id` 索引 | 按时间追加的完整问答 |
| `study_messages` | 自增 `id`，对话与候选人索引 | 多轮复习问题、回答及结构化元数据 |

存储 Pydantic JSON 的优点是 Demo 演进快且快照原子；大型生产系统可将高频筛选字段拆成列，并迁移到 PostgreSQL。若需要语义记忆，可在仓储接口后增加 pgvector/向量数据库，但不应把可审计的分数和会话状态只存入向量库。

## 9. 扩展方式

### 扩展题库

通用面试题可在 `QUESTION_DATA` 增加元组；带标准答案的知识题应写入
`data/knowledge_base*.json`，加载时会自动加入模拟面试。所有 ID 必须唯一；若新增领域，同时
加入 `SUPPORTED_TOPICS`。项目实战题还必须包含步骤、示例、验证和易错点，不能只给概念。

### 更换模型供应商

兼容 OpenAI API 的服务只需调整 `.env` 中的地址和模型名。非兼容供应商可新增 `AnswerEvaluator` 实现，或把 `LangChainEvaluator` 中的聊天模型替换为对应 LangChain 集成。

### 生产化建议

- 用 PostgreSQL 替换业务 SQLite，并使用数据库型 LangGraph Checkpointer。
- 在多实例部署时为同一 `session_id` 增加乐观锁或分布式锁。
- 加入身份认证、候选人数据加密、保留期限和删除接口。
- 使用 LangSmith/OpenTelemetry 记录耗时、token、模型错误率，但避免采集敏感原始回答。
- 将题库迁移到带版本号的管理后台，记录评分标准版本以支持审计复现。
- 对 LLM 限流、熔断和降级；高风险工具调用应增加人工审批节点。

## 10. 测试策略

测试默认使用临时 SQLite 和离线评估器，不读取 `.env`、不访问网络：

- `test_question_bank.py` 验证领域覆盖、未知领域拒绝和不重复出题。
- `test_knowledge.py` 验证八领域覆盖、问答向量匹配和项目实战字段完整性。
- `test_memory.py` 验证新仓储实例能恢复会话、问答及长期画像。
- `test_workflow.py` 完成两轮面试，验证评分、下一题、结束状态和报告闭环。

线上模型输出质量还应使用一组固定回答做评测集，比较分数一致性、事实准确率和不同群体的公平性；单元测试不能替代模型评测。
