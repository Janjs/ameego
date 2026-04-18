from __future__ import annotations

import argparse
import logging
import os
import queue
import textwrap
import threading
import time
from dataclasses import dataclass

from openai import OpenAI

from config import Config, configure_logging
from llm import LanguageModelService


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class UIMessage:
    speaker: str
    text: str


class DesktopMirror:
    def __init__(self, config: Config) -> None:
        self.config = config
        self._queue: queue.Queue[UIMessage] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._failed = False

    def start(self) -> None:
        if not self.config.app_ui_enabled:
            return
        if "DISPLAY" not in os.environ:
            logger.info("Desktop mirror disabled because DISPLAY is not set.")
            return
        self._thread = threading.Thread(target=self._run, name="ameego-ui", daemon=True)
        self._thread.start()
        self._ready.wait(timeout=3)

    def post(self, speaker: str, text: str) -> None:
        if self._failed:
            return
        self._queue.put(UIMessage(speaker=speaker, text=text))

    def _run(self) -> None:
        try:
            import tkinter as tk
            from tkinter import scrolledtext

            root = tk.Tk()
            root.title(f"{self.config.robot_name} Console")
            if self.config.app_ui_fullscreen:
                root.attributes("-fullscreen", True)
            else:
                root.geometry(self.config.app_ui_geometry)
            root.configure(bg="#101418")

            title = tk.Label(
                root,
                text=self.config.robot_name,
                font=("Helvetica", 28, "bold"),
                bg="#101418",
                fg="#dff7ea",
                padx=20,
                pady=20,
            )
            title.pack(anchor="w")

            transcript = scrolledtext.ScrolledText(
                root,
                wrap=tk.WORD,
                font=("Courier New", 18),
                bg="#172026",
                fg="#e8fff4",
                insertbackground="#e8fff4",
                relief=tk.FLAT,
                padx=20,
                pady=20,
            )
            transcript.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
            transcript.insert(tk.END, f"{self.config.robot_name} desktop mirror ready.\n\n")
            transcript.configure(state=tk.DISABLED)

            def pump() -> None:
                while True:
                    try:
                        item = self._queue.get_nowait()
                    except queue.Empty:
                        break
                    transcript.configure(state=tk.NORMAL)
                    transcript.insert(tk.END, f"{item.speaker}> {item.text}\n\n")
                    transcript.see(tk.END)
                    transcript.configure(state=tk.DISABLED)
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
        self.history: list[dict[str, str]] = []
        self.desktop = DesktopMirror(config)

    def run_terminal(self) -> None:
        self.desktop.start()
        self.desktop.post(self.config.robot_name.lower(), "Terminal chat ready.")
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
                    self.desktop.post("system", "Conversation cleared.")
                    print("conversation cleared")
                    continue

                self.desktop.post("you", prompt)
                reply = self.ask(prompt)
                self._print_reply(reply)
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
        self.desktop.post(self.config.robot_name.lower(), reply)
        wrapped = textwrap.fill(reply, width=88)
        print(f"{self.config.robot_name.lower()}> {wrapped}")

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
        reply = assistant.ask(args.text)
        assistant.desktop.post(config.robot_name.lower(), reply)
        print(f"{config.robot_name}: {reply}")
        time.sleep(0.3)
        return

    assistant.run_terminal()


if __name__ == "__main__":
    main()
