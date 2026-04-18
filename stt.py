from __future__ import annotations

import logging
from pathlib import Path

from openai import OpenAI

from config import Config


logger = logging.getLogger(__name__)


class SpeechToTextService:
    def __init__(self, config: Config, client: OpenAI) -> None:
        self.config = config
        self.client = client

    def transcribe(self, audio_path: str | Path) -> str:
        audio_path = Path(audio_path)
        logger.info("Submitting %s for transcription", audio_path)
        with audio_path.open("rb") as audio_file:
            response = self.client.audio.transcriptions.create(
                model=self.config.stt_model,
                file=audio_file,
            )
        text = (response.text or "").strip()
        if not text:
            raise RuntimeError("Transcription returned no text.")
        logger.info("Transcription: %s", text)
        return text
