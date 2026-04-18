from __future__ import annotations

import argparse
import logging
import os
import queue
import textwrap
import threading
import time
from dataclasses import dataclass
from itertools import count

from openai import OpenAI

from config import Config, configure_logging
from llm import LanguageModelService
from tts import TextToSpeechService


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class UIMessage:
    kind: str
    message_id: int
    speaker: str
    text: str


class DesktopMirror:
    def __init__(self, config: Config) -> None:
        self.config = config
        self._queue: queue.Queue[UIMessage] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._failed = False
        self._ids = count(1)

    def start(self) -> None:
        if not self.config.app_ui_enabled:
            return
        os.environ.setdefault("DISPLAY", self.config.app_ui_display)
        if self.config.app_ui_xauthority:
            os.environ.setdefault("XAUTHORITY", self.config.app_ui_xauthority)
        self._thread = threading.Thread(target=self._run, name="ameego-ui", daemon=True)
        self._thread.start()
        self._ready.wait(timeout=3)

    def post(self, speaker: str, text: str, kind: str = "append", message_id: int | None = None) -> int:
        if self._failed:
            return -1
        actual_id = next(self._ids) if message_id is None else message_id
        self._queue.put(UIMessage(kind=kind, message_id=actual_id, speaker=speaker, text=text))
        return actual_id

    def _run(self) -> None:
        try:
            import tkinter as tk

            root = tk.Tk()
            root.title(self.config.robot_name)
            if self.config.app_ui_fullscreen:
                root.attributes("-fullscreen", True)
            else:
                root.geometry(self.config.app_ui_geometry)
            root.configure(bg="#000000")

            transcript = tk.Text(
                root,
                wrap=tk.WORD,
                font=("Helvetica", 24),
                bg="#000000",
                fg="#f2f2f2",
                insertbackground="#f2f2f2",
                relief=tk.FLAT,
                bd=0,
                highlightthickness=0,
                padx=48,
                pady=48,
            )
            transcript.pack(fill=tk.BOTH, expand=True)
            transcript.configure(state=tk.DISABLED)
            rendered: list[UIMessage] = []

            def redraw() -> None:
                transcript.configure(state=tk.NORMAL)
                transcript.delete("1.0", tk.END)
                for item in rendered:
                    transcript.insert(tk.END, f"{item.speaker}> {item.text}\n\n")
                transcript.see(tk.END)
                transcript.configure(state=tk.DISABLED)

            def pump() -> None:
                while True:
                    try:
                        item = self._queue.get_nowait()
                    except queue.Empty:
                        break
                    if item.kind == "replace":
                        for index, existing in enumerate(rendered):
                            if existing.message_id == item.message_id:
                                rendered[index] = item
                                break
                        else:
                            rendered.append(item)
                    else:
                        rendered.append(item)
                    redraw()
                root.after(100, pump)

            root.bind("<Escape>", lambda _event: root.attributes("-fullscreen", False))
            self._ready.set()
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
                thinking_id = self.desktop.post(self.config.robot_name.lower(), "thinking...")
                print(f"{self.config.robot_name.lower()}> thinking...")
                reply = self.ask(prompt)
                self.desktop.post(self.config.robot_name.lower(), reply, kind="replace", message_id=thinking_id)
                self._print_reply(reply)
                self._speak_reply(reply)
        except KeyboardInterrupt:
            print("\nbye")

    def ask(self, prompt: str) -> str:
        clean_prompt = prompt.strip()
        if not clean_prompt:
            raise ValueError("Prompt cannot be empty.")

        self.history.append({"role": "user", "text": clean_prompt})
        reply = self.llm.respond(self.history)
        self.history.append({"role": "assistant", "text": reply})
        return reply

    def _print_reply(self, reply: str) -> None:
        wrapped = textwrap.fill(reply, width=88)
        print(f"{self.config.robot_name.lower()}> {wrapped}")

    def _speak_reply(self, reply: str) -> None:
        try:
            self.tts.speak(reply)
        except Exception:
            logger.exception("TTS playback failed")

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
        thinking_id = assistant.desktop.post(config.robot_name.lower(), "thinking...")
        reply = assistant.ask(args.text)
        assistant.desktop.post(config.robot_name.lower(), reply, kind="replace", message_id=thinking_id)
        print(f"{config.robot_name}: {reply}")
        assistant._speak_reply(reply)
        time.sleep(0.5)
        return

    assistant.run_terminal()


if __name__ == "__main__":
    main()
