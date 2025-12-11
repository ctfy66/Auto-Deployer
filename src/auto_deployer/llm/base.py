"""Base class and factory for LLM providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..config import LLMConfig


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def generate_response(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        response_format: str = "json",
        timeout: int = 60,
        max_retries: int = 3,
    ) -> Optional[str]:
        """
        Generate a response from the LLM.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            response_format: "json" or "text"
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries on rate limit

        Returns:
            Generated text or None on failure
        """
        pass


def create_llm_provider(config: "LLMConfig") -> BaseLLMProvider:
    """
    Factory function to create the appropriate LLM provider based on config.

    Args:
        config: LLM configuration

    Returns:
        An instance of the appropriate LLM provider

    Raises:
        ValueError: If provider is not supported
    """
    provider = config.provider.lower()

    if provider == "gemini":
        from .gemini import GeminiProvider
        return GeminiProvider(config)
    elif provider == "openai":
        from .openai import OpenAIProvider
        return OpenAIProvider(config)
    elif provider == "anthropic" or provider == "claude":
        from .anthropic import AnthropicProvider
        return AnthropicProvider(config)
    elif provider == "deepseek":
        from .deepseek import DeepSeekProvider
        return DeepSeekProvider(config)
    elif provider == "openrouter":
        from .openrouter import OpenRouterProvider
        return OpenRouterProvider(config)
    elif provider == "openai-compatible" or provider == "custom":
        from .openai_compatible import OpenAICompatibleProvider
        return OpenAICompatibleProvider(config)
    else:
        raise ValueError(
            f"Unsupported LLM provider: {provider}. "
            f"Supported providers: gemini, openai, anthropic, deepseek, openrouter, openai-compatible"
        )
