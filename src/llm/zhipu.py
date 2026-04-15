"""Zhipu AI (智谱) LLM implementation — OpenAI-compatible API."""

import os

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from .base import BaseLLM

ZHIPU_BASE_URL = "https://open.bigmodel.cn/api/paas/v4/"


class ZhipuLLM(BaseLLM):
    """Zhipu AI LLM via OpenAI-compatible API."""

    def __init__(self, model: str = "glm-4.7", api_key: str | None = None):
        self._model = model
        self._api_key = api_key or os.getenv("ZHIPU_API_KEY")
        if not self._api_key:
            raise ValueError(
                "ZHIPU_API_KEY not set. "
                "Set it in .env file or pass api_key parameter."
            )

    @property
    def model_name(self) -> str:
        return self._model

    def get_chat_model(self) -> BaseChatModel:
        return ChatOpenAI(
            model=self._model,
            api_key=self._api_key,
            base_url=ZHIPU_BASE_URL,
        )
