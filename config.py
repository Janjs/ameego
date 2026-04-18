from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return int(raw)


@dataclass(slots=True)
class Config:
    openai_api_key: str
    robot_name: str
    chat_model: str
    max_output_tokens: int
    log_level: str

    @classmethod
    def load(cls, env_path: str | Path | None = None) -> "Config":
        load_dotenv(env_path or BASE_DIR / ".env")
        return cls(
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            robot_name=os.getenv("ROBOT_NAME", "Ameego"),
            chat_model=os.getenv("OPENAI_CHAT_MODEL", "gpt-4.1-mini"),
            max_output_tokens=_get_int("OPENAI_MAX_OUTPUT_TOKENS", 250),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        )

    def validate(self) -> None:
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY is not set.")
        if self.max_output_tokens < 1:
            raise ValueError("OPENAI_MAX_OUTPUT_TOKENS must be at least 1.")


def configure_logging(level_name: str) -> None:
    level = getattr(logging, level_name.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
