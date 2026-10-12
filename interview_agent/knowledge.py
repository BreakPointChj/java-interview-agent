"""结构化八股文知识库与无需外部服务的 TF-IDF 向量检索。"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, Field

from interview_agent.models import Difficulty


class KnowledgeEntry(BaseModel):
    """一道问题及其严格对应的答案、别名与检索元数据。"""

    id: str
    topic: str
    difficulty: Difficulty
    question: str
    aliases: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    answer: str
    key_points: list[str]
    follow_up_questions: list[str] = Field(default_factory=list)


@dataclass(frozen=True, slots=True)
class SearchResult:
    """向量检索结果，score 已归一化到 0-1。"""

    entry: KnowledgeEntry
    score: float


class KnowledgeBase:
    """加载知识库并在内存中构建稀疏 TF-IDF 向量索引。"""

    def __init__(self, data_path: Path | None = None) -> None:
        path = data_path or Path(__file__).resolve().parent / "data" / "knowledge_base.json"
        raw_data = json.loads(path.read_text(encoding="utf-8"))
        self.entries = [KnowledgeEntry.model_validate(item) for item in raw_data]
        self._idf: dict[str, float] = {}
        self._vectors: list[dict[str, float]] = []
        self._build_index()

    @staticmethod
    def _normalize(text: str) -> str:
        """统一常见写法，降低大小写、空格和中英文别名造成的召回损失。"""

        normalized = text.lower().replace("i/o", "io").replace("j.d.k", "jdk")
        replacements = {
            "中央处理器": "cpu",
            "输入输出": "io",
            "线程池参数配置": "线程池配置",
            "数据库": "db",
            "缓存": "cache",
            "消息队列": "mq",
        }
        for source, target in replacements.items():
            normalized = normalized.replace(source, target)
        return re.sub(r"\s+", "", normalized)

    @classmethod
    def _tokenize(cls, text: str) -> list[str]:
        """抽取英文词与中文 2/3-gram，形成适合技术短问题的稀疏向量。"""

        normalized = cls._normalize(text)
        latin = re.findall(r"[a-z][a-z0-9_.+#-]*|\d+", normalized)
        chinese_parts = re.findall(r"[\u4e00-\u9fff]+", normalized)
        chinese_tokens: list[str] = []
        for part in chinese_parts:
            for size in (2, 3):
                chinese_tokens.extend(
                    part[index : index + size] for index in range(len(part) - size + 1)
                )
        return latin + chinese_tokens

    @staticmethod
    def _entry_text(entry: KnowledgeEntry) -> str:
        """索引问题侧字段，不把长答案放入向量以免无关词稀释主题。"""

        return " ".join(
            [entry.topic, entry.question, *entry.aliases, *entry.keywords, *entry.key_points]
        )

    def _build_index(self) -> None:
        """计算逆文档频率和单位化稀疏文档向量。"""

        tokenized = [self._tokenize(self._entry_text(entry)) for entry in self.entries]
        document_frequency: Counter[str] = Counter()
        for tokens in tokenized:
            document_frequency.update(set(tokens))
        count = len(tokenized)
        self._idf = {
            token: math.log((count + 1) / (frequency + 1)) + 1
            for token, frequency in document_frequency.items()
        }
        self._vectors = [self._vectorize_tokens(tokens) for tokens in tokenized]

    def _vectorize_tokens(self, tokens: list[str]) -> dict[str, float]:
        """生成 L2 单位化 TF-IDF 稀疏向量。"""

        frequencies = Counter(tokens)
        vector = {
            token: (1 + math.log(frequency)) * self._idf.get(token, 1.0)
            for token, frequency in frequencies.items()
        }
        norm = math.sqrt(sum(value * value for value in vector.values())) or 1.0
        return {token: value / norm for token, value in vector.items()}

    def search(
        self,
        query: str,
        topic_hint: str | None = None,
        history_queries: list[str] | None = None,
        limit: int = 3,
    ) -> list[SearchResult]:
        """以当前问题为主、历史问题为辅检索，并用别名精确命中修正向量分数。"""

        history = " ".join((history_queries or [])[-2:])
        query_text = f"{query} {history}"
        query_vector = self._vectorize_tokens(self._tokenize(query_text))
        normalized_query = self._normalize(query)
        results: list[SearchResult] = []
        for entry, vector in zip(self.entries, self._vectors, strict=True):
            cosine = sum(value * vector.get(token, 0.0) for token, value in query_vector.items())
            aliases = [entry.question, *entry.aliases]
            exact_bonus = 0.0
            for alias in aliases:
                normalized_alias = self._normalize(alias).rstrip("？?")
                if len(normalized_alias) >= 4 and (
                    normalized_alias in normalized_query or normalized_query in normalized_alias
                ):
                    exact_bonus = max(exact_bonus, 0.55)
            keyword_hits = sum(
                1 for keyword in entry.keywords if self._normalize(keyword) in normalized_query
            )
            keyword_bonus = min(0.2, keyword_hits * 0.05)
            topic_bonus = 0.08 if topic_hint and entry.topic == topic_hint else 0.0
            score = min(1.0, cosine * 0.72 + exact_bonus + keyword_bonus + topic_bonus)
            results.append(SearchResult(entry=entry, score=round(score, 4)))
        return sorted(results, key=lambda item: item.score, reverse=True)[:limit]
