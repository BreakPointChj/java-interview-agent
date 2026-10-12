"""SQLite 持久化记忆：近期问答为短期记忆，画像为跨会话长期记忆。"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from interview_agent.models import (
    CandidateProfile,
    InterviewSession,
    StudyMessage,
    TurnRecord,
    utc_now_iso,
)


class SQLiteMemoryRepository:
    """使用短连接和可重入锁实现的线程安全记忆仓储。"""

    def __init__(self, database_path: Path | str) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._initialize_schema()

    def _connect(self) -> sqlite3.Connection:
        """创建启用外键和 WAL 的独立连接。"""

        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def _initialize_schema(self) -> None:
        """幂等创建数据表。"""

        with self._lock, self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS profiles (
                    candidate_id TEXT PRIMARY KEY, payload TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY, candidate_id TEXT NOT NULL,
                    payload TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS turns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL,
                    payload TEXT NOT NULL, created_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES sessions(session_id)
                );
                CREATE INDEX IF NOT EXISTS idx_turns_session ON turns(session_id, id DESC);
                CREATE TABLE IF NOT EXISTS study_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    candidate_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_study_conversation
                    ON study_messages(conversation_id, id DESC);
                CREATE INDEX IF NOT EXISTS idx_study_candidate
                    ON study_messages(candidate_id, id DESC);
                """
            )

    def save_profile(self, profile: CandidateProfile) -> None:
        """新增或覆盖候选人长期画像。"""

        with self._lock, self._connect() as connection:
            connection.execute(
                """INSERT INTO profiles(candidate_id, payload, updated_at) VALUES (?, ?, ?)
                ON CONFLICT(candidate_id) DO UPDATE SET
                payload=excluded.payload, updated_at=excluded.updated_at""",
                (profile.candidate_id, profile.model_dump_json(), utc_now_iso()),
            )

    def get_profile(self, candidate_id: str) -> CandidateProfile | None:
        """读取候选人画像。"""

        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM profiles WHERE candidate_id = ?", (candidate_id,)
            ).fetchone()
        return CandidateProfile.model_validate_json(row["payload"]) if row else None

    def save_session(self, session: InterviewSession) -> None:
        """原子保存当前会话快照。"""

        session.updated_at = utc_now_iso()
        with self._lock, self._connect() as connection:
            connection.execute(
                """INSERT INTO sessions(session_id, candidate_id, payload, updated_at)
                VALUES (?, ?, ?, ?) ON CONFLICT(session_id) DO UPDATE SET
                payload=excluded.payload, updated_at=excluded.updated_at""",
                (
                    session.session_id,
                    session.candidate_id,
                    session.model_dump_json(),
                    session.updated_at,
                ),
            )

    def get_session(self, session_id: str) -> InterviewSession | None:
        """读取会话；不存在时返回 None。"""

        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
        return InterviewSession.model_validate_json(row["payload"]) if row else None

    def list_sessions(self, candidate_id: str, limit: int = 20) -> list[InterviewSession]:
        """按最近更新时间倒序返回候选人的会话，供前端恢复与历史查看。"""

        with self._connect() as connection:
            rows = connection.execute(
                """SELECT payload FROM sessions WHERE candidate_id = ?
                ORDER BY updated_at DESC LIMIT ?""",
                (candidate_id, limit),
            ).fetchall()
        return [InterviewSession.model_validate_json(row["payload"]) for row in rows]

    def add_turn(self, turn: TurnRecord) -> None:
        """追加一轮问答，不覆盖历史。"""

        with self._lock, self._connect() as connection:
            connection.execute(
                "INSERT INTO turns(session_id, payload, created_at) VALUES (?, ?, ?)",
                (turn.session_id, turn.model_dump_json(), turn.created_at),
            )

    def get_recent_turns(self, session_id: str, limit: int) -> list[TurnRecord]:
        """按时间正序返回最近问答，供上下文窗口使用。"""

        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM turns WHERE session_id = ? ORDER BY id DESC LIMIT ?",
                (session_id, limit),
            ).fetchall()
        return [TurnRecord.model_validate_json(row["payload"]) for row in reversed(rows)]

    def update_profile_from_turn(self, candidate_id: str, topic: str, score: int) -> None:
        """增量更新长期均分与薄弱领域统计。"""

        with self._lock:
            profile = self.get_profile(candidate_id) or CandidateProfile(candidate_id=candidate_id)
            previous_total = profile.total_answers
            profile.average_score = round(
                (profile.average_score * previous_total + score) / (previous_total + 1), 2
            )
            profile.total_answers += 1
            if score < 70:
                profile.weak_topics[topic] = profile.weak_topics.get(topic, 0) + 1
            elif topic in profile.weak_topics:
                profile.weak_topics[topic] = max(0, profile.weak_topics[topic] - 1)
            self.save_profile(profile)

    def export_session(self, session_id: str) -> dict[str, object]:
        """导出完整面试记录，便于生成报告与审计。"""

        session = self.get_session(session_id)
        if session is None:
            raise KeyError(f"面试会话不存在：{session_id}")
        turns = self.get_recent_turns(session_id, limit=1000)
        return {
            "session": session.model_dump(mode="json"),
            "turns": [turn.model_dump(mode="json") for turn in turns],
        }

    def add_study_message(self, message: StudyMessage) -> None:
        """追加复习对话消息，保留完整的提问和回答顺序。"""

        with self._lock, self._connect() as connection:
            connection.execute(
                """INSERT INTO study_messages(
                    conversation_id, candidate_id, role, payload, created_at
                ) VALUES (?, ?, ?, ?, ?)""",
                (
                    message.conversation_id,
                    message.candidate_id,
                    message.role,
                    message.model_dump_json(),
                    message.created_at,
                ),
            )

    def get_study_messages(self, conversation_id: str, limit: int = 20) -> list[StudyMessage]:
        """按正序返回某次复习对话的最近消息。"""

        with self._connect() as connection:
            rows = connection.execute(
                """SELECT payload FROM study_messages WHERE conversation_id = ?
                ORDER BY id DESC LIMIT ?""",
                (conversation_id, limit),
            ).fetchall()
        return [StudyMessage.model_validate_json(row["payload"]) for row in reversed(rows)]

    def list_study_conversations(
        self, candidate_id: str, limit: int = 10
    ) -> list[dict[str, object]]:
        """返回候选人的复习对话摘要，用第一条提问作为标题。"""

        with self._connect() as connection:
            rows = connection.execute(
                """SELECT conversation_id, MAX(id) AS last_id, COUNT(*) AS message_count
                FROM study_messages WHERE candidate_id = ?
                GROUP BY conversation_id ORDER BY last_id DESC LIMIT ?""",
                (candidate_id, limit),
            ).fetchall()
            result: list[dict[str, object]] = []
            for row in rows:
                first = connection.execute(
                    """SELECT payload FROM study_messages
                    WHERE conversation_id = ? AND role = 'user' ORDER BY id ASC LIMIT 1""",
                    (row["conversation_id"],),
                ).fetchone()
                if first:
                    message = StudyMessage.model_validate_json(first["payload"])
                    result.append(
                        {
                            "conversation_id": row["conversation_id"],
                            "title": message.content[:40],
                            "message_count": row["message_count"],
                        }
                    )
        return result
