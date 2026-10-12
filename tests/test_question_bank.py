"""题库行为测试。"""

import pytest

from interview_agent.models import Difficulty
from interview_agent.question_bank import SUPPORTED_TOPICS, QuestionBank


def test_question_bank_covers_all_topics() -> None:
    """所有声明的领域都必须至少有一道题。"""

    bank = QuestionBank()
    for topic in SUPPORTED_TOPICS:
        assert bank.count_available([topic]) > 0


def test_question_bank_rejects_unknown_topic() -> None:
    """未知领域不能静默回退。"""

    with pytest.raises(ValueError, match="不支持"):
        QuestionBank().select(["不存在"], Difficulty.INTERMEDIATE, [])
    with pytest.raises(ValueError, match="不存在"):
        QuestionBank().count_available(["Java", "不存在"])


def test_question_bank_does_not_repeat() -> None:
    """排除列表中的题不能再次选中。"""

    bank = QuestionBank()
    first = bank.select(["Java"], Difficulty.INTERMEDIATE, [])
    second = bank.select(["Java"], Difficulty.INTERMEDIATE, [first.id])
    assert first.id != second.id
