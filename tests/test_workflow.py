"""离线端到端工作流测试。"""

from pathlib import Path

from interview_agent.config import Settings
from interview_agent.evaluator import OfflineEvaluator
from interview_agent.graph import InterviewWorkflow
from interview_agent.memory import SQLiteMemoryRepository
from interview_agent.models import InterviewStatus
from interview_agent.question_bank import QuestionBank
from interview_agent.service import InterviewService


def _settings(database_path: Path) -> Settings:
    """构造不读取用户环境变量的测试配置。"""

    return Settings("", "", "test", 0, "offline", database_path, 4, "127.0.0.1", 8000, "INFO")


def test_complete_interview_and_generate_report(tmp_path) -> None:
    """从开始、回答到报告生成应形成闭环。"""

    settings = _settings(tmp_path / "workflow.db")
    service = InterviewService(
        settings, SQLiteMemoryRepository(settings.database_path), QuestionBank(), OfflineEvaluator()
    )
    workflow = InterviewWorkflow(service)
    started = workflow.invoke(
        {
            "action": "start",
            "candidate_id": "u1",
            "candidate_name": "张三",
            "topics": ["Java"],
            "difficulty": "中级",
            "total_questions": 2,
        }
    )
    session_id = started["session_id"]
    first = workflow.invoke(
        {
            "action": "answer",
            "session_id": session_id,
            "user_answer": "堆、虚拟机栈、元空间和直接内存",
        }
    )
    assert first["completed"] is False
    second = workflow.invoke(
        {
            "action": "answer",
            "session_id": session_id,
            "user_answer": "线程池包含队列、核心线程与拒绝策略",
        }
    )
    assert second["completed"] is True
    assert second["report"]["answered_questions"] == 2
    assert service.repository.get_session(session_id).status == InterviewStatus.COMPLETED
