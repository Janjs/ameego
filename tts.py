from __future__ import annotations

import logging
from pathlib import Path

from openai import OpenAI

from config import Config


logger = logging.getLogger(__name__)


class TextToSpeechService:
    def __init__(self, config: Config, client: OpenAI) -> None:
        self.config = config
        self.client = client

    def synthesize_to_file(self, text: str, output_path: str | Path) -> Path:
        output_path = Path(output_path)
        logger.info("Submitting %d characters to TTS", len(text))
        response = self.client.audio.speech.create(
            model=self.config.tts_model,
            voice=self.config.tts_voice,
            input=text,
            response_format="wav",
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        response.write_to_file(str(output_path))
        logger.info("Saved TTS audio to %s", output_path)
        return output_path
