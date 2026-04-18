from __future__ import annotations

import argparse
import itertools
import time

from config import Config, configure_logging
from eyes import EyesRenderer


def main() -> None:
    parser = argparse.ArgumentParser(description="Cycle Ameego eye states")
    parser.add_argument("--windowed", action="store_true", help="Run in a window instead of fullscreen")
    parser.add_argument("--seconds-per-state", type=float, default=3.0)
    args = parser.parse_args()

    config = Config.load()
    configure_logging(config.log_level)
    renderer = EyesRenderer(config=config, enabled=True, windowed=args.windowed)
    renderer.start()

    try:
        for state in itertools.cycle(
            ["idle", "wake_detected", "listening", "thinking", "speaking", "error", "sleeping"]
        ):
            print(f"Showing state: {state}")
            renderer.set_state(state)
            time.sleep(args.seconds_per_state)
    except KeyboardInterrupt:
        pass
    finally:
        renderer.stop()


if __name__ == "__main__":
    main()
