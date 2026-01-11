"""Claude API provider implementation.

Uses the Anthropic Python SDK to interact with Claude models.

Configuration:
    API key can be provided via:
    1. ANTHROPIC_API_KEY environment variable
    2. api_key parameter to ClaudeProvider
"""

import json
import os
from typing import Any

from course_scribe.llm import (
    LLMProvider,
    LLMResponse,
    APIKeyNotFoundError,
    RateLimitError,
    InvalidResponseError,
    register_provider,
)


# Default model to use
DEFAULT_MODEL = "claude-sonnet-4-20250514"


class ClaudeProvider(LLMProvider):
    """Claude API provider using Anthropic SDK."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
    ):
        """Initialize Claude provider.

        Args:
            api_key: Anthropic API key. If not provided, uses ANTHROPIC_API_KEY env var.
            model: Model to use (default: claude-sonnet-4-20250514)
        """
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self._model = model
        self._client = None

    def _get_client(self):
        """Get or create the Anthropic client."""
        if self._client is None:
            if not self._api_key:
                raise APIKeyNotFoundError(
                    "Anthropic API key not found.\n"
                    "Set ANTHROPIC_API_KEY environment variable or pass api_key parameter.\n"
                    "Get your API key at: https://console.anthropic.com/"
                )

            try:
                from anthropic import Anthropic
            except ImportError:
                raise ImportError(
                    "anthropic package is required for Claude API.\n"
                    "Install with: pip install anthropic"
                )

            self._client = Anthropic(api_key=self._api_key)

        return self._client

    @property
    def name(self) -> str:
        return "claude"

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """Generate a response using Claude."""
        client = self._get_client()

        try:
            kwargs: dict[str, Any] = {
                "model": self._model,
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            }

            if system_prompt:
                kwargs["system"] = system_prompt

            if temperature != 0.7:
                kwargs["temperature"] = temperature

            response = client.messages.create(**kwargs)

            return LLMResponse(
                content=response.content[0].text,
                model=response.model,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
            )

        except Exception as e:
            error_str = str(e).lower()
            if "rate" in error_str and "limit" in error_str:
                raise RateLimitError(f"Rate limit exceeded: {e}")
            raise

    def generate_json(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 4096,
    ) -> dict:
        """Generate a JSON response using Claude."""
        # Add JSON instruction to system prompt
        json_system = (
            "You must respond with valid JSON only. "
            "Do not include any text before or after the JSON. "
            "Do not use markdown code blocks."
        )

        if system_prompt:
            full_system = f"{system_prompt}\n\n{json_system}"
        else:
            full_system = json_system

        response = self.generate(
            prompt=prompt,
            system_prompt=full_system,
            max_tokens=max_tokens,
            temperature=0.3,  # Lower temperature for more consistent JSON
        )

        # Parse JSON
        content = response.content.strip()

        # Remove markdown code blocks if present
        if content.startswith("```"):
            lines = content.split("\n")
            # Remove first and last lines (```json and ```)
            content = "\n".join(lines[1:-1])

        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            raise InvalidResponseError(
                f"Failed to parse JSON response: {e}\n"
                f"Response was: {content[:500]}..."
            )


# Register the provider
register_provider("claude", ClaudeProvider)
