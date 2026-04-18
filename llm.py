from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from openai import OpenAI

from config import Config


logger = logging.getLogger(__name__)

EMOTIONS = ("neutral", "happy", "curious", "sleepy", "surprised", "sad")

SYSTEM_PROMPT = """You are Ameego, a warm, friendly companion the user can talk to.
You are not a Raspberry Pi help bot unless the user explicitly asks for technical help.
Respond like a thoughtful, natural conversational partner.
Keep replies as short as possible by default, especially because replies may be spoken aloud.
Prefer 1 short sentence when that is enough.
Only give longer answers when the user clearly asks for more detail.
Avoid long lists unless the user asks for options.
Be kind, calm, and a little playful without being cheesy.
If the user wants advice or support, be encouraging and practical.
If the user asks a technical question, you can still help clearly and directly.
Before each reply, choose the best matching facial emotion for the on-screen avatar."""


@dataclass(slots=True)
class AssistantReply:
    text: str
    emotion: str = "neutral"


class LanguageModelService:
    def __init__(self, config: Config, client: OpenAI) -> None:
        self.config = config
        self.client = client

    def respond(self, conversation: list[dict[str, str]]) -> AssistantReply:
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

        first_response = self.client.responses.create(
            model=self.config.chat_model,
            input=messages,
            tool_choice="required",
            tools=[
                {
                    "type": "function",
                    "name": "set_emotion",
                    "description": "Set the robot eye emotion for the assistant's next reply.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "emotion": {
                                "type": "string",
                                "enum": list(EMOTIONS),
                            }
                        },
                        "required": ["emotion"],
                        "additionalProperties": False,
                    },
                }
            ],
            max_output_tokens=self.config.max_output_tokens,
        )

        emotion, call_id = self._extract_emotion(first_response)
        text = (first_response.output_text or "").strip()

        if call_id:
            follow_up = self.client.responses.create(
                model=self.config.chat_model,
                previous_response_id=first_response.id,
                input=[
                    {
                        "type": "function_call_output",
                        "call_id": call_id,
                        "output": json.dumps({"status": "ok", "emotion": emotion}),
                    }
                ],
                max_output_tokens=self.config.max_output_tokens,
            )
            text = (follow_up.output_text or "").strip()

        if not text:
            raise RuntimeError("Language model returned an empty response.")
        logger.info("Assistant reply (%s): %s", emotion, text)
        return AssistantReply(text=text, emotion=emotion)

    def _extract_emotion(self, response: object) -> tuple[str, str | None]:
        for item in getattr(response, "output", []) or []:
            if getattr(item, "type", None) != "function_call":
                continue
            if getattr(item, "name", "") != "set_emotion":
                continue
            raw_arguments = getattr(item, "arguments", "") or "{}"
            try:
                arguments = json.loads(raw_arguments)
            except json.JSONDecodeError:
                logger.warning("Failed to decode emotion tool arguments: %r", raw_arguments)
                return "neutral", getattr(item, "call_id", None)
            emotion = arguments.get("emotion", "neutral")
            if emotion not in EMOTIONS:
                emotion = "neutral"
            return emotion, getattr(item, "call_id", None)
        return "neutral", None
