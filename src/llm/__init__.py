"""LLM abstraction layer with multi-provider support."""

import os

from dotenv import load_dotenv

from .base import BaseLLM
from .claude import ClaudeLLM
from .openai import OpenAILLM
from .zhipu import ZhipuLLM

load_dotenv()

__all__ = ["BaseLLM", "ClaudeLLM", "OpenAILLM", "ZhipuLLM", "get_llm"]


def get_llm(provider: str | None = None, model: str | None = None) -> BaseLLM:
    """Factory function to create LLM instance.

    Args:
        provider: "claude", "openai", or "zhipu". Defaults to DEFAULT_LLM env var.
        model: Model name override. Defaults to provider's default.
    """
    provider = provider or os.getenv("DEFAULT_LLM", "zhipu")

    if provider == "claude":
        return ClaudeLLM(model=model) if model else ClaudeLLM()
    elif provider == "openai":
        return OpenAILLM(model=model) if model else OpenAILLM()
    elif provider == "zhipu":
        return ZhipuLLM(model=model) if model else ZhipuLLM()
    else:
        raise ValueError(f"Unknown LLM provider: {provider}. Use 'claude', 'openai', or 'zhipu'.")
