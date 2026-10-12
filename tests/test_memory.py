"""SQLite 长短期记忆测试。"""

from interview_agent.memory import SQLiteMemoryRepository
from interview_agent.models import (
    Difficulty,
    Evaluation,
    InterviewSession,
    StudyMessage,
    TurnRecord,
)


def test_memory_persists_session_turn_and_profile(tmp_path) -> None:
    """会话、问答和画像必须可以跨仓储实例恢复。"""

    database = tmp_path / "memory.db"
    repository = SQLiteMemoryRepository(database)
    session = InterviewSession(
        session_id="s1",
        candidate_id="u1",
        topics=["Java"],
        difficulty=Difficulty.INTERMEDIATE,
        total_questions=2,
    )
    repository.save_session(session)
    evaluation = Evaluation(score=60, feedback="尚可", suggested_answer="参考")
    repository.add_turn(
        TurnRecord(
            session_id="s1",
            question_id="java-01",
            question="问题",
            answer="回答",
            evaluation=evaluation,
        )
    )
    repository.update_profile_from_turn("u1", "Java", 60)

    restored = SQLiteMemoryRepository(database)
    assert restored.get_session("s1") is not None
    assert restored.list_sessions("u1")[0].session_id == "s1"
    assert len(restored.get_recent_turns("s1", 10)) == 1
    profile = restored.get_profile("u1")
    assert profile is not None
    assert profile.weak_topics["Java"] == 1

    repository.add_study_message(
        StudyMessage(
            conversation_id="c1",
            candidate_id="u1",
            role="user",
            content="什么是 JVM？",
        )
    )
    assert repository.get_study_messages("c1")[0].content == "什么是 JVM？"
    assert repository.list_study_conversations("u1")[0]["conversation_id"] == "c1"
