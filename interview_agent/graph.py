"""使用 LangGraph 将创建面试与回答处理编排成显式状态机。"""

from __future__ import annotations

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from interview_agent.models import Difficulty, InterviewState, StartInterviewRequest
from interview_agent.service import InterviewService


class InterviewWorkflow:
    """面试工作流门面；业务数据持久化到 SQLite，图检查点保存进程内执行快照。"""

    def __init__(self, service: InterviewService) -> None:
        self.service = service
        builder = StateGraph(InterviewState)
        builder.add_node("start_interview", self._start_interview)
        builder.add_node("evaluate_answer", self._evaluate_answer)
        builder.add_conditional_edges(
            START,
            self._route,
            {"start": "start_interview", "answer": "evaluate_answer"},
        )
        builder.add_edge("start_interview", END)
        builder.add_edge("evaluate_answer", END)
        self.graph = builder.compile(checkpointer=InMemorySaver())

    @staticmethod
    def _route(state: InterviewState) -> str:
        """按动作路由；拒绝未声明操作。"""

        action = state.get("action", "")
        if action not in {"start", "answer"}:
            raise ValueError(f"未知工作流动作：{action}")
        return action

    def _start_interview(self, state: InterviewState) -> InterviewState:
        """把图状态转换为领域请求。"""

        request = StartInterviewRequest(
            candidate_id=state["candidate_id"],
            candidate_name=state.get("candidate_name", "候选人"),
            topics=state.get("topics", []),
            difficulty=Difficulty(state.get("difficulty", Difficulty.INTERMEDIATE.value)),
            total_questions=state.get("total_questions", 8),
        )
        return {"response": self.service.start(request)}

    def _evaluate_answer(self, state: InterviewState) -> InterviewState:
        """处理一轮回答。"""

        return {"response": self.service.answer(state["session_id"], state["user_answer"])}

    def invoke(self, state: InterviewState) -> dict[str, object]:
        """为每次 HTTP/CLI 请求使用唯一图线程，业务会话 ID 仍由 SQLite 连续维护。"""

        import uuid

        result = self.graph.invoke(state, config={"configurable": {"thread_id": uuid.uuid4().hex}})
        return result["response"]
