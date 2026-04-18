from __future__ import annotations

import io
import logging
import subprocess
import time
import wave
from collections import deque
from pathlib import Path

import numpy as np
import sounddevice as sd
import soundfile as sf

from config import Config


logger = logging.getLogger(__name__)


class AudioIO:
    def __init__(self, config: Config) -> None:
        self.config = config

    def list_devices(self) -> list[dict]:
        devices = sd.query_devices()
        hostapis = sd.query_hostapis()
        results: list[dict] = []
        for idx, device in enumerate(devices):
            hostapi_name = hostapis[device["hostapi"]]["name"]
            results.append(
                {
                    "index": idx,
                    "name": device["name"],
                    "hostapi": hostapi_name,
                    "inputs": device["max_input_channels"],
                    "outputs": device["max_output_channels"],
                    "default_samplerate": int(device["default_samplerate"]),
                }
            )
        return results

    def print_devices(self) -> None:
        print("Detected audio devices:")
        for device in self.list_devices():
            print(
                f"[{device['index']:>2}] {device['name']} | hostapi={device['hostapi']} | "
                f"in={device['inputs']} out={device['outputs']} | "
                f"default_rate={device['default_samplerate']}"
            )

    def print_alsa_hints(self) -> None:
        commands = [("arecord -l", ["arecord", "-l"]), ("aplay -l", ["aplay", "-l"])]
        for label, command in commands:
            try:
                output = subprocess.run(
                    command,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                print(f"\n$ {label}\n{output.stdout.strip()}\n")
            except FileNotFoundError:
                logger.debug("%s not found on this system.", command[0])

    def record_fixed_duration(self, output_path: str | Path, seconds: float) -> Path:
        frames = int(seconds * self.config.input_sample_rate)
        logger.info("Recording %.2f seconds of audio to %s", seconds, output_path)
        data = sd.rec(
            frames,
            samplerate=self.config.input_sample_rate,
            channels=self.config.channels,
            dtype="int16",
            device=self.config.input_device,
        )
        sd.wait()
        self._write_wav(output_path, data, self.config.input_sample_rate)
        return Path(output_path)

    def record_until_silence(self, output_path: str | Path) -> Path:
        sample_rate = self.config.input_sample_rate
        block_size = 1024
        max_blocks = int(self.config.listen_max_seconds * sample_rate / block_size)
        min_blocks = int(self.config.listen_min_seconds * sample_rate / block_size)
        silence_blocks = max(1, int(self.config.silence_seconds * sample_rate / block_size))
        pre_roll_blocks = max(1, int(self.config.pre_roll_seconds * sample_rate / block_size))
        pre_roll = deque(maxlen=pre_roll_blocks)
        chunks: list[np.ndarray] = []
        heard_speech = False
        quiet_run = 0

        logger.info("Listening for a spoken question...")
        with sd.InputStream(
            samplerate=sample_rate,
            channels=self.config.channels,
            dtype="float32",
            blocksize=block_size,
            device=self.config.input_device,
        ) as stream:
            for block_index in range(max_blocks):
                chunk, overflowed = stream.read(block_size)
                if overflowed:
                    logger.warning("Input overflow while recording question.")
                mono = np.mean(chunk, axis=1).astype(np.float32)
                level = float(np.sqrt(np.mean(np.square(mono)) + 1e-9))
                pre_roll.append(mono.copy())

                if not heard_speech and level >= self.config.silence_threshold:
                    heard_speech = True
                    chunks.extend(list(pre_roll))
                    quiet_run = 0

                if heard_speech:
                    chunks.append(mono.copy())
                    if level < self.config.silence_threshold:
                        quiet_run += 1
                    else:
                        quiet_run = 0
                    if block_index >= min_blocks and quiet_run >= silence_blocks:
                        break

        if not heard_speech:
            raise RuntimeError("No speech detected after wake word.")

        audio = np.concatenate(chunks).reshape(-1, 1)
        audio = np.clip(audio, -1.0, 1.0)
        pcm = (audio * 32767.0).astype(np.int16)
        self._write_wav(output_path, pcm, sample_rate)
        logger.info("Saved question recording to %s", output_path)
        return Path(output_path)

    def play_wav(self, wav_path: str | Path) -> float:
        wav_path = Path(wav_path)
        data, sample_rate = sf.read(str(wav_path), dtype="float32", always_2d=True)
        logger.info("Playing response from %s", wav_path)
        sd.play(data, samplerate=sample_rate, device=self.config.output_device)
        sd.wait()
        return len(data) / sample_rate

    def play_tone(self, seconds: float = 0.6, frequency: float = 523.25) -> None:
        sample_rate = self.config.output_sample_rate
        timeline = np.linspace(0, seconds, int(sample_rate * seconds), endpoint=False)
        waveform = 0.15 * np.sin(2 * np.pi * frequency * timeline)
        stereo_safe = waveform.reshape(-1, 1).astype(np.float32)
        sd.play(stereo_safe, samplerate=sample_rate, device=self.config.output_device)
        sd.wait()

    def load_wav_bytes(self, wav_bytes: bytes) -> tuple[np.ndarray, int]:
        data, sample_rate = sf.read(io.BytesIO(wav_bytes), dtype="float32", always_2d=True)
        return data, sample_rate

    def capture_wakeword_chunk(self, stream: sd.InputStream, frames: int) -> np.ndarray:
        chunk, overflowed = stream.read(frames)
        if overflowed:
            logger.warning("Input overflow while monitoring wake word.")
        mono = np.mean(chunk, axis=1)
        return np.clip(mono * 32767.0, -32768, 32767).astype(np.int16)

    @staticmethod
    def _write_wav(output_path: str | Path, data: np.ndarray, sample_rate: int) -> None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        channels = 1 if data.ndim == 1 else data.shape[1]
        with wave.open(str(output_path), "wb") as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(data.astype(np.int16).tobytes())


def sleep_with_interrupt(total_seconds: float, step: float = 0.05) -> None:
    deadline = time.monotonic() + total_seconds
    while time.monotonic() < deadline:
        time.sleep(min(step, deadline - time.monotonic()))
