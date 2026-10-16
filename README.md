# Java 全栈面试 Agent

这是一个面向 Java 后端/全栈岗位的完整面试 Demo，基于 **LangChain + LangGraph + SQLite** 构建。它不是一次性问答脚本：每个候选人都有跨会话画像，每次面试都有可恢复状态，评分会结合题目参考点、最近上下文和历史薄弱领域。

## 核心能力

- 覆盖 Java、Python、Spring、LangChain、LangGraph、数据库、缓存、消息队列、微服务、前端十个领域。
- 初级/中级/高级三级题目，最近两题表现会触发自适应难度调整。
- 独立智能复习助手：自由提问、连续追问、知识点总结和推荐追问，可恢复历史对话。
- 99 组标准问答知识条目与 128 道可抽取面试题，其中 35 组采用实战结构，使用本地 TF-IDF 余弦向量检索保证问答对应。
- 实战题显式给出落地步骤、代码/SQL/配置示例、验证方法和易错点，覆盖 OTel→Kafka→MySQL、Token 统计、Dify/ClickHouse、数据外发、RAG、日志平台和 Docker 排障。
- LangChain 结构化输出：模型必须返回经过 Pydantic 校验的分数、优点、缺点和建议答案。
- LangGraph 状态机：创建面试和回答评分使用显式节点与条件路由。
- 双层记忆：有限窗口的近期问答作为短期上下文；画像、均分和薄弱领域作为长期记忆。
- SQLite WAL 持久化，会话中断后仍可查询与恢复；提供完整问答审计记录。
- 中文 Web 单页应用、CLI 和 FastAPI 三种入口；内置无需密钥的离线模式。
- 对候选人输入设置数据边界，提示模型不得执行回答中夹带的指令，降低提示词注入风险。

## 快速开始

本项目要求 Python 3.11。推荐新建独立 Conda 环境，不要直接使用 Anaconda `base`：

```powershell
conda env create -f environment.yml
conda activate java-interview-agent
Copy-Item .env.example .env
```

在 `.env` 中填写 `OPENAI_API_KEY`。兼容 OpenAI 协议的服务可同时修改 `OPENAI_BASE_URL` 和 `OPENAI_MODEL`。如果只想离线体验，把配置改为：

```dotenv
AGENT_MODE=offline
```

离线模式按参考关键词覆盖率评分，只用于功能演示和测试，不能替代大模型的语义评价。

启动交互式命令行：

```powershell
python main.py
```

启动 API：

```powershell
python main.py api
```

打开 `http://127.0.0.1:8000` 使用完整的中文面试界面。界面支持创建面试、逐题作答、
结构化反馈、最终报告、长期画像和历史会话恢复。API 调试页面位于
`http://127.0.0.1:8000/docs`。运行质量检查：

```powershell
pytest
ruff check .
```

## API 示例

创建两题 Java/Spring 面试：

```powershell
$body = @{
  candidate_id = "candidate-001"
  candidate_name = "张三"
  topics = @("Java", "Spring")
  difficulty = "中级"
  total_questions = 2
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/interviews `
  -ContentType "application/json; charset=utf-8" -Body $body
```

使用响应中的 `session_id` 提交回答：

```powershell
$answer = @{ answer = "这里是候选人的回答" } | ConvertTo-Json
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/api/v1/interviews/<session_id>/answers `
  -ContentType "application/json; charset=utf-8" -Body $answer
```

另外两个只读接口为：

- `GET /api/v1/interviews/{session_id}`：查询当前状态和待回答题目。
- `GET /api/v1/interviews/{session_id}/report`：获取当前或最终面试报告。
- `GET /api/v1/candidates/{candidate_id}`：获取长期画像和最近面试记录。
- `POST /api/v1/study/ask`：向复习助手提问；传入 `conversation_id` 可连续追问。
- `GET /api/v1/study/conversations/{conversation_id}`：恢复指定复习对话。

详细设计、目录职责、数据流和扩展方案见 [docs/DESIGN.md](docs/DESIGN.md)，题库字段、
覆盖范围和向量检索原理见 [docs/KNOWLEDGE_BASE.md](docs/KNOWLEDGE_BASE.md)。

## 开源许可证

本项目采用 [MIT License](LICENSE)，可自由使用、修改和分发，但需保留许可证与版权声明。
