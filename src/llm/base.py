"""LLM abstract base class."""

from abc import ABC, abstractmethod

from langchain_core.language_models import BaseChatModel


class BaseLLM(ABC):
    """Abstract base class for LLM providers."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        ...

    @abstractmethod
    def get_chat_model(self) -> BaseChatModel:
        ...
