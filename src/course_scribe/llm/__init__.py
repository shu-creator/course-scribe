"""LLM Provider abstraction layer.

This module provides a unified interface for LLM providers.
Currently supports Claude API, with extensibility for other providers.

Usage:
    provider = get_provider("claude")
    response = provider.generate(prompt, system_prompt)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum


class ProviderType(str, Enum):
    """Supported LLM provider types."""
    CLAUDE = "claude"


@dataclass
class LLMResponse:
    """Response from an LLM provider."""
    content: str
    model: str
    input_tokens: int
    output_tokens: int

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """Generate a response from the LLM.

        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt for context
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0-1)

        Returns:
            LLMResponse with the generated content
        """
        pass

    @abstractmethod
    def generate_json(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 4096,
    ) -> dict:
        """Generate a JSON response from the LLM.

        Args:
            prompt: The user prompt (should request JSON output)
            system_prompt: Optional system prompt
            max_tokens: Maximum tokens in response

        Returns:
            Parsed JSON as dict

        Raises:
            ValueError: If response is not valid JSON
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name."""
        pass


class LLMProviderError(Exception):
    """Base exception for LLM provider errors."""
    pass


class APIKeyNotFoundError(LLMProviderError):
    """Raised when API key is not configured."""
    pass


class RateLimitError(LLMProviderError):
    """Raised when rate limit is exceeded."""
    pass


class InvalidResponseError(LLMProviderError):
    """Raised when response cannot be parsed."""
    pass


# Provider registry
_providers: dict[str, type[LLMProvider]] = {}


def register_provider(name: str, provider_class: type[LLMProvider]) -> None:
    """Register an LLM provider."""
    _providers[name] = provider_class


def get_provider(name: str = "claude", **kwargs) -> LLMProvider:
    """Get an LLM provider instance.

    Args:
        name: Provider name (default: "claude")
        **kwargs: Provider-specific configuration

    Returns:
        Configured LLMProvider instance

    Raises:
        ValueError: If provider is not registered
    """
    if name not in _providers:
        # Lazy import to avoid circular dependencies
        if name == "claude":
            from course_scribe.llm.claude import ClaudeProvider
            register_provider("claude", ClaudeProvider)
        else:
            raise ValueError(
                f"Unknown provider: {name}. "
                f"Available: {list(_providers.keys())}"
            )

    return _providers[name](**kwargs)
