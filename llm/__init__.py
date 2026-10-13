"""LLM provider package factory for Prince AI Team."""

from config import LLM_PROVIDER
from llm.base import LLMProvider
from llm.ollama_provider import OllamaProvider
from llm.anthropic_provider import AnthropicProvider
from llm.mock_provider import MockProvider


def get_llm_provider() -> LLMProvider:
    """Returns configured LLM provider instance."""
    if LLM_PROVIDER == "anthropic":
        return AnthropicProvider()
    elif LLM_PROVIDER == "mock":
        return MockProvider()
    return OllamaProvider()


default_provider = get_llm_provider()
