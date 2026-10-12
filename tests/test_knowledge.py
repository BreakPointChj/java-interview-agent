"""知识库覆盖率和向量匹配准确性测试。"""

from collections import Counter

from interview_agent.knowledge import KnowledgeBase
from interview_agent.models import CandidateProfile
from interview_agent.question_bank import SUPPORTED_TOPICS, QuestionBank
from interview_agent.study import OfflineKnowledgeAssistant


def test_knowledge_base_covers_eight_topics() -> None:
    """八个领域都应有足够的标准问答，且能扩充模拟面试题。"""

    knowledge = KnowledgeBase()
    counts = Counter(entry.topic for entry in knowledge.entries)
    assert set(counts) == set(SUPPORTED_TOPICS)
    assert all(counts[topic] >= 8 for topic in SUPPORTED_TOPICS)
    assert QuestionBank().count_available([]) >= 90


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
