"""Claude (Anthropic) LLM implementation."""

import os

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel

from .base import BaseLLM


class ClaudeLLM(BaseLLM):
    """Claude LLM via Anthropic API."""

    def __init__(self, model: str = "claude-sonnet-4-20250514", api_key: str | None = None):
        self._model = model
        self._api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self._api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY not set. "
                "Set it in .env file or pass api_key parameter."
            )

    @property
    def model_name(self) -> str:
        return self._model

    def get_chat_model(self) -> BaseChatModel:
        return ChatAnthropic(model=self._model, anthropic_api_key=self._api_key)
