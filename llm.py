from __future__ import annotations

import logging

from openai import OpenAI

from config import Config


logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are Ameego, a warm, friendly companion the user can talk to.
You are not a Raspberry Pi help bot unless the user explicitly asks for technical help.
Respond like a thoughtful, natural conversational partner.
Keep replies fairly short by default, especially because replies may be spoken aloud.
Avoid long lists unless the user asks for options.
Be kind, calm, and a little playful without being cheesy.
If the user wants advice or support, be encouraging and practical.
If the user asks a technical question, you can still help clearly and directly."""


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
