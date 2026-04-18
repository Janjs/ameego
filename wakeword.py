from __future__ import annotations

import logging
from pathlib import Path

import sounddevice as sd
from openwakeword.model import Model

from audio import AudioIO
from config import Config


logger = logging.getLogger(__name__)


class WakeWordDetector:
    def __init__(self, config: Config, audio: AudioIO) -> None:
        self.config = config
        self.audio = audio
        self.label = config.wake_word_name
        self.chunk_size = 1280
        self.sample_rate = 16000
        self.model = self._build_model()

    def _build_model(self) -> Model:
        custom_path = self.config.wakeword_model_path
        if custom_path:
            path = Path(custom_path).expanduser()
            if path.exists():
                logger.info("Loading custom wake word model from %s", path)
                self.label = path.stem
                return Model(wakeword_models=[str(path)])
            logger.warning("Custom wake word model path not found: %s", path)

        logger.info(
            "Using built-in openWakeWord model '%s' as fallback for '%s'",
            self.config.wakeword_builtin_model,
            self.config.wake_word_name,
        )
        self.label = self.config.wakeword_builtin_model
        return Model()

    def wait_for_wake_word(self) -> str:
        logger.info("Waiting for wake word '%s'...", self.label)
        with sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            blocksize=self.chunk_size,
            device=self.config.input_device,
        ) as stream:
            while True:
                chunk = self.audio.capture_wakeword_chunk(stream, self.chunk_size)
                predictions = self.model.predict(chunk)
                score = self._extract_score(predictions)
                if score >= self.config.wakeword_threshold:
                    logger.info("Wake word detected with score %.3f", score)
                    return self.label

    def _extract_score(self, predictions: dict) -> float:
        candidate_keys = []
        if self.config.wakeword_model_path:
            candidate_keys.append(Path(self.config.wakeword_model_path).stem)
        candidate_keys.extend(
            [
                self.config.wakeword_builtin_model,
                self.label,
            ]
        )

        scores: list[float] = []
        for key in candidate_keys:
            if key in predictions:
                scores.append(self._coerce_score(predictions[key]))

        if not scores:
            scores.extend(self._coerce_score(value) for value in predictions.values())
        return max(scores, default=0.0)

    @staticmethod
    def _coerce_score(value: object) -> float:
        if isinstance(value, dict):
            for key in ("score", "confidence", "probability"):
                if key in value:
                    return float(value[key])
            nested = [WakeWordDetector._coerce_score(item) for item in value.values()]
            return max(nested, default=0.0)
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0
