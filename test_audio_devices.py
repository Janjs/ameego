from __future__ import annotations

import argparse
import tempfile

from audio import AudioIO
from config import Config, configure_logging


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect and smoke-test Ameego audio devices")
    parser.add_argument("--record-seconds", type=float, default=0.0, help="Record a sample clip if > 0")
    parser.add_argument("--play-tone", action="store_true", help="Play a short test tone")
    args = parser.parse_args()

    config = Config.load()
    configure_logging(config.log_level)
    audio = AudioIO(config)

    audio.print_devices()
    audio.print_alsa_hints()

    if args.play_tone:
        print("\nPlaying a short tone on the configured output device...")
        audio.play_tone()

    if args.record_seconds > 0:
        print(f"\nRecording {args.record_seconds:.1f} seconds from the configured input device...")
        with tempfile.NamedTemporaryFile(prefix="ameego-audio-test-", suffix=".wav", dir="/tmp", delete=False) as tmp:
            temp_path = tmp.name
        audio.record_fixed_duration(temp_path, args.record_seconds)
        print(f"Saved test recording to {temp_path}")


if __name__ == "__main__":
    main()
