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


def _get_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return float(raw)


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return int(raw)


@dataclass(slots=True)
class Config:
    openai_api_key: str
    robot_name: str
    wake_word_name: str
    wakeword_model_path: str | None
    wakeword_builtin_model: str
    wakeword_threshold: float
    stt_model: str
    chat_model: str
    tts_model: str
    tts_voice: str
    input_device: str
    output_device: str
    input_sample_rate: int
    output_sample_rate: int
    channels: int
    listen_max_seconds: float
    listen_min_seconds: float
    silence_seconds: float
    silence_threshold: float
    pre_roll_seconds: float
    playback_cooldown_seconds: float
    idle_sleep_timeout_seconds: int
    eyes_enabled: bool
    eyes_fullscreen: bool
    eyes_width: int
    eyes_height: int
    eyes_fps: int
    log_level: str

    @classmethod
    def load(cls, env_path: str | Path | None = None) -> "Config":
        load_dotenv(env_path or BASE_DIR / ".env")
        return cls(
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            robot_name=os.getenv("ROBOT_NAME", "Ameego"),
            wake_word_name=os.getenv("WAKE_WORD_NAME", "Hey Nomi"),
            wakeword_model_path=os.getenv("WAKEWORD_MODEL_PATH") or None,
            wakeword_builtin_model=os.getenv("WAKEWORD_BUILTIN_MODEL", "hey_jarvis"),
            wakeword_threshold=_get_float("WAKEWORD_THRESHOLD", 0.55),
            stt_model=os.getenv("OPENAI_STT_MODEL", "gpt-4o-mini-transcribe"),
            chat_model=os.getenv("OPENAI_CHAT_MODEL", "gpt-4.1-mini"),
            tts_model=os.getenv("OPENAI_TTS_MODEL", "gpt-4o-mini-tts"),
            tts_voice=os.getenv("OPENAI_TTS_VOICE", "alloy"),
            input_device=os.getenv("AUDIO_INPUT_DEVICE", "plughw:2,0"),
            output_device=os.getenv("AUDIO_OUTPUT_DEVICE", "plughw:1,0"),
            input_sample_rate=_get_int("AUDIO_SAMPLE_RATE", 16000),
            output_sample_rate=_get_int("AUDIO_OUTPUT_SAMPLE_RATE", 24000),
            channels=_get_int("AUDIO_CHANNELS", 1),
            listen_max_seconds=_get_float("LISTEN_MAX_SECONDS", 12.0),
            listen_min_seconds=_get_float("LISTEN_MIN_SECONDS", 1.0),
            silence_seconds=_get_float("SILENCE_SECONDS", 1.1),
            silence_threshold=_get_float("SILENCE_THRESHOLD", 0.012),
            pre_roll_seconds=_get_float("PRE_ROLL_SECONDS", 0.35),
            playback_cooldown_seconds=_get_float("PLAYBACK_COOLDOWN_SECONDS", 1.0),
            idle_sleep_timeout_seconds=_get_int("IDLE_SLEEP_TIMEOUT_SECONDS", 180),
            eyes_enabled=_get_bool("EYES_ENABLED", True),
            eyes_fullscreen=_get_bool("EYES_FULLSCREEN", True),
            eyes_width=_get_int("EYES_WIDTH", 800),
            eyes_height=_get_int("EYES_HEIGHT", 480),
            eyes_fps=_get_int("EYES_FPS", 30),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        )

    def validate(self) -> None:
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY is not set.")
        if self.channels < 1:
            raise ValueError("AUDIO_CHANNELS must be at least 1.")
        if self.listen_min_seconds > self.listen_max_seconds:
            raise ValueError("LISTEN_MIN_SECONDS cannot exceed LISTEN_MAX_SECONDS.")


def configure_logging(level_name: str) -> None:
    level = getattr(logging, level_name.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
