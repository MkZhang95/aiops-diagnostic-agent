"""OpenAI LLM implementation."""

import os

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from .base import BaseLLM


class OpenAILLM(BaseLLM):
    """OpenAI GPT LLM."""

    def __init__(self, model: str = "gpt-4o", api_key: str | None = None):
        self._model = model
        self._api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self._api_key:
            raise ValueError(
                "OPENAI_API_KEY not set. "
                "Set it in .env file or pass api_key parameter."
            )

    @property
    def model_name(self) -> str:
        return self._model

    def get_chat_model(self) -> BaseChatModel:
        return ChatOpenAI(model=self._model, api_key=self._api_key)
