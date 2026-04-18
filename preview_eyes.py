from __future__ import annotations

import argparse
import time

from assistant import EMOTION_FRAMES


ON = "██"
OFF = "  "


def render_eye_rows(rows: tuple[str, ...]) -> list[str]:
    return ["".join(ON if cell == "1" else OFF for cell in row) for row in rows]


def render_frame(frame: tuple[tuple[str, ...], tuple[str, ...]]) -> str:
    left, right = frame
    left_lines = render_eye_rows(left)
    right_lines = render_eye_rows(right)
    combined = [f"{l}    {r}" for l, r in zip(left_lines, right_lines)]
    return "\n".join(combined)


def preview_static() -> None:
    for emotion, frames in EMOTION_FRAMES.items():
        print(f"\n== {emotion} ==")
        print(render_frame(frames[0]))


def preview_animated(emotion: str, delay: float) -> None:
    frames = EMOTION_FRAMES[emotion]
    try:
        while True:
            for index, frame in enumerate(frames, start=1):
                print("\033[2J\033[H", end="")
                print(f"{emotion} frame {index}/{len(frames)}\n")
                print(render_frame(frame))
                time.sleep(delay)
    except KeyboardInterrupt:
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Preview Ameego eye frames in the terminal")
    parser.add_argument("--emotion", choices=sorted(EMOTION_FRAMES.keys()))
    parser.add_argument("--animate", action="store_true", help="Loop through all frames for one emotion")
    parser.add_argument("--delay", type=float, default=0.35, help="Delay between animated frames")
    args = parser.parse_args()

    if args.emotion and args.animate:
        preview_animated(args.emotion, args.delay)
        return

    if args.emotion:
        print(f"== {args.emotion} ==")
        for index, frame in enumerate(EMOTION_FRAMES[args.emotion], start=1):
            print(f"\nframe {index}/{len(EMOTION_FRAMES[args.emotion])}")
            print(render_frame(frame))
        return

    preview_static()


if __name__ == "__main__":
    main()
