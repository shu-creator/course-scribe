"""Tests for LLM provider abstraction layer."""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock

from course_scribe.llm import (
    LLMResponse,
    LLMProvider,
    get_provider,
    register_provider,
    LLMProviderError,
    APIKeyNotFoundError,
    RateLimitError,
    InvalidResponseError,
)

# Check if anthropic is available for some tests
try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False


class TestLLMResponse:
    """Tests for LLMResponse dataclass."""

    def test_llm_response_creation(self):
        """Test creating an LLMResponse."""
        response = LLMResponse(
            content="Hello, world!",
            model="claude-sonnet-4-20250514",
            input_tokens=10,
            output_tokens=5,
        )

        assert response.content == "Hello, world!"
        assert response.model == "claude-sonnet-4-20250514"
        assert response.input_tokens == 10
        assert response.output_tokens == 5

    def test_total_tokens(self):
        """Test total_tokens property."""
        response = LLMResponse(
            content="Test",
            model="test-model",
            input_tokens=100,
            output_tokens=50,
        )

        assert response.total_tokens == 150


class TestGetProvider:
    """Tests for get_provider function."""

    def test_get_claude_provider(self):
        """Test getting Claude provider."""
        with patch("course_scribe.llm.claude.os.environ.get") as mock_env:
            mock_env.return_value = "test-api-key"
            provider = get_provider("claude")
            assert provider.name == "claude"

    def test_get_unknown_provider(self):
        """Test error when requesting unknown provider."""
        with pytest.raises(ValueError, match="Unknown provider"):
            get_provider("unknown_provider")

    def test_provider_with_kwargs(self):
        """Test passing kwargs to provider."""
        with patch("course_scribe.llm.claude.os.environ.get") as mock_env:
            mock_env.return_value = None
            provider = get_provider("claude", api_key="custom-key")
            assert provider._api_key == "custom-key"


class TestClaudeProvider:
    """Tests for ClaudeProvider implementation."""

    def test_provider_name(self):
        """Test provider name property."""
        provider = get_provider("claude", api_key="test-key")
        assert provider.name == "claude"

    def test_api_key_from_env(self):
        """Test API key from environment variable."""
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "env-key"}):
            from course_scribe.llm.claude import ClaudeProvider
            provider = ClaudeProvider()
            assert provider._api_key == "env-key"

    def test_api_key_from_parameter(self):
        """Test API key from parameter takes precedence."""
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "env-key"}):
            from course_scribe.llm.claude import ClaudeProvider
            provider = ClaudeProvider(api_key="param-key")
            assert provider._api_key == "param-key"

    def test_missing_api_key_raises_error(self):
        """Test error when API key is missing."""
        with patch.dict("os.environ", {}, clear=True):
            from course_scribe.llm.claude import ClaudeProvider
            provider = ClaudeProvider()
            provider._api_key = None

            with pytest.raises(APIKeyNotFoundError, match="API key not found"):
                provider._get_client()

    @pytest.mark.skipif(not HAS_ANTHROPIC, reason="anthropic not installed")
    def test_generate(self):
        """Test generate method."""
        with patch("anthropic.Anthropic") as mock_class:
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text="Test response")]
            mock_response.model = "claude-sonnet-4-20250514"
            mock_response.usage.input_tokens = 10
            mock_response.usage.output_tokens = 20

            mock_client = MagicMock()
            mock_client.messages.create.return_value = mock_response
            mock_class.return_value = mock_client

            from course_scribe.llm.claude import ClaudeProvider
            provider = ClaudeProvider(api_key="test-key")

            response = provider.generate(
                prompt="Hello",
                system_prompt="Be helpful",
            )

            assert response.content == "Test response"
            assert response.model == "claude-sonnet-4-20250514"
            assert response.input_tokens == 10
            assert response.output_tokens == 20

            # Verify API was called correctly
            mock_client.messages.create.assert_called_once()
            call_kwargs = mock_client.messages.create.call_args.kwargs
            assert call_kwargs["messages"] == [{"role": "user", "content": "Hello"}]
            assert call_kwargs["system"] == "Be helpful"

    @pytest.mark.skipif(not HAS_ANTHROPIC, reason="anthropic not installed")
    def test_generate_without_system_prompt(self):
        """Test generate without system prompt."""
        with patch("anthropic.Anthropic") as mock_class:
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text="Test response")]
            mock_response.model = "test-model"
            mock_response.usage.input_tokens = 10
            mock_response.usage.output_tokens = 20

            mock_client = MagicMock()
            mock_client.messages.create.return_value = mock_response
            mock_class.return_value = mock_client

            from course_scribe.llm.claude import ClaudeProvider
            provider = ClaudeProvider(api_key="test-key")

            provider.generate(prompt="Hello")

            call_kwargs = mock_client.messages.create.call_args.kwargs
            assert "system" not in call_kwargs

    @pytest.mark.skipif(not HAS_ANTHROPIC, reason="anthropic not installed")
    def test_generate_json(self):
        """Test generate_json method."""
        with patch("anthropic.Anthropic") as mock_class:
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text='{"key": "value", "number": 42}')]
            mock_response.model = "test-model"
            mock_response.usage.input_tokens = 10
            mock_response.usage.output_tokens = 20

            mock_client = MagicMock()
            mock_client.messages.create.return_value = mock_response
            mock_class.return_value = mock_client

            from course_scribe.llm.claude import ClaudeProvider
            provider = ClaudeProvider(api_key="test-key")

            result = provider.generate_json(
                prompt="Generate JSON",
                system_prompt="Return JSON",
            )

            assert result == {"key": "value", "number": 42}

    @pytest.mark.skipif(not HAS_ANTHROPIC, reason="anthropic not installed")
    def test_generate_json_with_markdown_code_block(self):
        """Test generate_json handles markdown code blocks."""
        with patch("anthropic.Anthropic") as mock_class:
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text='```json\n{"key": "value"}\n```')]
            mock_response.model = "test-model"
            mock_response.usage.input_tokens = 10
            mock_response.usage.output_tokens = 20

            mock_client = MagicMock()
            mock_client.messages.create.return_value = mock_response
            mock_class.return_value = mock_client

            from course_scribe.llm.claude import ClaudeProvider
            provider = ClaudeProvider(api_key="test-key")

            result = provider.generate_json(prompt="Generate JSON")

            assert result == {"key": "value"}

    @pytest.mark.skipif(not HAS_ANTHROPIC, reason="anthropic not installed")
    def test_generate_json_invalid_response(self):
        """Test error when response is not valid JSON."""
        with patch("anthropic.Anthropic") as mock_class:
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text="This is not JSON")]
            mock_response.model = "test-model"
            mock_response.usage.input_tokens = 10
            mock_response.usage.output_tokens = 20

            mock_client = MagicMock()
            mock_client.messages.create.return_value = mock_response
            mock_class.return_value = mock_client

            from course_scribe.llm.claude import ClaudeProvider
            provider = ClaudeProvider(api_key="test-key")

            with pytest.raises(InvalidResponseError, match="Failed to parse JSON"):
                provider.generate_json(prompt="Generate JSON")

    @pytest.mark.skipif(not HAS_ANTHROPIC, reason="anthropic not installed")
    def test_rate_limit_error(self):
        """Test rate limit error handling."""
        with patch("anthropic.Anthropic") as mock_class:
            mock_client = MagicMock()
            mock_client.messages.create.side_effect = Exception("Rate limit exceeded")
            mock_class.return_value = mock_client

            from course_scribe.llm.claude import ClaudeProvider
            provider = ClaudeProvider(api_key="test-key")

            with pytest.raises(RateLimitError, match="Rate limit"):
                provider.generate(prompt="Hello")


class TestProviderIntegrationWithSkills:
    """Tests for provider integration with skills (using mocks)."""

    @pytest.fixture
    def mock_provider(self):
        """Create a mock LLM provider."""
        provider = MagicMock(spec=LLMProvider)
        provider.name = "mock"
        return provider

    @pytest.fixture
    def sample_lecture(self):
        """Sample lecture data."""
        return {
            "week_number": 1,
            "title": "Introduction to AI",
            "source_type": "transcript",
            "raw_text": "This lecture covers machine learning basics.",
            "sections": [
                {
                    "heading": "What is ML?",
                    "content": "Machine learning is a subset of AI.",
                    "keywords_mentioned": ["machine learning", "AI"],
                }
            ],
        }

    @pytest.fixture
    def sample_syllabus(self):
        """Sample syllabus data."""
        return {
            "course_name": "AI Course",
            "weeks": [
                {
                    "week_number": 1,
                    "title": "AI Introduction",
                    "topics": ["AI basics", "ML fundamentals"],
                    "keywords": ["AI", "machine learning"],
                }
            ],
        }

    def test_summarize_with_llm(self, mock_provider, sample_lecture, sample_syllabus):
        """Test summarize_lecture with use_llm=True."""
        # Setup mock response
        mock_provider.generate_json.return_value = {
            "week_number": 1,
            "title": "Week 1 Summary",
            "syllabus_alignment": {"AI basics": True},
            "sections": [
                {
                    "heading": "Overview",
                    "content": "AI fundamentals summary",
                    "syllabus_topics": ["AI basics"],
                    "key_points": ["AI is powerful"],
                }
            ],
            "exam_focus_points": ["Understand AI basics"],
            "uncovered_topics": [],
        }

        with patch("course_scribe.llm.get_provider") as mock_get:
            mock_get.return_value = mock_provider

            from course_scribe.skills.summarize import summarize_lecture
            result = summarize_lecture(
                sample_lecture,
                sample_syllabus,
                use_llm=True,
            )

            assert result["week_number"] == 1
            assert result["title"] == "Week 1 Summary"
            mock_provider.generate_json.assert_called_once()

    def test_generate_questions_with_llm(
        self, mock_provider, sample_lecture, sample_syllabus
    ):
        """Test generate_questions with use_llm=True."""
        # Setup mock response
        mock_provider.generate_json.return_value = {
            "week_number": 1,
            "title": "Week 1 Questions",
            "essay_questions": [
                {
                    "question_text": "Explain AI basics",
                    "syllabus_topics": ["AI basics"],
                    "difficulty": "medium",
                    "source_reference": "Lecture 1",
                    "expected_length": "400-600",
                    "required_concepts": ["AI"],
                    "model_answer": {
                        "answer_text": "AI is...",
                        "key_points": ["Definition of AI"],
                        "grading": {
                            "full_marks": 20,
                            "criteria": ["Accurate definition"],
                            "partial_credit_rules": [],
                            "common_mistakes": [],
                        },
                    },
                }
            ],
            "calculation_questions": [],
            "multiple_choice_questions": [],
        }

        with patch("course_scribe.llm.get_provider") as mock_get:
            mock_get.return_value = mock_provider

            from course_scribe.skills.generate_questions import generate_questions
            result = generate_questions(
                sample_lecture,
                sample_syllabus,
                use_llm=True,
            )

            assert result["week_number"] == 1
            assert len(result["essay_questions"]) == 1
            assert result["essay_questions"][0]["question_text"] == "Explain AI basics"
            mock_provider.generate_json.assert_called_once()
