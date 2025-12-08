"""
Tests for output generation functions.

MEDIUM PRIORITY: YAML frontmatter, file writing, and summary generation.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import yaml

from pipeline import (
    format_frontmatter,
    write_staged_item,
    write_extraction_summary,
    generate_item_id,
)


class TestFormatFrontmatter:
    """Tests for format_frontmatter() function."""

    def test_basic_metadata(self):
        """Basic metadata should produce valid YAML frontmatter."""
        metadata = {"title": "Test Title", "type": "theme"}
        result = format_frontmatter(metadata)

        assert result.startswith("---\n")
        assert result.endswith("---")
        # Should be parseable YAML
        yaml_content = result.strip("---").strip()
        parsed = yaml.safe_load(yaml_content)
        assert parsed["title"] == "Test Title"
        assert parsed["type"] == "theme"

    def test_list_values(self):
        """List values should be properly serialized."""
        metadata = {
            "title": "Test",
            "related_themes": ["[[Theme 1]]", "[[Theme 2]]", "[[Theme 3]]"],
        }
        result = format_frontmatter(metadata)

        yaml_content = result.strip("---").strip()
        parsed = yaml.safe_load(yaml_content)
        assert parsed["related_themes"] == ["[[Theme 1]]", "[[Theme 2]]", "[[Theme 3]]"]

    def test_nested_dict(self):
        """Nested dictionaries should be serialized."""
        metadata = {
            "title": "Test",
            "metadata": {"key": "value", "nested": {"deep": True}},
        }
        result = format_frontmatter(metadata)

        yaml_content = result.strip("---").strip()
        parsed = yaml.safe_load(yaml_content)
        assert parsed["metadata"]["key"] == "value"
        assert parsed["metadata"]["nested"]["deep"] is True

    def test_special_characters_in_values(self):
        """Special characters should be properly escaped."""
        metadata = {
            "title": 'Test: with "quotes" and colons',
            "content": "Line 1\nLine 2",
        }
        result = format_frontmatter(metadata)

        yaml_content = result.strip("---").strip()
        parsed = yaml.safe_load(yaml_content)
        assert 'with "quotes"' in parsed["title"]
        assert "Line 1\nLine 2" == parsed["content"]

    def test_unicode_content(self):
        """Unicode content should be preserved."""
        metadata = {
            "title": "日本語タイトル",
            "emoji": "🎉🚀",
        }
        result = format_frontmatter(metadata)

        yaml_content = result.strip("---").strip()
        parsed = yaml.safe_load(yaml_content)
        assert parsed["title"] == "日本語タイトル"
        assert parsed["emoji"] == "🎉🚀"

    def test_empty_metadata(self):
        """Empty metadata should produce valid empty frontmatter."""
        result = format_frontmatter({})

        assert result.startswith("---\n")
        assert result.endswith("---")
        yaml_content = result.strip("---").strip()
        # Empty YAML parses as None or empty dict
        parsed = yaml.safe_load(yaml_content)
        assert parsed is None or parsed == {}

    def test_none_values(self):
        """None values should be serialized as null."""
        metadata = {"title": "Test", "optional_field": None}
        result = format_frontmatter(metadata)

        yaml_content = result.strip("---").strip()
        parsed = yaml.safe_load(yaml_content)
        assert parsed["optional_field"] is None

    def test_boolean_values(self):
        """Boolean values should be serialized correctly."""
        metadata = {"enabled": True, "disabled": False}
        result = format_frontmatter(metadata)

        yaml_content = result.strip("---").strip()
        parsed = yaml.safe_load(yaml_content)
        assert parsed["enabled"] is True
        assert parsed["disabled"] is False

    def test_numeric_values(self):
        """Numeric values should be preserved."""
        metadata = {"count": 42, "score": 3.14, "negative": -10}
        result = format_frontmatter(metadata)

        yaml_content = result.strip("---").strip()
        parsed = yaml.safe_load(yaml_content)
        assert parsed["count"] == 42
        assert parsed["score"] == 3.14
        assert parsed["negative"] == -10

    def test_date_string(self):
        """Date strings should be preserved as strings."""
        metadata = {"date": "2024-12-07", "datetime": "2024-12-07T10:30:00"}
        result = format_frontmatter(metadata)

        yaml_content = result.strip("---").strip()
        parsed = yaml.safe_load(yaml_content)
        # YAML may parse dates as datetime objects, but we accept either
        assert "2024-12-07" in str(parsed["date"])


class TestGenerateItemId:
    """Tests for generate_item_id() function."""

    def test_consistent_id(self):
        """Same input should produce same ID."""
        item = {"type": "theme", "title": "Test Theme"}
        id1 = generate_item_id(item, "claude", "2024-12-07")
        id2 = generate_item_id(item, "claude", "2024-12-07")
        assert id1 == id2

    def test_different_inputs_different_ids(self):
        """Different inputs should produce different IDs."""
        item = {"type": "theme", "title": "Test Theme"}
        id1 = generate_item_id(item, "claude", "2024-12-07")
        id2 = generate_item_id(item, "chatgpt", "2024-12-07")
        id3 = generate_item_id(item, "claude", "2024-12-08")
        assert id1 != id2
        assert id1 != id3
        assert id2 != id3

    def test_id_length(self):
        """ID should be 12 characters (first 12 of SHA-256)."""
        item = {"type": "theme", "title": "Test"}
        result = generate_item_id(item, "claude", "2024-12-07")
        assert len(result) == 12

    def test_id_is_hex(self):
        """ID should be hexadecimal."""
        item = {"type": "theme", "title": "Test"}
        result = generate_item_id(item, "claude", "2024-12-07")
        assert all(c in "0123456789abcdef" for c in result)


class TestWriteStagedItem:
    """Tests for write_staged_item() function."""

    @pytest.fixture
    def sample_item(self):
        """Return a sample extracted item."""
        return {
            "type": "theme",
            "title": "Gumroad Launch Strategy",
            "content": "A comprehensive strategy for launching on Gumroad.",
            "key_quote": "We need to focus on the initial launch momentum.",
            "related_themes": ["[[Product Launch]]", "[[Marketing]]"],
            "confidence": "high",
        }

    def test_creates_file(self, sample_item, tmp_path):
        """Should create a markdown file in staging directory."""
        result = write_staged_item(
            item=sample_item,
            source="claude",
            source_date="2024-12-07",
            source_file="00-Inbox/claude/test.txt",
            staging_dir=tmp_path,
        )

        assert result.exists()
        assert result.suffix == ".md"
        assert result.parent == tmp_path

    def test_filename_format(self, sample_item, tmp_path):
        """Filename should follow type-title-id.md format."""
        result = write_staged_item(
            item=sample_item,
            source="claude",
            source_date="2024-12-07",
            source_file="test.txt",
            staging_dir=tmp_path,
        )

        filename = result.name
        # Should start with type
        assert filename.startswith("theme-")
        # Should end with .md
        assert filename.endswith(".md")
        # Should contain sanitized title
        assert "gumroad-launch-strategy" in filename

    def test_content_structure(self, sample_item, tmp_path):
        """File content should have frontmatter, title, content, and sections."""
        result = write_staged_item(
            item=sample_item,
            source="claude",
            source_date="2024-12-07",
            source_file="test.txt",
            staging_dir=tmp_path,
        )

        content = result.read_text()

        # Should have frontmatter
        assert content.startswith("---\n")
        assert "---\n\n#" in content

        # Should have main heading
        assert "# Gumroad Launch Strategy" in content

        # Should have item content
        assert "A comprehensive strategy for launching on Gumroad." in content

        # Should have key quote section
        assert "## Key Quote" in content
        assert "> We need to focus on the initial launch momentum." in content

        # Should have review notes section
        assert "## Review Notes" in content

        # Should have actions section
        assert "## Actions" in content
        assert "- [ ] Review and route to appropriate folder" in content

    def test_frontmatter_contains_metadata(self, sample_item, tmp_path):
        """Frontmatter should contain all required metadata."""
        result = write_staged_item(
            item=sample_item,
            source="claude",
            source_date="2024-12-07",
            source_file="test.txt",
            staging_dir=tmp_path,
        )

        content = result.read_text()

        # Extract frontmatter
        frontmatter_match = re.search(r"^---\n(.+?)\n---", content, re.DOTALL)
        assert frontmatter_match
        frontmatter = yaml.safe_load(frontmatter_match.group(1))

        assert frontmatter["title"] == "Gumroad Launch Strategy"
        assert frontmatter["type"] == "theme"
        assert frontmatter["source"] == "claude"
        assert frontmatter["source_date"] == "2024-12-07"
        assert frontmatter["source_file"] == "test.txt"
        assert frontmatter["related_themes"] == ["[[Product Launch]]", "[[Marketing]]"]
        assert frontmatter["confidence"] == "high"
        assert frontmatter["status"] == "staged"
        assert "created" in frontmatter
        assert "id" in frontmatter

    def test_missing_optional_fields(self, tmp_path):
        """Should handle missing optional fields gracefully."""
        item = {
            "type": "insight",
            "title": "Simple Insight",
            "content": "Just a simple insight.",
            # No key_quote, related_themes, or confidence
        }

        result = write_staged_item(
            item=item,
            source="gemini",
            source_date="2024-12-07",
            source_file="test.txt",
            staging_dir=tmp_path,
        )

        content = result.read_text()

        # Should have default key quote
        assert "> No quote captured" in content

        # Frontmatter should have defaults
        frontmatter_match = re.search(r"^---\n(.+?)\n---", content, re.DOTALL)
        frontmatter = yaml.safe_load(frontmatter_match.group(1))
        assert frontmatter["related_themes"] == []
        assert frontmatter["confidence"] == "medium"

    def test_unicode_content(self, tmp_path):
        """Should handle unicode content correctly."""
        item = {
            "type": "theme",
            "title": "日本語のテーマ",
            "content": "コンテンツは日本語です 🎉",
            "key_quote": "重要な引用",
        }

        result = write_staged_item(
            item=item,
            source="claude",
            source_date="2024-12-07",
            source_file="test.txt",
            staging_dir=tmp_path,
        )

        content = result.read_text(encoding="utf-8")
        assert "日本語のテーマ" in content
        assert "コンテンツは日本語です 🎉" in content
        assert "重要な引用" in content

    def test_returns_filepath(self, sample_item, tmp_path):
        """Should return Path object to created file."""
        result = write_staged_item(
            item=sample_item,
            source="claude",
            source_date="2024-12-07",
            source_file="test.txt",
            staging_dir=tmp_path,
        )

        assert isinstance(result, Path)
        assert result.is_file()

    def test_different_item_types(self, tmp_path):
        """Should handle all item types correctly."""
        for item_type in ["theme", "decision", "action", "insight"]:
            item = {
                "type": item_type,
                "title": f"Test {item_type.title()}",
                "content": f"Content for {item_type}",
            }

            result = write_staged_item(
                item=item,
                source="claude",
                source_date="2024-12-07",
                source_file="test.txt",
                staging_dir=tmp_path,
            )

            assert result.name.startswith(f"{item_type}-")
            assert result.exists()


class TestWriteExtractionSummary:
    """Tests for write_extraction_summary() function."""

    @pytest.fixture
    def sample_extraction(self):
        """Return a sample extraction result."""
        return {
            "items": [
                {"type": "theme", "title": "Theme One"},
                {"type": "theme", "title": "Theme Two"},
                {"type": "decision", "title": "Decision A"},
                {"type": "action", "title": "Action Item"},
                {"type": "insight", "title": "Key Insight"},
            ],
            "conversation_summary": "This was a productive conversation about planning.",
            "primary_themes": ["[[Planning]]", "[[Strategy]]"],
        }

    def test_creates_summary_file(self, sample_extraction, tmp_path):
        """Should create a summary markdown file."""
        result = write_extraction_summary(
            extraction=sample_extraction,
            source="claude",
            source_date="2024-12-07",
            source_file="test.txt",
            staging_dir=tmp_path,
        )

        assert result.exists()
        assert result.suffix == ".md"

    def test_filename_format(self, sample_extraction, tmp_path):
        """Filename should follow _summary-source-date.md format."""
        result = write_extraction_summary(
            extraction=sample_extraction,
            source="claude",
            source_date="2024-12-07",
            source_file="test.txt",
            staging_dir=tmp_path,
        )

        assert result.name == "_summary-claude-2024-12-07.md"

    def test_frontmatter_content(self, sample_extraction, tmp_path):
        """Frontmatter should contain extraction metadata."""
        result = write_extraction_summary(
            extraction=sample_extraction,
            source="claude",
            source_date="2024-12-07",
            source_file="test.txt",
            staging_dir=tmp_path,
        )

        content = result.read_text()

        assert "type: extraction-summary" in content
        assert "source: claude" in content
        assert "source_date: 2024-12-07" in content
        assert "source_file: test.txt" in content
        assert "item_count: 5" in content
        assert "processed_at:" in content

    def test_conversation_summary_included(self, sample_extraction, tmp_path):
        """Should include conversation summary."""
        result = write_extraction_summary(
            extraction=sample_extraction,
            source="claude",
            source_date="2024-12-07",
            source_file="test.txt",
            staging_dir=tmp_path,
        )

        content = result.read_text()
        assert "## Conversation Summary" in content
        assert "This was a productive conversation about planning." in content

    def test_primary_themes_listed(self, sample_extraction, tmp_path):
        """Should list primary themes."""
        result = write_extraction_summary(
            extraction=sample_extraction,
            source="claude",
            source_date="2024-12-07",
            source_file="test.txt",
            staging_dir=tmp_path,
        )

        content = result.read_text()
        assert "## Primary Themes" in content
        assert "- [[Planning]]" in content
        assert "- [[Strategy]]" in content

    def test_items_grouped_by_type(self, sample_extraction, tmp_path):
        """Should group extracted items by type."""
        result = write_extraction_summary(
            extraction=sample_extraction,
            source="claude",
            source_date="2024-12-07",
            source_file="test.txt",
            staging_dir=tmp_path,
        )

        content = result.read_text()

        # Should have sections for each type
        assert "### Themes (2)" in content
        assert "### Decisions (1)" in content
        assert "### Actions (1)" in content
        assert "### Insights (1)" in content

        # Should list items under each section
        assert "- Theme One" in content
        assert "- Theme Two" in content
        assert "- Decision A" in content
        assert "- Action Item" in content
        assert "- Key Insight" in content

    def test_empty_extraction(self, tmp_path):
        """Should handle extraction with no items."""
        extraction = {
            "items": [],
            "conversation_summary": "Nothing useful.",
            "primary_themes": [],
        }

        result = write_extraction_summary(
            extraction=extraction,
            source="claude",
            source_date="2024-12-07",
            source_file="test.txt",
            staging_dir=tmp_path,
        )

        content = result.read_text()
        assert "item_count: 0" in content
        assert "Nothing useful." in content

    def test_missing_optional_fields(self, tmp_path):
        """Should handle missing optional fields."""
        extraction = {"items": [{"type": "theme", "title": "Single Theme"}]}

        result = write_extraction_summary(
            extraction=extraction,
            source="claude",
            source_date="2024-12-07",
            source_file="test.txt",
            staging_dir=tmp_path,
        )

        content = result.read_text()
        assert "No summary available" in content
        assert "### Themes (1)" in content
