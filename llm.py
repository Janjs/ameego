from __future__ import annotations

import logging

from openai import OpenAI

from config import Config


logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are Ameego, a calm and helpful Raspberry Pi terminal assistant.
Respond clearly and conversationally.
Keep answers compact by default, but go deeper when asked.
Prefer practical, actionable help.
When useful, format commands or code in fenced code blocks."""


class LanguageModelService:
    def __init__(self, config: Config, client: OpenAI) -> None:
        self.config = config
        self.client = client

    def respond(self, conversation: list[dict[str, str]]) -> str:
        logger.info("Sending %d conversation messages to model %s", len(conversation), self.config.chat_model)
        messages = [
            {
                "role": "system",
                "content": [{"type": "input_text", "text": SYSTEM_PROMPT}],
            }
        ]
        for item in conversation:
            messages.append(
                {
                    "role": item["role"],
                    "content": [{"type": "input_text", "text": item["text"]}],
                }
            )

        response = self.client.responses.create(
            model=self.config.chat_model,
            input=messages,
            max_output_tokens=self.config.max_output_tokens,
        )
        text = (response.output_text or "").strip()
        if not text:
            raise RuntimeError("Language model returned an empty response.")
        logger.info("Assistant reply: %s", text)
        return text
