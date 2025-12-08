"""
Tests for prompt generation functions.

LOW PRIORITY: Extraction prompt template formatting.
"""

import pytest

from prompts.extraction_prompt import (
    EXTRACTION_SYSTEM_PROMPT,
    EXTRACTION_USER_PROMPT,
    build_extraction_prompt,
)


class TestExtractionSystemPrompt:
    """Tests for the system prompt constant."""

    def test_system_prompt_not_empty(self):
        """System prompt should not be empty."""
        assert len(EXTRACTION_SYSTEM_PROMPT) > 0

    def test_system_prompt_mentions_knowledge_extraction(self):
        """System prompt should describe the knowledge extraction role."""
        assert "knowledge extraction" in EXTRACTION_SYSTEM_PROMPT.lower()

    def test_system_prompt_mentions_json(self):
        """System prompt should mention JSON output format."""
        assert "JSON" in EXTRACTION_SYSTEM_PROMPT

    def test_system_prompt_mentions_confidence(self):
        """System prompt should explain confidence levels."""
        assert "confidence" in EXTRACTION_SYSTEM_PROMPT.lower()
        assert "high" in EXTRACTION_SYSTEM_PROMPT
        assert "medium" in EXTRACTION_SYSTEM_PROMPT
        assert "low" in EXTRACTION_SYSTEM_PROMPT

    def test_system_prompt_mentions_obsidian(self):
        """System prompt should mention Obsidian context."""
        assert "Obsidian" in EXTRACTION_SYSTEM_PROMPT


class TestExtractionUserPrompt:
    """Tests for the user prompt template."""

    def test_user_prompt_has_placeholders(self):
        """User prompt should have format placeholders."""
        assert "{bible_context}" in EXTRACTION_USER_PROMPT
        assert "{source}" in EXTRACTION_USER_PROMPT
        assert "{source_date}" in EXTRACTION_USER_PROMPT
        assert "{conversation_text}" in EXTRACTION_USER_PROMPT

    def test_user_prompt_mentions_item_types(self):
        """User prompt should describe all item types."""
        assert "THEMES" in EXTRACTION_USER_PROMPT
        assert "DECISIONS" in EXTRACTION_USER_PROMPT
        assert "ACTIONS" in EXTRACTION_USER_PROMPT
        assert "INSIGHTS" in EXTRACTION_USER_PROMPT

    def test_user_prompt_contains_json_schema(self):
        """User prompt should contain the expected JSON schema."""
        assert '"items"' in EXTRACTION_USER_PROMPT
        assert '"type"' in EXTRACTION_USER_PROMPT
        assert '"title"' in EXTRACTION_USER_PROMPT
        assert '"content"' in EXTRACTION_USER_PROMPT
        assert '"key_quote"' in EXTRACTION_USER_PROMPT
        assert '"related_themes"' in EXTRACTION_USER_PROMPT
        assert '"confidence"' in EXTRACTION_USER_PROMPT

    def test_user_prompt_mentions_wiki_links(self):
        """User prompt should mention Obsidian wiki link syntax."""
        assert "[[" in EXTRACTION_USER_PROMPT
        assert "]]" in EXTRACTION_USER_PROMPT


class TestBuildExtractionPrompt:
    """Tests for build_extraction_prompt() function."""

    def test_basic_prompt_construction(self):
        """Should construct a prompt with all provided values."""
        result = build_extraction_prompt(
            conversation_text="User: Hello\n\nAssistant: Hi",
            source="claude",
            source_date="2024-12-07",
            bible_context="Project goals here",
        )

        assert "User: Hello" in result
        assert "Assistant: Hi" in result
        assert "claude" in result
        assert "2024-12-07" in result
        assert "Project goals here" in result

    def test_empty_bible_context_shows_placeholder(self):
        """Empty bible context should show placeholder message."""
        result = build_extraction_prompt(
            conversation_text="Test conversation",
            source="claude",
            source_date="2024-12-07",
            bible_context="",
        )

        assert "(No project context provided)" in result

    def test_none_bible_context_handled(self):
        """None bible context should be handled gracefully."""
        # Default value is empty string, but let's verify behavior
        result = build_extraction_prompt(
            conversation_text="Test",
            source="claude",
            source_date="2024-12-07",
        )

        assert "(No project context provided)" in result

    def test_preserves_conversation_formatting(self):
        """Should preserve conversation text formatting."""
        conversation = "User: Line 1\n\nAssistant: Line 2\nContinued on next line"

        result = build_extraction_prompt(
            conversation_text=conversation,
            source="claude",
            source_date="2024-12-07",
        )

        assert "Line 1\n\nAssistant: Line 2\nContinued" in result

    def test_unicode_content(self):
        """Should handle unicode content in all fields."""
        result = build_extraction_prompt(
            conversation_text="User: 日本語の質問\n\nAssistant: 日本語の回答",
            source="claude",
            source_date="2024-12-07",
            bible_context="プロジェクトコンテキスト 🎉",
        )

        assert "日本語の質問" in result
        assert "日本語の回答" in result
        assert "プロジェクトコンテキスト 🎉" in result

    def test_special_characters_in_conversation(self):
        """Should handle special characters without escaping issues."""
        result = build_extraction_prompt(
            conversation_text="User: What about {curly} and $dollar?",
            source="claude",
            source_date="2024-12-07",
            bible_context="Context with {braces}",
        )

        # Should not raise format errors
        assert "{curly}" in result
        assert "$dollar" in result

    def test_very_long_conversation(self):
        """Should handle very long conversations."""
        long_conversation = "User: Hello\n" * 10000

        result = build_extraction_prompt(
            conversation_text=long_conversation,
            source="claude",
            source_date="2024-12-07",
        )

        assert len(result) > 100000

    def test_all_source_types(self):
        """Should work with all expected source types."""
        for source in ["claude", "chatgpt", "gemini"]:
            result = build_extraction_prompt(
                conversation_text="Test",
                source=source,
                source_date="2024-12-07",
            )
            assert source in result

    def test_various_date_formats(self):
        """Should accept various date string formats."""
        dates = ["2024-12-07", "2024-01-01", "2023-06-15"]

        for date in dates:
            result = build_extraction_prompt(
                conversation_text="Test",
                source="claude",
                source_date=date,
            )
            assert date in result

    def test_prompt_structure(self):
        """Resulting prompt should have expected structure."""
        result = build_extraction_prompt(
            conversation_text="Test conversation",
            source="claude",
            source_date="2024-12-07",
            bible_context="Context",
        )

        # Should have context section
        assert "## Current Context" in result

        # Should have conversation section
        assert "## Conversation to Analyze" in result

        # Should have source and date
        assert "Source:" in result
        assert "Date:" in result

        # Should have extraction instructions
        assert "Extract the following" in result

    def test_return_type_is_string(self):
        """Should return a string."""
        result = build_extraction_prompt(
            conversation_text="Test",
            source="claude",
            source_date="2024-12-07",
        )

        assert isinstance(result, str)
