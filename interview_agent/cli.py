"""面向开发者的中文交互式命令行客户端。"""

from __future__ import annotations

import json

from interview_agent.bootstrap import get_workflow
from interview_agent.models import Difficulty
from interview_agent.question_bank import SUPPORTED_TOPICS


def _print_json(data: object) -> None:
    """以 UTF-8 中文友好的形式打印结构化结果。"""

    print(json.dumps(data, ensure_ascii=False, indent=2))


def run_cli() -> None:
    """启动交互式面试；输入 /quit 可提前退出，/report 可查看阶段报告。"""

    print("\n=== Java 全栈面试 Agent ===")
    print("支持领域：" + "、".join(SUPPORTED_TOPICS))
    candidate_id = input("候选人 ID [demo-user]：").strip() or "demo-user"
    candidate_name = input("候选人姓名 [候选人]：").strip() or "候选人"
    topic_text = input("面试领域（逗号分隔，留空表示全部）：").strip()
    topics = [item.strip() for item in topic_text.replace("，", ",").split(",") if item.strip()]
    difficulty_text = input("难度（初级/中级/高级）[中级]：").strip() or "中级"
    count_text = input("题目数量 [8]：").strip() or "8"

    try:
        Difficulty(difficulty_text)
        count = int(count_text)
        workflow = get_workflow()
        result = workflow.invoke(
            {
                "action": "start",
                "candidate_id": candidate_id,
                "candidate_name": candidate_name,
                "topics": topics,
                "difficulty": difficulty_text,
                "total_questions": count,
            }
        )
    except Exception as error:
        print(f"启动失败：{error}")
        return

    session_id = str(result["session_id"])
    question = result["question"]
    while True:
        print(f"\n[{question['topic']} / {question['difficulty']}] {question['question']}")
        if question.get("follow_up"):
            print("提示：回答充分时，面试官也会关注相关深入问题。")
        answer = input("你的回答：").strip()
        if answer.lower() == "/quit":
            print(f"已退出。会话 {session_id} 已保存，下次可通过 API 恢复。")
            return
        if answer.lower() == "/report":
            _print_json(workflow.service.report(session_id))
            continue
        if not answer:
            print("回答不能为空，请重新输入。")
            continue
        try:
            result = workflow.invoke(
                {"action": "answer", "session_id": session_id, "user_answer": answer}
            )
        except Exception as error:
            print(f"处理失败：{error}")
            continue

        evaluation = result["evaluation"]
        print(f"\n得分：{evaluation['score']}｜反馈：{evaluation['feedback']}")
        print("建议答案：" + evaluation["suggested_answer"])
        if result["completed"]:
            print("\n=== 面试完成 ===")
            _print_json(result["report"])
            return
        question = result["next_question"]
