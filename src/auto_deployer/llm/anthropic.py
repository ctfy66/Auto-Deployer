"""Anthropic Claude LLM provider implementation."""

from __future__ import annotations

import json
import logging
import time
from typing import TYPE_CHECKING, Optional

import requests

if TYPE_CHECKING:
    from ..config import LLMConfig

logger = logging.getLogger(__name__)


class AnthropicProvider:
    """Anthropic Claude LLM provider using official API."""

    def __init__(self, config: "LLMConfig"):
        """
        Initialize Anthropic provider.

        Args:
            config: LLM configuration with api_key and optional endpoint
        """
        if not config.api_key:
            raise ValueError("Anthropic API key is required")

        self.config = config
        self.session = requests.Session()

        # Set up proxy if configured
        import os
        proxy = config.proxy or os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
        if proxy:
            self.session.proxies = {"http": proxy, "https": proxy}
            logger.info("Anthropic provider using proxy: %s", proxy)

        # Anthropic API endpoint
        self.base_url = config.endpoint or "https://api.anthropic.com/v1"
        self.api_key = config.api_key
        self.model = config.model or "claude-3-5-sonnet-20241022"
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
        Generate a response from Anthropic Claude.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            response_format: "json" or "text" (Claude doesn't have strict JSON mode)
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries on rate limit

        Returns:
            Generated text or None on failure
        """
        url = f"{self.base_url}/messages"

        # Build request body
        body = {
            "model": self.model,
            "max_tokens": 4096,
            "temperature": self.temperature,
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }

        # Add system prompt if provided
        if system_prompt:
            # For JSON format, append instruction to system prompt
            if response_format == "json":
                system_prompt += "\n\nIMPORTANT: You MUST respond with valid JSON only, no markdown, no explanation."
            body["system"] = system_prompt

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
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
                    logger.warning(f"Rate limited by Anthropic. Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                    continue

                response.raise_for_status()
                data = response.json()

                # Extract response content
                content_blocks = data.get("content", [])
                if not content_blocks:
                    logger.error("No content in Anthropic response")
                    return None

                # Get text from first content block
                text = content_blocks[0].get("text")

                if not text:
                    logger.error("No text in Anthropic response content")
                    return None

                return text

            except requests.exceptions.HTTPError as e:
                if response.status_code == 429 and attempt < max_retries - 1:
                    wait_time = 30 * (attempt + 1)
                    logger.warning(f"Rate limited. Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                    continue
                logger.error(f"Anthropic API call failed: {e}")
                if hasattr(e, 'response') and e.response is not None:
                    try:
                        error_data = e.response.json()
                        logger.error(f"Error details: {error_data}")
                    except:
                        logger.error(f"Response text: {e.response.text[:500]}")
                return None
            except Exception as exc:
                logger.error(f"Anthropic API call failed: {exc}")
                return None

        logger.error("Rate limited after max retries")
        return None
