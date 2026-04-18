from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path

from openai import OpenAI

from config import Config


logger = logging.getLogger(__name__)


class TextToSpeechService:
    def __init__(self, config: Config, client: OpenAI) -> None:
        self.config = config
        self.client = client

    def speak(self, text: str) -> None:
        with tempfile.NamedTemporaryFile(prefix="ameego-tts-", suffix=".wav", dir="/tmp", delete=False) as tmp:
            output_path = Path(tmp.name)

        try:
            logger.info("Submitting %d characters to TTS", len(text))
            response = self.client.audio.speech.create(
                model=self.config.tts_model,
                voice=self.config.tts_voice,
                input=text,
                response_format="wav",
            )
            response.write_to_file(str(output_path))
            self._play_wav(output_path)
        finally:
            try:
                output_path.unlink(missing_ok=True)
            except OSError:
                logger.warning("Failed to remove temporary TTS file %s", output_path)

    def _play_wav(self, wav_path: Path) -> None:
        logger.info("Playing TTS reply through %s", self.config.audio_output_device)
        command = ["aplay", "-D", self.config.audio_output_device, str(wav_path)]
        try:
            subprocess.run(command, check=True, capture_output=True, text=True)
        except FileNotFoundError as exc:
            raise RuntimeError("`aplay` is not installed. Install `alsa-utils` on the Pi.") from exc
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(f"Audio playback failed: {exc.stderr.strip() or exc.stdout.strip()}") from exc
