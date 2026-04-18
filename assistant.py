from __future__ import annotations

import argparse
import logging
import math
import os
import queue
import random
import textwrap
import threading
import time
from dataclasses import dataclass
from itertools import count

from openai import OpenAI

from config import Config, configure_logging
from llm import AssistantReply, LanguageModelService
from tts import TextToSpeechService


logger = logging.getLogger(__name__)

EYE_COLORS = {
    "bg": "#05060b",
    "panel": "#10131d",
    "pixel_off": "#05060b",
    "pixel_on": "#33e7f0",
    "text": "#f2f6fb",
}

EMOTION_FRAMES: dict[str, list[tuple[tuple[str, ...], tuple[str, ...]]]] = {
    "neutral": [(("01110", "11111", "11111", "11111", "11111", "11111", "01110"),) * 2],
    "happy": [(("01110", "11111", "11111", "11111", "11111", "11011", "10001"),) * 2],
    "curious": [
        (
            ("00110", "01111", "11111", "11111", "11110", "01100", "00100"),
            ("01110", "11111", "11111", "11111", "11111", "11111", "01110"),
        )
    ],
    "sleepy": [(("00000", "00000", "11111", "11111", "01110", "00000", "00000"),) * 2],
    "surprised": [
        (
            ("01110", "11111", "11111", "11111", "11111", "11111", "11111"),
            ("01110", "11111", "11111", "11111", "11111", "11111", "11111"),
        )
    ],
    "sad": [(("00110", "01111", "11111", "11111", "11111", "11111", "01110"),) * 2],
    "angry": [(("01100", "11110", "11111", "11111", "11111", "11111", "01110"), ("00110", "01111", "11111", "11111", "11111", "11111", "01110"))],
    "loading": [
        (("00000", "00000", "11111", "11111", "00000", "00000", "00000"),) * 2,
        (("00000", "01110", "11111", "11111", "01110", "00000", "00000"),) * 2,
        (("00100", "01110", "11111", "11111", "11111", "01110", "00100"),) * 2,
        (("00000", "00000", "01110", "11111", "01110", "00000", "00000"),) * 2,
    ],
    "blink": [(("00000", "00000", "00000", "11111", "00000", "00000", "00000"),) * 2],
    "speaking": [
        (("01110", "11111", "11111", "11111", "11111", "11111", "01110"),) * 2,
        (
            ("00100", "01110", "11111", "11111", "11111", "01110", "00100"),
            ("01110", "11111", "11111", "11111", "11111", "11111", "01110"),
        ),
        (
            ("01110", "11111", "11111", "11111", "11111", "11111", "01110"),
            ("00100", "01110", "11111", "11111", "11111", "01110", "00100"),
        ),
    ],
}


@dataclass(slots=True)
class UIMessage:
    kind: str
    message_id: int
    speaker: str
    text: str
    emotion: str | None = None


class DesktopMirror:
    def __init__(self, config: Config) -> None:
        self.config = config
        self._queue: queue.Queue[UIMessage] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._failed = False
        self._ids = count(1)
        self._idle_reset_at = 0.0

    def start(self) -> None:
        if not self.config.app_ui_enabled:
            return
        os.environ.setdefault("DISPLAY", self.config.app_ui_display)
        if self.config.app_ui_xauthority:
            os.environ.setdefault("XAUTHORITY", self.config.app_ui_xauthority)
        self._thread = threading.Thread(target=self._run, name="ameego-ui", daemon=True)
        self._thread.start()
        self._ready.wait(timeout=3)

    def post(
        self,
        speaker: str,
        text: str,
        kind: str = "append",
        message_id: int | None = None,
        emotion: str | None = None,
    ) -> int:
        if self._failed:
            return -1
        actual_id = next(self._ids) if message_id is None else message_id
        self._queue.put(UIMessage(kind=kind, message_id=actual_id, speaker=speaker, text=text, emotion=emotion))
        return actual_id

    def set_emotion(self, emotion: str) -> None:
        self.post("", "", kind="state", emotion=emotion)

    def schedule_idle(self) -> None:
        self._idle_reset_at = time.monotonic() + self.config.app_ui_idle_after_seconds

    def _run(self) -> None:
        try:
            import tkinter as tk

            root = tk.Tk()
            root.title(self.config.robot_name)
            if self.config.app_ui_fullscreen:
                root.attributes("-fullscreen", True)
            else:
                root.geometry(self.config.app_ui_geometry)
            root.configure(bg=EYE_COLORS["bg"])

            frame = tk.Frame(root, bg=EYE_COLORS["bg"])
            frame.pack(fill=tk.BOTH, expand=True)

            eyes = tk.Canvas(
                frame,
                bg=EYE_COLORS["bg"],
                height=260,
                relief=tk.FLAT,
                bd=0,
                highlightthickness=0,
            )
            eyes.pack(fill=tk.X, padx=48, pady=(36, 12))

            transcript = tk.Text(
                frame,
                wrap=tk.WORD,
                font=("Helvetica", 24),
                bg=EYE_COLORS["bg"],
                fg=EYE_COLORS["text"],
                insertbackground=EYE_COLORS["text"],
                relief=tk.FLAT,
                bd=0,
                highlightthickness=0,
                padx=48,
                pady=24,
            )
            transcript.pack(fill=tk.BOTH, expand=True)
            transcript.configure(state=tk.DISABLED)
            rendered: list[UIMessage] = []
            current_emotion = "neutral"
            animation_index = 0
            next_blink_at = time.monotonic() + random.uniform(4.5, 8.5)
            blink_end_at = 0.0

            def draw_eyes(emotion: str) -> None:
                nonlocal animation_index
                eyes.delete("all")
                frames = EMOTION_FRAMES.get(emotion, EMOTION_FRAMES["neutral"])
                left_rows, right_rows = frames[animation_index % len(frames)]
                canvas_width = max(eyes.winfo_width(), 320)
                canvas_height = max(eyes.winfo_height(), 180)
                rows = len(left_rows)
                cols = len(left_rows[0])
                eye_gap = canvas_width * 0.08
                pixel = min(
                    (canvas_width * 0.72 - eye_gap) / (cols * 2),
                    canvas_height * 0.72 / rows,
                )
                pixel = max(10, int(pixel))
                gap = max(2, int(pixel * 0.18))
                eye_width = cols * pixel + (cols - 1) * gap
                eye_height = rows * pixel + (rows - 1) * gap
                total_width = eye_width * 2 + eye_gap
                start_x = (canvas_width - total_width) / 2
                start_y = max(16, (canvas_height - eye_height) / 2)

                def draw_eye(rows_data: tuple[str, ...], x_offset: float) -> None:
                    for row_index, row in enumerate(rows_data):
                        for col_index, value in enumerate(row):
                            x1 = x_offset + col_index * (pixel + gap)
                            y1 = start_y + row_index * (pixel + gap)
                            x2 = x1 + pixel
                            y2 = y1 + pixel
                            if value == "1":
                                eyes.create_rectangle(
                                    x1,
                                    y1,
                                    x2,
                                    y2,
                                    fill=EYE_COLORS["pixel_on"],
                                    outline="",
                                    width=0,
                                )

                draw_eye(left_rows, start_x)
                draw_eye(right_rows, start_x + eye_width + eye_gap)
                animation_index += 1

            def redraw() -> None:
                transcript.configure(state=tk.NORMAL)
                transcript.delete("1.0", tk.END)
                for item in rendered:
                    transcript.insert(tk.END, f"{item.speaker}> {item.text}\n\n")
                transcript.see(tk.END)
                transcript.configure(state=tk.DISABLED)

            def animate() -> None:
                nonlocal current_emotion, next_blink_at, blink_end_at, animation_index
                now = time.monotonic()
                draw_emotion = current_emotion

                if self._idle_reset_at and now >= self._idle_reset_at:
                    current_emotion = "neutral"
                    self._idle_reset_at = 0.0
                    animation_index = 0

                if current_emotion == "neutral":
                    if now >= next_blink_at:
                        blink_end_at = now + 0.18
                        next_blink_at = now + random.uniform(4.5, 9.5)
                    if now < blink_end_at:
                        draw_emotion = "blink"

                draw_eyes(draw_emotion)
                delay = 220 if current_emotion in {"loading", "speaking"} else 700
                root.after(delay, animate)

            def pump() -> None:
                nonlocal current_emotion, animation_index
                while True:
                    try:
                        item = self._queue.get_nowait()
                    except queue.Empty:
                        break
                    if item.kind == "state":
                        if item.emotion:
                            current_emotion = item.emotion
                            animation_index = 0
                        continue
                    if item.kind == "replace":
                        for index, existing in enumerate(rendered):
                            if existing.message_id == item.message_id:
                                rendered[index] = item
                                break
                        else:
                            rendered.append(item)
                    else:
                        rendered.append(item)
                    if item.emotion:
                        current_emotion = item.emotion
                        animation_index = 0
                        if item.emotion not in {"loading", "speaking"}:
                            self.schedule_idle()
                    redraw()
                root.after(100, pump)

            root.bind("<Escape>", lambda _event: root.attributes("-fullscreen", False))
            self._ready.set()
            draw_eyes(current_emotion)
            animate()
            pump()
            root.mainloop()
        except Exception:
            self._failed = True
            self._ready.set()
            logger.exception("Desktop mirror failed to start")


class AmeegoAssistant:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.client = OpenAI(api_key=config.openai_api_key)
        self.llm = LanguageModelService(config, self.client)
        self.tts = TextToSpeechService(config, self.client)
        self.history: list[dict[str, str]] = []
        self.desktop = DesktopMirror(config)

    def run_terminal(self) -> None:
        self.desktop.start()
        print(self._header())
        try:
            while True:
                prompt = input("you> ").strip()
                if not prompt:
                    continue
                if prompt.lower() in {"/quit", "quit", "exit"}:
                    print("bye")
                    return
                if prompt.lower() == "/help":
                    print(self._help_text())
                    continue
                if prompt.lower() == "/clear":
                    self.history.clear()
                    print("conversation cleared")
                    continue

                self.desktop.post("you", prompt)
                thinking_id = self.desktop.post(
                    self.config.robot_name.lower(),
                    "thinking...",
                    emotion="loading",
                )
                print(f"{self.config.robot_name.lower()}> thinking...")
                reply = self.ask(prompt)
                self.desktop.post(
                    self.config.robot_name.lower(),
                    reply.text,
                    kind="replace",
                    message_id=thinking_id,
                    emotion=reply.emotion,
                )
                self._print_reply(reply.text)
                self._speak_reply(reply.text, reply.emotion)
        except KeyboardInterrupt:
            print("\nbye")

    def ask(self, prompt: str) -> AssistantReply:
        clean_prompt = prompt.strip()
        if not clean_prompt:
            raise ValueError("Prompt cannot be empty.")

        self.history.append({"role": "user", "text": clean_prompt})
        reply = self.llm.respond(self.history)
        self.history.append({"role": "assistant", "text": reply.text})
        return reply

    def _print_reply(self, reply: str) -> None:
        wrapped = textwrap.fill(reply, width=88)
        print(f"{self.config.robot_name.lower()}> {wrapped}")

    def _speak_reply(self, reply: str, emotion: str) -> None:
        try:
            self.desktop.set_emotion("speaking" if emotion == "neutral" else emotion)
            self.tts.speak(reply)
        except Exception:
            logger.exception("TTS playback failed")
        finally:
            self.desktop.schedule_idle()

    def _header(self) -> str:
        return "\n".join(
            [
                f"{self.config.robot_name} terminal chat",
                "Type a message and press Enter.",
                "Commands: /help, /clear, /quit",
                "",
            ]
        )

    @staticmethod
    def _help_text() -> str:
        return "\n".join(
            [
                "Commands:",
                "  /help   Show this help message",
                "  /clear  Clear the current conversation history",
                "  /quit   Exit the app",
            ]
        )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ameego SSH terminal assistant")
    parser.add_argument("--text", help="Send a single prompt and print the reply")
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    config = Config.load()
    configure_logging(config.log_level)
    config.validate()

    assistant = AmeegoAssistant(config=config)

    if args.text:
        assistant.desktop.start()
        assistant.desktop.post("you", args.text)
        thinking_id = assistant.desktop.post(config.robot_name.lower(), "thinking...", emotion="loading")
        reply = assistant.ask(args.text)
        assistant.desktop.post(
            config.robot_name.lower(),
            reply.text,
            kind="replace",
            message_id=thinking_id,
            emotion=reply.emotion,
        )
        print(f"{config.robot_name}: {reply.text}")
        assistant._speak_reply(reply.text, reply.emotion)
        time.sleep(0.5)
        return

    assistant.run_terminal()


if __name__ == "__main__":
    main()
