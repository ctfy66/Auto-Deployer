"""OpenRouter LLM provider implementation (aggregator for multiple models)."""

from __future__ import annotations

import json
import logging
import time
from typing import TYPE_CHECKING, Optional

import requests

if TYPE_CHECKING:
    from ..config import LLMConfig

logger = logging.getLogger(__name__)


class OpenRouterProvider:
    """OpenRouter LLM provider - access multiple LLMs through one API."""

    def __init__(self, config: "LLMConfig"):
        """
        Initialize OpenRouter provider.

        Args:
            config: LLM configuration with api_key and optional endpoint
        """
        if not config.api_key:
            raise ValueError("OpenRouter API key is required")

        self.config = config
        self.session = requests.Session()

        # Set up proxy if configured
        import os
        proxy = config.proxy or os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
        if proxy:
            self.session.proxies = {"http": proxy, "https": proxy}
            logger.info("OpenRouter provider using proxy: %s", proxy)

        # OpenRouter API endpoint
        self.base_url = config.endpoint or "https://openrouter.ai/api/v1"
        self.api_key = config.api_key
        # Popular models: anthropic/claude-3.5-sonnet, openai/gpt-4o, google/gemini-2.0-flash-exp, etc.
        self.model = config.model or "anthropic/claude-3.5-sonnet"
        self.temperature = config.temperature

    def generate_response(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        response_format: str = "json",
        timeout: int = 60,
        max_retries: int = 3,
    ) -> Optional[str]:
        """
        Generate a response from OpenRouter.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            response_format: "json" or "text"
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries on rate limit

        Returns:
            Generated text or None on failure
        """
        url = f"{self.base_url}/chat/completions"

        # Build messages
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # Build request body
        body = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
        }

        # Add response format if JSON is requested (not all models support this)
        if response_format == "json":
            body["response_format"] = {"type": "json_object"}

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/yourusername/auto-deployer",  # Optional: for rankings
            "X-Title": "Auto-Deployer",  # Optional: show in OpenRouter dashboard
        }

        # Retry loop for rate limiting
        for attempt in range(max_retries):
            try:
                response = self.session.post(
                    url,
                    json=body,
                    headers=headers,
                    timeout=timeout
                )

                # Handle rate limiting
                if response.status_code == 429:
                    wait_time = 30 * (attempt + 1)
                    logger.warning(f"Rate limited by OpenRouter. Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                    continue

                response.raise_for_status()
                data = response.json()

                # Extract response content
                choices = data.get("choices", [])
                if not choices:
                    logger.error("No choices in OpenRouter response")
                    return None

                message = choices[0].get("message", {})
                content = message.get("content")

                if not content:
                    logger.error("No content in OpenRouter response")
                    return None

                return content

            except requests.exceptions.HTTPError as e:
                if response.status_code == 429 and attempt < max_retries - 1:
                    wait_time = 30 * (attempt + 1)
                    logger.warning(f"Rate limited. Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                    continue
                logger.error(f"OpenRouter API call failed: {e}")
                if hasattr(e, 'response') and e.response is not None:
                    try:
                        error_data = e.response.json()
                        logger.error(f"Error details: {error_data}")
                    except:
                        logger.error(f"Response text: {e.response.text[:500]}")
                return None
            except Exception as exc:
                logger.error(f"OpenRouter API call failed: {exc}")
                return None

        logger.error("Rate limited after max retries")
        return None
