from __future__ import annotations

import logging

from openai import OpenAI

from config import Config


logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are Ameego, a calm and helpful home robot assistant.
Speak conversationally and keep spoken replies short unless the user asks for more detail.
Be practical, kind, and concise.
If the user asks for a multi-step task, summarize the answer in a way that sounds natural when spoken aloud.
If you are unsure, say so briefly and offer the most likely helpful next step."""


class LanguageModelService:
    def __init__(self, config: Config, client: OpenAI) -> None:
        self.config = config
        self.client = client

    def respond(self, transcript: str) -> str:
        logger.info("Sending transcript to model %s", self.config.chat_model)
        response = self.client.responses.create(
            model=self.config.chat_model,
            input=[
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": SYSTEM_PROMPT}],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": transcript}],
                },
            ],
            max_output_tokens=180,
        )
        text = (response.output_text or "").strip()
        if not text:
            raise RuntimeError("Language model returned an empty response.")
        logger.info("Assistant reply: %s", text)
        return text
