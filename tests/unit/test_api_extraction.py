"""
Tests for extract_knowledge() function with mocked API.

HIGH PRIORITY: API integration with retry logic and error handling.
"""

import json
import time
from unittest.mock import MagicMock, patch, call

import pytest


# Create a proper mock APIError exception class
class MockAPIError(Exception):
    """Mock for anthropic.APIError."""
    pass


# We need to properly mock the anthropic module before importing pipeline
@pytest.fixture(autouse=True)
def mock_anthropic_module(monkeypatch):
    """Mock the anthropic module with a proper APIError exception."""
    mock_anthropic = MagicMock()
    mock_anthropic.APIError = MockAPIError
    monkeypatch.setattr("pipeline.anthropic", mock_anthropic)
    return mock_anthropic


# Import after setting up the fixture
from pipeline import extract_knowledge, API_RETRY_ATTEMPTS, API_RETRY_DELAY


class TestExtractKnowledgeSuccess:
    """Test successful API extraction scenarios."""

    def test_successful_extraction(self, sample_extraction_response):
        """Successful API call should return parsed JSON response."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(text=json.dumps(sample_extraction_response))
        ]
        mock_client.messages.create.return_value = mock_response

        result = extract_knowledge(
            conversation_text="Test conversation",
            source="claude",
            source_date="2024-12-07",
            bible_context="Test context",
            client=mock_client,
        )

        assert "items" in result
        assert len(result["items"]) == 2
        assert result["items"][0]["type"] == "theme"
        assert result["conversation_summary"] == sample_extraction_response["conversation_summary"]

    def test_api_called_with_correct_parameters(self, sample_extraction_response, monkeypatch):
        """API should be called with correct model and parameters."""
        # Mock CONFIG
        test_config = {"model": "test-model", "max_tokens": 2048}
        monkeypatch.setattr("pipeline.CONFIG", test_config)

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(text=json.dumps(sample_extraction_response))
        ]
        mock_client.messages.create.return_value = mock_response

        extract_knowledge(
            conversation_text="Test conversation",
            source="claude",
            source_date="2024-12-07",
            bible_context="Context",
            client=mock_client,
        )

        # Verify API was called
        mock_client.messages.create.assert_called_once()
        call_kwargs = mock_client.messages.create.call_args[1]

        assert call_kwargs["model"] == "test-model"
        assert call_kwargs["max_tokens"] == 2048
        assert "system" in call_kwargs
        assert "messages" in call_kwargs

    def test_empty_items_response(self):
        """API returning empty items should work."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(text=json.dumps({
                "items": [],
                "conversation_summary": "Nothing interesting",
                "primary_themes": [],
            }))
        ]
        mock_client.messages.create.return_value = mock_response

        result = extract_knowledge(
            conversation_text="Boring conversation",
            source="claude",
            source_date="2024-12-07",
            bible_context="",
            client=mock_client,
        )

        assert result["items"] == []
        assert "error" not in result


class TestExtractKnowledgeRetryLogic:
    """Test retry logic for API failures."""

    def test_retries_on_api_error(self, sample_extraction_response, mock_anthropic_module):
        """Should retry on API error and succeed."""
        mock_client = MagicMock()

        # First two calls fail, third succeeds
        mock_success = MagicMock()
        mock_success.content = [
            MagicMock(text=json.dumps(sample_extraction_response))
        ]

        mock_client.messages.create.side_effect = [
            MockAPIError("Rate limited"),
            MockAPIError("Rate limited"),
            mock_success,
        ]

        with patch("pipeline.time.sleep"):  # Don't actually wait
            result = extract_knowledge(
                conversation_text="Test",
                source="claude",
                source_date="2024-12-07",
                bible_context="",
                client=mock_client,
            )

        assert "items" in result
        assert "error" not in result
        assert mock_client.messages.create.call_count == 3

    def test_exponential_backoff_delays(self, sample_extraction_response, mock_anthropic_module):
        """Should use exponential backoff between retries."""
        mock_client = MagicMock()
        mock_success = MagicMock()
        mock_success.content = [
            MagicMock(text=json.dumps(sample_extraction_response))
        ]

        mock_client.messages.create.side_effect = [
            MockAPIError("Error"),
            MockAPIError("Error"),
            mock_success,
        ]

        with patch("pipeline.time.sleep") as mock_sleep:
            extract_knowledge(
                conversation_text="Test",
                source="claude",
                source_date="2024-12-07",
                bible_context="",
                client=mock_client,
            )

            # Check exponential backoff: 2*1, 2*2 (API_RETRY_DELAY * attempt)
            assert mock_sleep.call_count == 2
            calls = mock_sleep.call_args_list
            assert calls[0] == call(API_RETRY_DELAY * 1)  # First retry: 2s
            assert calls[1] == call(API_RETRY_DELAY * 2)  # Second retry: 4s

    def test_fails_after_max_retries(self, mock_anthropic_module):
        """Should return error after exhausting all retries."""
        mock_client = MagicMock()

        # All calls fail
        mock_client.messages.create.side_effect = MockAPIError("Persistent error")

        with patch("pipeline.time.sleep"):
            result = extract_knowledge(
                conversation_text="Test",
                source="claude",
                source_date="2024-12-07",
                bible_context="",
                client=mock_client,
            )

        assert "error" in result
        assert result["items"] == []
        assert "after retries" in result["error"]
        assert mock_client.messages.create.call_count == API_RETRY_ATTEMPTS


class TestExtractKnowledgeJSONParsing:
    """Test JSON response parsing."""

    def test_invalid_json_response(self):
        """Invalid JSON in response should return error."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Not valid JSON {{{")]
        mock_client.messages.create.return_value = mock_response

        result = extract_knowledge(
            conversation_text="Test",
            source="claude",
            source_date="2024-12-07",
            bible_context="",
            client=mock_client,
        )

        assert "error" in result
        assert "JSON decode error" in result["error"]
        assert result["items"] == []

    def test_truncated_json_response(self):
        """Truncated JSON should return error."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        # JSON that's cut off mid-way
        mock_response.content = [MagicMock(text='{"items": [{"type": "theme", "title":')]
        mock_client.messages.create.return_value = mock_response

        result = extract_knowledge(
            conversation_text="Test",
            source="claude",
            source_date="2024-12-07",
            bible_context="",
            client=mock_client,
        )

        assert "error" in result
        assert result["items"] == []

    def test_json_with_markdown_code_block(self):
        """JSON wrapped in markdown code block should still fail (API shouldn't do this)."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        # Response with markdown wrapper
        mock_response.content = [
            MagicMock(text='```json\n{"items": []}\n```')
        ]
        mock_client.messages.create.return_value = mock_response

        result = extract_knowledge(
            conversation_text="Test",
            source="claude",
            source_date="2024-12-07",
            bible_context="",
            client=mock_client,
        )

        # This will fail JSON parsing due to markdown wrapper
        assert "error" in result


class TestExtractKnowledgeErrorHandling:
    """Test various error conditions."""

    def test_unexpected_exception(self):
        """Unexpected exceptions should be caught and return error."""
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = ValueError("Unexpected error")

        result = extract_knowledge(
            conversation_text="Test",
            source="claude",
            source_date="2024-12-07",
            bible_context="",
            client=mock_client,
        )

        assert "error" in result
        assert "Unexpected error" in result["error"]
        assert result["items"] == []

    def test_network_timeout(self):
        """Network timeout (as generic Exception) should be caught."""
        mock_client = MagicMock()
        # Use a regular Exception since TimeoutError might not be caught properly
        mock_client.messages.create.side_effect = Exception("Connection timed out")

        result = extract_knowledge(
            conversation_text="Test",
            source="claude",
            source_date="2024-12-07",
            bible_context="",
            client=mock_client,
        )

        assert "error" in result
        assert result["items"] == []

    def test_empty_response_content(self):
        """Empty response content should be handled."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = []  # Empty content list
        mock_client.messages.create.return_value = mock_response

        # This will raise IndexError when accessing content[0], caught by general except
        result = extract_knowledge(
            conversation_text="Test",
            source="claude",
            source_date="2024-12-07",
            bible_context="",
            client=mock_client,
        )

        assert "error" in result


class TestExtractKnowledgeInputHandling:
    """Test handling of various input types."""

    def test_empty_conversation(self, sample_extraction_response):
        """Empty conversation text should still make API call."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(text=json.dumps(sample_extraction_response))
        ]
        mock_client.messages.create.return_value = mock_response

        result = extract_knowledge(
            conversation_text="",
            source="claude",
            source_date="2024-12-07",
            bible_context="",
            client=mock_client,
        )

        # Should still work
        mock_client.messages.create.assert_called_once()

    def test_very_long_conversation(self, sample_extraction_response):
        """Very long conversation should be passed through."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(text=json.dumps(sample_extraction_response))
        ]
        mock_client.messages.create.return_value = mock_response

        # 100KB of text
        long_conversation = "User: Hello\n" * 10000

        result = extract_knowledge(
            conversation_text=long_conversation,
            source="claude",
            source_date="2024-12-07",
            bible_context="",
            client=mock_client,
        )

        assert "items" in result
        # Verify the long text was passed
        call_kwargs = mock_client.messages.create.call_args[1]
        assert long_conversation in call_kwargs["messages"][0]["content"]

    def test_unicode_in_conversation(self, sample_extraction_response):
        """Unicode in conversation should be handled."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(text=json.dumps(sample_extraction_response))
        ]
        mock_client.messages.create.return_value = mock_response

        result = extract_knowledge(
            conversation_text="User: 日本語で話しましょう",
            source="claude",
            source_date="2024-12-07",
            bible_context="コンテキスト",
            client=mock_client,
        )

        assert "items" in result

    def test_special_characters_in_bible_context(self, sample_extraction_response):
        """Special characters in bible context should be handled."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(text=json.dumps(sample_extraction_response))
        ]
        mock_client.messages.create.return_value = mock_response

        result = extract_knowledge(
            conversation_text="Test",
            source="claude",
            source_date="2024-12-07",
            bible_context="Goals: $1M revenue\nFormula: a < b && c > d\nQuote: \"success\"",
            client=mock_client,
        )

        assert "items" in result


class TestExtractKnowledgeResponseValidation:
    """Test handling of various response structures."""

    def test_missing_items_key(self):
        """Response without 'items' key should still work."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(text=json.dumps({
                "conversation_summary": "Summary only",
            }))
        ]
        mock_client.messages.create.return_value = mock_response

        result = extract_knowledge(
            conversation_text="Test",
            source="claude",
            source_date="2024-12-07",
            bible_context="",
            client=mock_client,
        )

        # Should return the parsed response as-is
        assert "conversation_summary" in result

    def test_extra_fields_preserved(self):
        """Extra fields in response should be preserved."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(text=json.dumps({
                "items": [],
                "conversation_summary": "Test",
                "primary_themes": [],
                "extra_field": "extra_value",
                "metadata": {"key": "value"},
            }))
        ]
        mock_client.messages.create.return_value = mock_response

        result = extract_knowledge(
            conversation_text="Test",
            source="claude",
            source_date="2024-12-07",
            bible_context="",
            client=mock_client,
        )

        assert result.get("extra_field") == "extra_value"
        assert result.get("metadata") == {"key": "value"}
