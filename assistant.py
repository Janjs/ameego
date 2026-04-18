from __future__ import annotations

import argparse
import logging
import textwrap

from openai import OpenAI

from config import Config, configure_logging
from llm import LanguageModelService


logger = logging.getLogger(__name__)


class AmeegoAssistant:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.client = OpenAI(api_key=config.openai_api_key)
        self.llm = LanguageModelService(config, self.client)
        self.history: list[dict[str, str]] = []

    def run_terminal(self) -> None:
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
        reply = assistant.ask(args.text)
        print(f"{config.robot_name}: {reply}")
        return

    assistant.run_terminal()


if __name__ == "__main__":
    main()
