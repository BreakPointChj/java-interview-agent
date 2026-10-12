"""智能复习助手端到端测试。"""

from interview_agent.config import Settings
from interview_agent.knowledge import KnowledgeBase
from interview_agent.memory import SQLiteMemoryRepository
from interview_agent.models import StudyQuestionRequest
from interview_agent.study import OfflineKnowledgeAssistant, StudyService


def test_study_question_keeps_context(tmp_path) -> None:
    """连续提问应复用对话 ID，并持久化用户与助手消息。"""

    settings = Settings(
        "", "", "test", 0, "offline", tmp_path / "study.db", 4, "127.0.0.1", 8000, "INFO"
    )
    repository = SQLiteMemoryRepository(settings.database_path)
    service = StudyService(settings, repository, OfflineKnowledgeAssistant(KnowledgeBase()))
    first = service.ask(
        StudyQuestionRequest(candidate_id="u1", question="JVM 内存区域有哪些？", topic="Java")
    )
    second = service.ask(
        StudyQuestionRequest(
            candidate_id="u1",
            question="其中堆内存有什么作用？",
            topic="Java",
            conversation_id=first["conversation_id"],
        )
    )
    assert second["conversation_id"] == first["conversation_id"]
    assert len(repository.get_study_messages(first["conversation_id"])) == 4
    assert first["key_points"]
