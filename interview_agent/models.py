"""领域模型：约束 API、持久化层和工作流之间交换的数据。"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, TypedDict

from pydantic import BaseModel, Field


def utc_now_iso() -> str:
    """返回带时区的 ISO 时间，避免跨时区部署产生歧义。"""

    return datetime.now(UTC).isoformat()


class Difficulty(StrEnum):
    """面试难度。"""

    JUNIOR = "初级"
    INTERMEDIATE = "中级"
    SENIOR = "高级"


class InterviewStatus(StrEnum):
    """面试会话生命周期。"""

    CREATED = "created"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class Question(BaseModel):
    """一道结构化面试题。"""

    id: str
    topic: str
    difficulty: Difficulty
    question: str
    reference_points: list[str]
    follow_up: str | None = None


class Evaluation(BaseModel):
    """模型对单次回答的结构化评价。"""

    score: int = Field(ge=0, le=100)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    missing_points: list[str] = Field(default_factory=list)
    feedback: str
    suggested_answer: str


class CandidateProfile(BaseModel):
    """候选人画像，可在多个会话之间长期保存。"""

    candidate_id: str
    name: str = "候选人"
    target_level: Difficulty = Difficulty.INTERMEDIATE
    preferred_topics: list[str] = Field(default_factory=list)
    total_answers: int = 0
    average_score: float = 0.0
    weak_topics: dict[str, int] = Field(default_factory=dict)


class InterviewSession(BaseModel):
    """一次面试会话的可持久化状态。"""

    session_id: str
    candidate_id: str
    topics: list[str]
    difficulty: Difficulty
    total_questions: int = Field(ge=1, le=50)
    current_index: int = 0
    asked_question_ids: list[str] = Field(default_factory=list)
    current_question_id: str | None = None
    status: InterviewStatus = InterviewStatus.CREATED
    scores: list[int] = Field(default_factory=list)
    created_at: str = Field(default_factory=utc_now_iso)
    updated_at: str = Field(default_factory=utc_now_iso)


class TurnRecord(BaseModel):
    """一轮问答记录，是短期上下文和审计信息的来源。"""

    session_id: str
    question_id: str
    question: str
    answer: str
    evaluation: Evaluation
    created_at: str = Field(default_factory=utc_now_iso)


class InterviewState(TypedDict, total=False):
    """LangGraph 节点之间传递的状态。"""

    action: str
    session_id: str
    candidate_id: str
    candidate_name: str
    topics: list[str]
    difficulty: str
    total_questions: int
    user_answer: str
    session: dict[str, Any]
    question: dict[str, Any]
    evaluation: dict[str, Any]
    response: dict[str, Any]
    error: str


class StartInterviewRequest(BaseModel):
    """创建面试的请求体。"""

    candidate_id: str = Field(min_length=1, max_length=100)
    candidate_name: str = Field(default="候选人", max_length=100)
    topics: list[str] = Field(default_factory=list)
    difficulty: Difficulty = Difficulty.INTERMEDIATE
    total_questions: int = Field(default=8, ge=1, le=50)


class SubmitAnswerRequest(BaseModel):
    """提交回答的请求体。"""

    answer: str = Field(min_length=1, max_length=20_000)


class StudyQuestionRequest(BaseModel):
    """智能复习提问请求；conversation_id 为空时创建新对话。"""

    candidate_id: str = Field(min_length=1, max_length=100)
    question: str = Field(min_length=2, max_length=10_000)
    conversation_id: str | None = Field(default=None, max_length=100)
    topic: str | None = Field(default=None, max_length=50)


class StudyAnswer(BaseModel):
    """复习助手的结构化回答，便于前端分区展示。"""

    topic: str
    answer: str
    key_points: list[str] = Field(default_factory=list)
    follow_up_questions: list[str] = Field(default_factory=list)
    matched_questions: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class StudyMessage(BaseModel):
    """一条可持久化的复习对话消息。"""

    conversation_id: str
    candidate_id: str
    role: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=utc_now_iso)
