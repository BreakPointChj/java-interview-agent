"""面试领域服务：组织选题、评分、上下文、记忆更新与报告生成。"""

from __future__ import annotations

from collections import defaultdict
from uuid import uuid4

from interview_agent.config import Settings
from interview_agent.evaluator import AnswerEvaluator
from interview_agent.memory import SQLiteMemoryRepository
from interview_agent.models import (
    CandidateProfile,
    Difficulty,
    InterviewSession,
    InterviewStatus,
    Question,
    StartInterviewRequest,
    TurnRecord,
)
from interview_agent.question_bank import SUPPORTED_TOPICS, QuestionBank


class InterviewService:
    """与传输层无关的面试业务实现。"""

    def __init__(
        self,
        settings: Settings,
        repository: SQLiteMemoryRepository,
        bank: QuestionBank,
        evaluator: AnswerEvaluator,
    ) -> None:
        self.settings = settings
        self.repository = repository
        self.bank = bank
        self.evaluator = evaluator

    def start(self, request: StartInterviewRequest) -> dict[str, object]:
        """创建画像和会话，并返回第一道题。"""

        topics = request.topics or list(SUPPORTED_TOPICS)
        self.bank.validate_topics(topics)
        available = self.bank.count_available(topics)
        if request.total_questions > available:
            raise ValueError(f"所选领域仅有 {available} 道不重复题，total_questions 不能超过该值")

        profile = self.repository.get_profile(request.candidate_id) or CandidateProfile(
            candidate_id=request.candidate_id,
            name=request.candidate_name,
            target_level=request.difficulty,
            preferred_topics=topics,
        )
        profile.name = request.candidate_name
        profile.target_level = request.difficulty
        profile.preferred_topics = topics
        self.repository.save_profile(profile)

        question = self.bank.select(topics, request.difficulty, [], profile.weak_topics)
        session = InterviewSession(
            session_id=uuid4().hex,
            candidate_id=request.candidate_id,
            topics=topics,
            difficulty=request.difficulty,
            total_questions=request.total_questions,
            asked_question_ids=[question.id],
            current_question_id=question.id,
            status=InterviewStatus.IN_PROGRESS,
        )
        self.repository.save_session(session)
        return self._question_response(session, question)

    def answer(self, session_id: str, answer: str) -> dict[str, object]:
        """评价当前回答，写入记忆，然后自适应选择下一题或结束面试。"""

        session = self._require_session(session_id)
        if session.status == InterviewStatus.COMPLETED:
            raise ValueError("该面试已经结束，不能继续提交回答")
        if not session.current_question_id:
            raise RuntimeError("会话缺少当前题目，数据状态不完整")

        question = self.bank.get(session.current_question_id)
        profile = self.repository.get_profile(session.candidate_id) or CandidateProfile(
            candidate_id=session.candidate_id
        )
        recent_turns = self.repository.get_recent_turns(
            session_id, self.settings.context_window_turns
        )
        evaluation = self.evaluator.evaluate(question, answer.strip(), profile, recent_turns)
        turn = TurnRecord(
            session_id=session_id,
            question_id=question.id,
            question=question.question,
            answer=answer.strip(),
            evaluation=evaluation,
        )
        self.repository.add_turn(turn)
        self.repository.update_profile_from_turn(
            session.candidate_id, question.topic, evaluation.score
        )
        session.scores.append(evaluation.score)
        session.current_index += 1

        if session.current_index >= session.total_questions:
            session.status = InterviewStatus.COMPLETED
            session.current_question_id = None
            self.repository.save_session(session)
            return {
                "session_id": session_id,
                "completed": True,
                "evaluation": evaluation.model_dump(mode="json"),
                "report": self.report(session_id),
            }

        updated_profile = self.repository.get_profile(session.candidate_id) or profile
        next_difficulty = self._adaptive_difficulty(session)
        next_question = self.bank.select(
            session.topics,
            next_difficulty,
            session.asked_question_ids,
            updated_profile.weak_topics,
        )
        session.current_question_id = next_question.id
        session.asked_question_ids.append(next_question.id)
        self.repository.save_session(session)
        return {
            "session_id": session_id,
            "completed": False,
            "evaluation": evaluation.model_dump(mode="json"),
            "next_question": next_question.model_dump(mode="json", exclude={"reference_points"}),
            "progress": {"answered": session.current_index, "total": session.total_questions},
        }

    def _adaptive_difficulty(self, session: InterviewSession) -> Difficulty:
        """依据最近两题均分小幅调难度，避免单次波动导致跳级。"""

        levels = [Difficulty.JUNIOR, Difficulty.INTERMEDIATE, Difficulty.SENIOR]
        base_index = levels.index(session.difficulty)
        recent = session.scores[-2:]
        if len(recent) == 2 and sum(recent) / 2 >= 85:
            return levels[min(2, base_index + 1)]
        if len(recent) == 2 and sum(recent) / 2 < 50:
            return levels[max(0, base_index - 1)]
        return session.difficulty

    def get_session(self, session_id: str) -> dict[str, object]:
        """返回会话和当前题目，但不泄露评分参考点。"""

        session = self._require_session(session_id)
        payload: dict[str, object] = {"session": session.model_dump(mode="json")}
        if session.current_question_id:
            question = self.bank.get(session.current_question_id)
            payload["current_question"] = question.model_dump(
                mode="json", exclude={"reference_points"}
            )
        return payload

    def get_candidate(self, candidate_id: str) -> dict[str, object]:
        """返回候选人长期画像和最近会话，供个人面板展示。"""

        profile = self.repository.get_profile(candidate_id)
        sessions = self.repository.list_sessions(candidate_id)
        return {
            "profile": profile.model_dump(mode="json") if profile else None,
            "study_conversations": self.repository.list_study_conversations(candidate_id),
            "sessions": [
                {
                    "session_id": session.session_id,
                    "topics": session.topics,
                    "difficulty": session.difficulty.value,
                    "total_questions": session.total_questions,
                    "answered_questions": session.current_index,
                    "average_score": round(sum(session.scores) / len(session.scores), 2)
                    if session.scores
                    else 0,
                    "status": session.status.value,
                    "updated_at": session.updated_at,
                }
                for session in sessions
            ],
        }

    def report(self, session_id: str) -> dict[str, object]:
        """聚合总分、领域得分、优劣势和学习建议。"""

        exported = self.repository.export_session(session_id)
        session = self._require_session(session_id)
        turns = self.repository.get_recent_turns(session_id, 1000)
        topic_scores: dict[str, list[int]] = defaultdict(list)
        strengths: list[str] = []
        weaknesses: list[str] = []
        for turn in turns:
            topic = self.bank.get(turn.question_id).topic
            topic_scores[topic].append(turn.evaluation.score)
            strengths.extend(turn.evaluation.strengths)
            weaknesses.extend(turn.evaluation.weaknesses)
        topic_averages = {
            topic: round(sum(values) / len(values), 2) for topic, values in topic_scores.items()
        }
        average = round(sum(session.scores) / len(session.scores), 2) if session.scores else 0.0
        weak = sorted(topic_averages, key=topic_averages.get)[:2]
        return {
            "session_id": session_id,
            "status": session.status.value,
            "average_score": average,
            "topic_scores": topic_averages,
            "representative_strengths": list(dict.fromkeys(strengths))[:5],
            "priority_improvements": list(dict.fromkeys(weaknesses))[:5],
            "learning_suggestion": f"建议优先复习：{'、'.join(weak)}。"
            if weak
            else "完成更多题目后生成建议。",
            "answered_questions": len(turns),
            "detail": exported["turns"],
        }

    def _require_session(self, session_id: str) -> InterviewSession:
        """读取会话，不存在则转换为统一异常。"""

        session = self.repository.get_session(session_id)
        if session is None:
            raise KeyError(f"面试会话不存在：{session_id}")
        return session

    @staticmethod
    def _question_response(session: InterviewSession, question: Question) -> dict[str, object]:
        """构建不包含答案参考点的对外响应。"""

        return {
            "session_id": session.session_id,
            "completed": False,
            "question": question.model_dump(mode="json", exclude={"reference_points"}),
            "progress": {"answered": 0, "total": session.total_questions},
        }
