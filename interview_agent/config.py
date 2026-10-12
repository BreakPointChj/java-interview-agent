"""集中管理运行配置，避免业务代码散落读取环境变量。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True, slots=True)
class Settings:
    """不可变应用配置，保证全进程配置一致。"""

    openai_api_key: str
    openai_base_url: str
    openai_model: str
    llm_temperature: float
    agent_mode: str
    database_path: Path
    context_window_turns: int
    api_host: str
    api_port: int
    log_level: str

    @property
    def is_offline(self) -> bool:
        """是否使用无需网络和密钥的离线评估器。"""

        return self.agent_mode == "offline"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """从 UTF-8 的 .env 加载并校验配置。"""

    load_dotenv(encoding="utf-8")
    mode = os.getenv("AGENT_MODE", "openai").strip().lower()
    if mode not in {"openai", "offline"}:
        raise ValueError("AGENT_MODE 仅支持 openai 或 offline")
    context_turns = int(os.getenv("CONTEXT_WINDOW_TURNS", "8"))
    if not 1 <= context_turns <= 30:
        raise ValueError("CONTEXT_WINDOW_TURNS 必须在 1 到 30 之间")
    return Settings(
        openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
        openai_base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip(),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip(),
        llm_temperature=float(os.getenv("LLM_TEMPERATURE", "0.2")),
        agent_mode=mode,
        database_path=Path(os.getenv("DATABASE_PATH", "data/interview_agent.db")),
        context_window_turns=context_turns,
        api_host=os.getenv("API_HOST", "127.0.0.1"),
        api_port=int(os.getenv("API_PORT", "8000")),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
    )


def validate_runtime(settings: Settings) -> None:
    """在调用模型前检查密钥，给出可操作的错误信息。"""

    if not settings.is_offline and (
        not settings.openai_api_key or settings.openai_api_key == "sk-"
    ):
        raise RuntimeError(
            "未配置 OPENAI_API_KEY。请复制 .env.example 为 .env 并填写密钥，"
            "或设置 AGENT_MODE=offline 体验离线模式。"
        )
