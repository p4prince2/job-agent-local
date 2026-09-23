"""LLM provider package factory for Prince AI Team."""

from config import LLM_PROVIDER
from llm.base import LLMProvider
from llm.ollama_provider import OllamaProvider
from llm.anthropic_provider import AnthropicProvider


def get_llm_provider() -> LLMProvider:
    """Returns configured LLM provider instance."""
    if LLM_PROVIDER == "anthropic":
        return AnthropicProvider()
    return OllamaProvider()


default_provider = get_llm_provider()
