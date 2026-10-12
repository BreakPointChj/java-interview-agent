"""依赖装配入口，把配置、仓储、题库、评估器和工作流连接起来。"""

from __future__ import annotations

from functools import lru_cache

from interview_agent.config import get_settings
from interview_agent.evaluator import create_evaluator
from interview_agent.graph import InterviewWorkflow
from interview_agent.knowledge import KnowledgeBase
from interview_agent.memory import SQLiteMemoryRepository
from interview_agent.question_bank import QuestionBank
from interview_agent.service import InterviewService
from interview_agent.study import StudyService, create_knowledge_assistant


@lru_cache(maxsize=1)
def get_workflow() -> InterviewWorkflow:
    """创建全局工作流；缓存可避免重复初始化数据库和模型客户端。"""

    settings = get_settings()
    repository = SQLiteMemoryRepository(settings.database_path)
    bank = QuestionBank()
    evaluator = create_evaluator(settings)
    service = InterviewService(settings, repository, bank, evaluator)
    return InterviewWorkflow(service)


@lru_cache(maxsize=1)
def get_study_service() -> StudyService:
    """创建复习问答服务，并复用面试工作流的持久化仓储。"""

    settings = get_settings()
    repository = get_workflow().service.repository
    assistant = create_knowledge_assistant(settings, KnowledgeBase())
    return StudyService(settings, repository, assistant)
