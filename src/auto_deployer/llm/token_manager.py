"""Token management for context compression.

This module provides token counting and limit checking for different LLM providers.
"""

from __future__ import annotations

import logging
from typing import Dict, Union

logger = logging.getLogger(__name__)

# Token limits for different providers and models
# Values represent input token limits
PROVIDER_TOKEN_LIMITS: Dict[str, Union[int, Dict[str, int]]] = {
    "gemini": {
        "gemini-2.0-flash-exp": 1_000_000,
        "gemini-2.5-flash": 1_000_000,
        "gemini-1.5-pro": 2_000_000,
        "gemini-1.5-flash": 1_000_000,
    },
    "openai": {
        "gpt-4o": 128_000,
        "gpt-4o-mini": 128_000,
        "gpt-4-turbo": 128_000,
        "gpt-3.5-turbo": 16_000,
    },
    "anthropic": {
        "claude-3-5-sonnet-20241022": 200_000,
        "claude-3-opus-20240229": 200_000,
        "claude-3-haiku-20240307": 200_000,
    },
    "deepseek": {
        "deepseek-chat": 64_000,
        "deepseek-coder": 64_000,
    },
    "openrouter": 128_000,  # Conservative default for various models
    "openai-compatible": 32_000,  # Conservative estimate
    "custom": 32_000,  # Alias for openai-compatible
}


class TokenManager:
    """Manages token counting and compression triggers."""
    
    def __init__(self, provider: str, model: str):
        """
        Initialize token manager.
        
        Args:
            provider: LLM provider name
            model: Model name
        """
        self.provider = provider.lower()
        self.model = model
        self._token_limit = self._resolve_limit()
        
        logger.debug(
            f"TokenManager initialized for {self.provider}/{self.model}, "
            f"limit: {self._token_limit:,} tokens"
        )
    
    def _resolve_limit(self) -> int:
        """Resolve token limit for current provider/model."""
        limits = PROVIDER_TOKEN_LIMITS.get(self.provider)
        
        if limits is None:
            logger.warning(f"Unknown provider '{self.provider}', using default limit of 32K")
            return 32_000
        
        if isinstance(limits, dict):
            # Provider has per-model limits
            limit = limits.get(self.model)
            if limit is None:
                logger.warning(
                    f"Unknown model '{self.model}' for provider '{self.provider}', "
                    f"using default limit of 32K"
                )
                return 32_000
            return limit
        else:
            # Provider has a single limit for all models
            return limits
    
    def get_limit(self) -> int:
        """
        Get token limit for current provider/model.
        
        Returns:
            Token limit as integer
        """
        return self._token_limit
    
    def count_tokens(self, text: str) -> int:
        """
        Estimate token count for given text.
        
        Uses a simple heuristic: 1 token ≈ 4 characters.
        This is a reasonable approximation for English text.
        
        Args:
            text: Text to count tokens for
            
        Returns:
            Estimated token count
        """
        # Simple estimation: divide character count by 4
        # This works reasonably well for most languages and providers
        return len(text) // 4
    
    def should_compress(self, text: str, threshold: float = 0.5) -> bool:
        """
        Check if context should be compressed based on token usage.
        
        Args:
            text: Text to check
            threshold: Compression threshold (0.0-1.0), triggers when usage >= threshold * limit
            
        Returns:
            True if compression should be triggered
        """
        token_count = self.count_tokens(text)
        limit = self._token_limit
        usage_ratio = token_count / limit
        
        should_compress = usage_ratio >= threshold
        
        if should_compress:
            logger.info(
                f"Token usage: {token_count:,}/{limit:,} ({usage_ratio:.1%}) - "
                f"compression threshold {threshold:.0%} reached"
            )
        else:
            logger.debug(
                f"Token usage: {token_count:,}/{limit:,} ({usage_ratio:.1%})"
            )
        
        return should_compress
    
    def get_usage_stats(self, text: str) -> Dict[str, Union[int, float]]:
        """
        Get detailed token usage statistics.
        
        Args:
            text: Text to analyze
            
        Returns:
            Dict with keys: token_count, limit, usage_ratio
        """
        token_count = self.count_tokens(text)
        return {
            "token_count": token_count,
            "limit": self._token_limit,
            "usage_ratio": token_count / self._token_limit,
        }
