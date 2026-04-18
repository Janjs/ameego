from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent


def _get_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


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
    tts_model: str
    tts_voice: str
    audio_output_device: str
    app_ui_enabled: bool
    app_ui_fullscreen: bool
    app_ui_geometry: str
    app_ui_display: str
    app_ui_xauthority: str
    log_level: str

    @classmethod
    def load(cls, env_path: str | Path | None = None) -> "Config":
        load_dotenv(env_path or BASE_DIR / ".env")
        return cls(
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            robot_name=os.getenv("ROBOT_NAME", "Ameego"),
            chat_model=os.getenv("OPENAI_CHAT_MODEL", "gpt-4.1-mini"),
            max_output_tokens=_get_int("OPENAI_MAX_OUTPUT_TOKENS", 250),
            tts_model=os.getenv("OPENAI_TTS_MODEL", "gpt-4o-mini-tts"),
            tts_voice=os.getenv("OPENAI_TTS_VOICE", "alloy"),
            audio_output_device=os.getenv("AUDIO_OUTPUT_DEVICE", "plughw:1,0"),
            app_ui_enabled=_get_bool("APP_UI_ENABLED", True),
            app_ui_fullscreen=_get_bool("APP_UI_FULLSCREEN", True),
            app_ui_geometry=os.getenv("APP_UI_GEOMETRY", "1280x720"),
            app_ui_display=os.getenv("APP_UI_DISPLAY", ":0"),
            app_ui_xauthority=os.getenv("APP_UI_XAUTHORITY", str(Path.home() / ".Xauthority")),
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
