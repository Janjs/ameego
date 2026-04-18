from __future__ import annotations

import argparse
import logging
import os
import tempfile
import time

from openai import OpenAI

from audio import AudioIO, sleep_with_interrupt
from config import Config, configure_logging
from eyes import BaseEyesRenderer, EyesRenderer
from llm import LanguageModelService
from stt import SpeechToTextService
from tts import TextToSpeechService
from wakeword import WakeWordDetector


logger = logging.getLogger(__name__)


class AmeegoAssistant:
    def __init__(
        self,
        config: Config,
        disable_eyes: bool = False,
        windowed_eyes: bool = False,
        push_to_talk: bool = False,
    ) -> None:
        self.config = config
        self.client = OpenAI(api_key=config.openai_api_key)
        self.audio = AudioIO(config)
        self.stt = SpeechToTextService(config, self.client)
        self.llm = LanguageModelService(config, self.client)
        self.tts = TextToSpeechService(config, self.client)
        self.wakeword: WakeWordDetector | None = None
        self.push_to_talk = push_to_talk
        self.last_activity = time.monotonic()
        self.eyes: BaseEyesRenderer = EyesRenderer(
            config=config,
            enabled=config.eyes_enabled and not disable_eyes,
            windowed=windowed_eyes,
        )

    def run(self) -> None:
        logger.info("Starting %s assistant", self.config.robot_name)
        self.eyes.start()
        self.eyes.set_state("idle")

        try:
            if self.push_to_talk:
                self._run_push_to_talk_loop()
            else:
                self._run_wake_word_loop()
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received, shutting down.")
        finally:
            self.eyes.stop()

    def dry_run(self) -> None:
        logger.info("Running dry-run diagnostics")
        self.eyes.start()
        self.eyes.set_state("thinking")
        self.audio.print_devices()
        self.audio.print_alsa_hints()

        with self._temp_path("ameego-dryrun-input-", ".wav") as record_path:
            logger.info("Recording a short microphone sample")
            self.audio.record_fixed_duration(record_path, seconds=2.5)
            logger.info("Sending dry-run sample to STT")
            transcript = self.stt.transcribe(record_path)
            logger.info("Dry-run STT transcript: %s", transcript)

        with self._temp_path("ameego-dryrun-output-", ".wav") as tts_path:
            message = f"{self.config.robot_name} dry run complete."
            logger.info("Generating a short TTS confirmation")
            self.tts.synthesize_to_file(message, tts_path)
            self.eyes.set_state("speaking")
            duration = self.audio.play_wav(tts_path)
            logger.info("Played %.2f seconds of TTS audio", duration)

        self.eyes.set_state("idle")
        self.eyes.stop()
        logger.info("Dry-run finished successfully")

    def _run_push_to_talk_loop(self) -> None:
        logger.info("Push-to-talk mode enabled. Press Enter to ask a question, or type q then Enter to quit.")
        while True:
            self._update_idle_state()
            command = input("> ").strip().lower()
            if command in {"q", "quit", "exit"}:
                logger.info("Exiting push-to-talk loop.")
                return
            self.eyes.set_state("listening")
            self._handle_interaction()

    def _run_wake_word_loop(self) -> None:
        if self.wakeword is None:
            try:
                self.wakeword = WakeWordDetector(self.config, self.audio)
            except RuntimeError:
                logger.exception("Wake-word mode is unavailable")
                self.eyes.set_state("error")
                sleep_with_interrupt(1.0)
                raise
        while True:
            self._update_idle_state()
            detected = self.wakeword.wait_for_wake_word()
            logger.info("Wake word detected: %s", detected)
            self.last_activity = time.monotonic()
            self.eyes.set_state("wake_detected")
            sleep_with_interrupt(0.3)
            self.eyes.set_state("listening")
            self._handle_interaction()

    def _handle_interaction(self) -> None:
        try:
            with self._temp_path("ameego-input-", ".wav") as input_path:
                self.last_activity = time.monotonic()
                self.audio.record_until_silence(input_path)
                self.eyes.set_state("thinking")
                transcript = self.stt.transcribe(input_path)
                reply = self.llm.respond(transcript)

            with self._temp_path("ameego-output-", ".wav") as output_path:
                self.tts.synthesize_to_file(reply, output_path)
                self.eyes.set_state("speaking")
                duration = self.audio.play_wav(output_path)
                self.last_activity = time.monotonic()
                logger.info("Playback duration %.2f seconds", duration)

            self.eyes.set_state("idle")
            sleep_with_interrupt(self.config.playback_cooldown_seconds)
        except KeyboardInterrupt:
            raise
        except Exception:
            logger.exception("Interaction failed")
            self.eyes.set_state("error")
            sleep_with_interrupt(1.0)
            self.eyes.set_state("idle")

    def _update_idle_state(self) -> None:
        inactive_seconds = time.monotonic() - self.last_activity
        if inactive_seconds >= self.config.idle_sleep_timeout_seconds:
            self.eyes.set_state("sleeping")
        else:
            self.eyes.set_state("idle")

    @staticmethod
    def _temp_path(prefix: str, suffix: str):
        class TempPathContext:
            def __enter__(self_inner) -> str:
                temp = tempfile.NamedTemporaryFile(prefix=prefix, suffix=suffix, delete=False, dir="/tmp")
                temp.close()
                self_inner.path = temp.name
                return self_inner.path

            def __exit__(self_inner, exc_type, exc, tb) -> None:
                try:
                    if self_inner.path and os.path.exists(self_inner.path):
                        os.unlink(self_inner.path)
                except OSError:
                    logger.warning("Failed to remove temporary file %s", self_inner.path)

        return TempPathContext()


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ameego Raspberry Pi voice assistant")
    parser.add_argument("--disable-eyes", action="store_true", help="Disable the animated eyes renderer")
    parser.add_argument("--windowed-eyes", action="store_true", help="Run eyes in a window instead of fullscreen")
    parser.add_argument("--dry-run", action="store_true", help="Run diagnostics without the wake-word loop")
    parser.add_argument("--push-to-talk", action="store_true", help="Use Enter-to-talk instead of wake-word detection")
    parser.add_argument("--list-devices", action="store_true", help="Print audio devices and exit")
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    config = Config.load()
    configure_logging(config.log_level)

    if args.list_devices:
        AudioIO(config).print_devices()
        AudioIO(config).print_alsa_hints()
        return

    if args.disable_eyes:
        logger.info("Eyes renderer disabled by CLI flag.")
    config.validate()

    assistant = AmeegoAssistant(
        config=config,
        disable_eyes=args.disable_eyes,
        windowed_eyes=args.windowed_eyes,
        push_to_talk=args.push_to_talk,
    )

    if args.dry_run:
        assistant.dry_run()
        return

    assistant.run()


if __name__ == "__main__":
    main()
