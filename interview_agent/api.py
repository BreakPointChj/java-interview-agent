"""FastAPI 接口，供 Web 前端、Postman 或其他服务调用。"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from interview_agent.bootstrap import get_study_service, get_workflow
from interview_agent.config import get_settings
from interview_agent.models import StartInterviewRequest, StudyQuestionRequest, SubmitAnswerRequest
from interview_agent.question_bank import SUPPORTED_TOPICS, QuestionBank

app = FastAPI(
    title="Java 全栈面试 Agent",
    description="支持多轮上下文、长期记忆、自适应难度和结构化反馈的面试服务",
    version="1.0.0",
)

# 静态文件随 Python 包发布，避免依赖当前启动目录。
WEB_DIRECTORY = Path(__file__).resolve().parent / "web"
app.mount("/static", StaticFiles(directory=WEB_DIRECTORY), name="static")


def _http_error(error: Exception) -> HTTPException:
    """将领域异常转换为语义清晰的 HTTP 错误。"""

    if isinstance(error, KeyError):
        return HTTPException(status_code=404, detail=str(error).strip("'"))
    if isinstance(error, (ValueError, LookupError)):
        return HTTPException(status_code=400, detail=str(error))
    return HTTPException(status_code=500, detail=f"服务处理失败：{error}")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    """返回完整的中文面试 Agent 单页界面。"""

    return FileResponse(WEB_DIRECTORY / "index.html", media_type="text/html; charset=utf-8")


@app.get("/health", summary="健康检查")
def health() -> dict[str, object]:
    """返回服务状态和支持领域。"""

    settings = get_settings()
    bank = QuestionBank()
    return {
        "status": "ok",
        "agent_mode": settings.agent_mode,
        "model": settings.openai_model if not settings.is_offline else "离线规则评估器",
        "supported_topics": list(SUPPORTED_TOPICS),
        "topic_counts": {topic: bank.count_available([topic]) for topic in SUPPORTED_TOPICS},
        "question_count": bank.count_available([]),
    }


@app.post("/api/v1/interviews", summary="创建面试")
def start_interview(request: StartInterviewRequest) -> dict[str, object]:
    """创建持久化会话并返回第一题。"""

    try:
        return get_workflow().invoke(
            {
                "action": "start",
                "candidate_id": request.candidate_id,
                "candidate_name": request.candidate_name,
                "topics": request.topics,
                "difficulty": request.difficulty.value,
                "total_questions": request.total_questions,
            }
        )
    except Exception as error:
        raise _http_error(error) from error


@app.post("/api/v1/interviews/{session_id}/answers", summary="提交回答")
def submit_answer(session_id: str, request: SubmitAnswerRequest) -> dict[str, object]:
    """评估本轮回答并返回下一题或最终报告。"""

    try:
        return get_workflow().invoke(
            {"action": "answer", "session_id": session_id, "user_answer": request.answer}
        )
    except Exception as error:
        raise _http_error(error) from error


@app.get("/api/v1/interviews/{session_id}", summary="查询面试状态")
def get_interview(session_id: str) -> dict[str, object]:
    """查询可恢复的会话状态和当前题目。"""

    try:
        return get_workflow().service.get_session(session_id)
    except Exception as error:
        raise _http_error(error) from error


@app.get("/api/v1/interviews/{session_id}/report", summary="获取面试报告")
def get_report(session_id: str) -> dict[str, object]:
    """返回实时或最终聚合报告。"""

    try:
        return get_workflow().service.report(session_id)
    except Exception as error:
        raise _http_error(error) from error


@app.get("/api/v1/candidates/{candidate_id}", summary="获取候选人画像")
def get_candidate(candidate_id: str) -> dict[str, object]:
    """返回长期能力画像以及最近面试列表。"""

    try:
        return get_workflow().service.get_candidate(candidate_id)
    except Exception as error:
        raise _http_error(error) from error


@app.post("/api/v1/study/ask", summary="向复习助手提问")
def ask_study_assistant(request: StudyQuestionRequest) -> dict[str, object]:
    """结合长期画像和最近对话，回答技术复习问题。"""

    try:
        return get_study_service().ask(request)
    except Exception as error:
        raise _http_error(error) from error


@app.get("/api/v1/study/conversations/{conversation_id}", summary="恢复复习对话")
def get_study_conversation(conversation_id: str, candidate_id: str) -> dict[str, object]:
    """返回指定候选人的完整复习对话。"""

    try:
        return get_study_service().get_conversation(candidate_id, conversation_id)
    except Exception as error:
        raise _http_error(error) from error
