"""知识库覆盖率和向量匹配准确性测试。"""

from collections import Counter

from interview_agent.knowledge import KnowledgeBase
from interview_agent.models import CandidateProfile
from interview_agent.question_bank import SUPPORTED_TOPICS, QuestionBank
from interview_agent.study import OfflineKnowledgeAssistant


def test_knowledge_base_covers_supported_topics() -> None:
    """所有声明领域都应有标准问答，八个核心领域至少保留八题。"""

    knowledge = KnowledgeBase()
    counts = Counter(entry.topic for entry in knowledge.entries)
    assert set(counts) == set(SUPPORTED_TOPICS)
    core_topics = set(SUPPORTED_TOPICS) - {"微服务", "前端"}
    assert all(counts[topic] >= 8 for topic in core_topics)
    assert counts["微服务"] >= 7
    assert counts["前端"] >= 1
    assert QuestionBank().count_available([]) >= 128


def test_exact_question_overrides_wrong_topic_hint() -> None:
    """强问题语义应优先于误选领域，避免截图中的错配问题。"""

    knowledge = KnowledgeBase()
    result = knowledge.search("CPU 密集型与 IO 密集型参数如何估算？", topic_hint="Python")
    assert result[0].entry.id == "kb-java-02"
    assert result[0].score >= 0.9

    answer = OfflineKnowledgeAssistant(knowledge).answer(
        "CPU 密集型与 IO 密集型参数如何估算？",
        "Python",
        CandidateProfile(candidate_id="u1"),
        [],
    )
    assert answer.topic == "Java"
    assert "CPU 核数" in answer.answer
    assert "Runnable" not in answer.answer
    assert answer.matched_questions == [result[0].entry.question]


def test_semantic_variant_retrieves_corresponding_answer() -> None:
    """非逐字相同的常见问法也应召回正确条目。"""

    result = KnowledgeBase().search("线程池大小到底应该怎么设置")
    assert result[0].entry.id == "kb-java-02"


def test_resume_practical_entries_are_actionable() -> None:
    """简历项目题必须包含实施、验证和边界，不能退化成概念描述。"""

    practical_entries = [
        entry for entry in KnowledgeBase().entries if entry.id.startswith("kb-practical-")
    ]
    assert len(practical_entries) == 25
    for entry in practical_entries:
        assert entry.project_context
        assert len(entry.practical_steps) >= 3
        assert entry.example
        assert entry.verification
        assert entry.pitfalls
        rendered = entry.render_answer()
        assert "实际工作场景：" in rendered
        assert "落地步骤：" in rendered
        assert "验证与排查：" in rendered
        assert "易错点：" in rendered


def test_resume_question_returns_matching_concrete_answer() -> None:
    """项目原题应命中对应条目，并返回 SQL、步骤和验证方法。"""

    knowledge = KnowledgeBase()
    question = "Token 使用量的明细表和日周月统计应怎样设计？"
    result = knowledge.search(question)
    assert result[0].entry.id == "kb-practical-db-01"

    answer = OfflineKnowledgeAssistant(knowledge).answer(
        question,
        None,
        CandidateProfile(candidate_id="resume-user"),
        [],
    )
    assert "event_id" in answer.answer
    assert "SELECT account_id" in answer.answer
    assert "验证与排查：" in answer.answer


def test_resume_scenario_variants_retrieve_correct_entries() -> None:
    """简历项目的常见口语问法应命中对应实战答案。"""

    knowledge = KnowledgeBase()
    cases = {
        "Kafka重复消息怎么避免MySQL重复入库": "kb-practical-mq-02",
        "Kafka积压怎么排查": "kb-practical-mq-03",
        "ClickHouse异地登录查询怎么优化": "kb-practical-db-03",
        "Dify工作流怎么用LangGraph恢复": "kb-practical-langgraph-01",
        "RAG检索到了为什么回答还错": "kb-practical-langchain-01",
        "Docker容器启动但外部访问不到": "kb-practical-spring-03",
        "Java CPU 100怎么定位": "kb-practical-java-01",
        "第三方接口超时怎么重试": "kb-practical-spring-02",
    }
    for query, expected_id in cases.items():
        result = knowledge.search(query)[0]
        assert result.entry.id == expected_id
        assert result.score >= 0.12


def test_supplement_entries_are_actionable_and_retrievable() -> None:
    """补充资料应转成完整实战题，并覆盖常见口语问法。"""

    knowledge = KnowledgeBase()
    supplement_entries = [
        entry for entry in knowledge.entries if entry.id.startswith("kb-supplement-")
    ]
    assert len(supplement_entries) == 10
    assert all(len(entry.practical_steps) >= 3 for entry in supplement_entries)
    assert all(
        entry.example and entry.verification and entry.pitfalls
        for entry in supplement_entries
    )

    cases = {
        "Nacos挂了为什么Feign还能调用": "kb-supplement-microservice-01",
        "Nacos临时实例心跳机制": "kb-supplement-microservice-02",
        "Nacos配置动态刷新流程": "kb-supplement-microservice-03",
        "Feign底层原理": "kb-supplement-microservice-04",
        "Route Predicate Filter区别": "kb-supplement-microservice-06",
        "Gateway全局鉴权怎么做": "kb-supplement-microservice-07",
        "Vue2迁移Vue3要改什么": "kb-supplement-frontend-01",
        "Java创建线程有几种方式": "kb-supplement-java-01",
        "数据库三范式实际例子": "kb-supplement-db-01",
    }
    for query, expected_id in cases.items():
        result = knowledge.search(query)[0]
        assert result.entry.id == expected_id
        assert result.score >= 0.12
