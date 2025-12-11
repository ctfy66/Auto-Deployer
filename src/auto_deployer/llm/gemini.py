"""Google Gemini LLM provider implementation."""

from __future__ import annotations

import json
import logging
import time
from typing import TYPE_CHECKING, Optional

import requests

if TYPE_CHECKING:
    from ..config import LLMConfig

logger = logging.getLogger(__name__)


class GeminiProvider:
    """Google Gemini LLM provider using official API."""

    def __init__(self, config: "LLMConfig"):
        """
        Initialize Gemini provider.

        Args:
            config: LLM configuration with api_key and optional endpoint
        """
        if not config.api_key:
            raise ValueError("Gemini API key is required")

        self.config = config
        self.session = requests.Session()

        # Set up proxy if configured
        import os
        proxy = config.proxy or os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
        if proxy:
            self.session.proxies = {"http": proxy, "https": proxy}
            logger.info("Gemini provider using proxy: %s", proxy)

        # Gemini API endpoint
        self.api_key = config.api_key
        self.model = config.model or "gemini-2.0-flash-exp"
        self.temperature = config.temperature

        # Build endpoint URL
        if config.endpoint:
            self.base_endpoint = config.endpoint
        else:
            self.base_endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"

    def generate_response(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        response_format: str = "json",
        timeout: int = 60,
        max_retries: int = 3,
    ) -> Optional[str]:
        """
        Generate a response from Gemini.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt (Note: Gemini doesn't have system prompt in the same way)
            response_format: "json" or "text"
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries on rate limit

        Returns:
            Generated text or None on failure
        """
        url = f"{self.base_endpoint}?key={self.api_key}"

        # Combine system prompt and user prompt for Gemini
        combined_prompt = prompt
        if system_prompt:
            combined_prompt = f"{system_prompt}\n\n---\n\n{prompt}"

        # Build request body
        body = {
            "contents": [{"role": "user", "parts": [{"text": combined_prompt}]}],
            "generationConfig": {
                "temperature": self.temperature,
            },
        }

        # Add JSON response format if requested
        if response_format == "json":
            body["generationConfig"]["responseMimeType"] = "application/json"

        # Retry loop for rate limiting
        for attempt in range(max_retries):
            try:
                response = self.session.post(
                    url,
                    json=body,
                    timeout=timeout
                )

                # Handle rate limiting
                if response.status_code == 429:
                    wait_time = 30 * (attempt + 1)
                    logger.warning(f"Rate limited by Gemini. Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                    continue

                response.raise_for_status()
                data = response.json()

                # Extract response text
                candidates = data.get("candidates") or []
                if not candidates:
                    logger.error("No candidates in Gemini response")
                    return None

                for candidate in candidates:
                    parts = candidate.get("content", {}).get("parts", [])
                    for part in parts:
                        text = part.get("text")
                        if text:
                            return text

                logger.error("No text found in Gemini response")
                return None

            except requests.exceptions.HTTPError as e:
                if response.status_code == 429 and attempt < max_retries - 1:
                    wait_time = 30 * (attempt + 1)
                    logger.warning(f"Rate limited. Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                    continue
                logger.error(f"Gemini API call failed: {e}")
                if hasattr(e, 'response') and e.response is not None:
                    try:
                        error_data = e.response.json()
                        logger.error(f"Error details: {error_data}")
                    except:
                        logger.error(f"Response text: {e.response.text[:500]}")
                return None
            except Exception as exc:
                logger.error(f"Gemini API call failed: {exc}")
                return None

        logger.error("Rate limited after max retries")
        return None
