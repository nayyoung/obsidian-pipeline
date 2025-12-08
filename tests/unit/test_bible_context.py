"""
Tests for load_bible_context() function.

MEDIUM PRIORITY: Context injection for knowledge extraction.
"""

import pytest
from pathlib import Path
from unittest.mock import patch

from pipeline import load_bible_context


class TestLoadBibleContext:
    """Tests for load_bible_context() function."""

    @pytest.fixture
    def mock_config(self, temp_vault, monkeypatch):
        """Mock CONFIG with temp vault paths."""
        test_config = {
            "vault_path": temp_vault,
            "bible_files": [
                "06-Bibles/bible1.md",
                "06-Bibles/bible2.md",
            ],
        }
        monkeypatch.setattr("pipeline.CONFIG", test_config)
        return test_config

    def test_loads_single_bible_file(self, temp_vault, monkeypatch):
        """Should load content from a single Bible file."""
        bible_dir = temp_vault / "06-Bibles"
        bible_dir.mkdir(parents=True, exist_ok=True)
        bible_file = bible_dir / "test_bible.md"
        bible_file.write_text("# Project Bible\n\nThis is the project context.")

        test_config = {
            "vault_path": temp_vault,
            "bible_files": ["06-Bibles/test_bible.md"],
        }
        monkeypatch.setattr("pipeline.CONFIG", test_config)

        result = load_bible_context()

        assert "# Project Bible" in result
        assert "This is the project context." in result
        assert "### test_bible.md" in result

    def test_loads_multiple_bible_files(self, mock_config, temp_vault):
        """Should concatenate content from multiple Bible files."""
        bible_dir = temp_vault / "06-Bibles"
        bible_dir.mkdir(parents=True, exist_ok=True)

        (bible_dir / "bible1.md").write_text("Content from Bible 1")
        (bible_dir / "bible2.md").write_text("Content from Bible 2")

        result = load_bible_context()

        assert "Content from Bible 1" in result
        assert "Content from Bible 2" in result
        assert "### bible1.md" in result
        assert "### bible2.md" in result
        # Files should be separated by divider
        assert "---" in result

    def test_missing_file_skipped(self, temp_vault, monkeypatch, caplog):
        """Should skip missing files and continue with others."""
        bible_dir = temp_vault / "06-Bibles"
        bible_dir.mkdir(parents=True, exist_ok=True)
        (bible_dir / "exists.md").write_text("I exist!")

        test_config = {
            "vault_path": temp_vault,
            "bible_files": [
                "06-Bibles/exists.md",
                "06-Bibles/missing.md",  # Doesn't exist
            ],
        }
        monkeypatch.setattr("pipeline.CONFIG", test_config)

        result = load_bible_context()

        assert "I exist!" in result
        assert "missing.md" not in result

    def test_all_files_missing_returns_empty(self, temp_vault, monkeypatch):
        """Should return empty string if no Bible files exist."""
        test_config = {
            "vault_path": temp_vault,
            "bible_files": [
                "06-Bibles/nonexistent1.md",
                "06-Bibles/nonexistent2.md",
            ],
        }
        monkeypatch.setattr("pipeline.CONFIG", test_config)

        result = load_bible_context()

        assert result == ""

    def test_empty_bible_files_list(self, temp_vault, monkeypatch):
        """Should return empty string if no Bible files configured."""
        test_config = {
            "vault_path": temp_vault,
            "bible_files": [],
        }
        monkeypatch.setattr("pipeline.CONFIG", test_config)

        result = load_bible_context()

        assert result == ""

    def test_unicode_content(self, temp_vault, monkeypatch):
        """Should handle unicode content in Bible files."""
        bible_dir = temp_vault / "06-Bibles"
        bible_dir.mkdir(parents=True, exist_ok=True)
        bible_file = bible_dir / "unicode.md"
        bible_file.write_text("# 日本語プロジェクト\n\nコンテンツ 🎉", encoding="utf-8")

        test_config = {
            "vault_path": temp_vault,
            "bible_files": ["06-Bibles/unicode.md"],
        }
        monkeypatch.setattr("pipeline.CONFIG", test_config)

        result = load_bible_context()

        assert "日本語プロジェクト" in result
        assert "コンテンツ 🎉" in result

    def test_large_bible_file(self, temp_vault, monkeypatch):
        """Should handle large Bible files."""
        bible_dir = temp_vault / "06-Bibles"
        bible_dir.mkdir(parents=True, exist_ok=True)
        bible_file = bible_dir / "large.md"
        large_content = "# Large Bible\n\n" + ("Lorem ipsum dolor sit amet. " * 1000)
        bible_file.write_text(large_content)

        test_config = {
            "vault_path": temp_vault,
            "bible_files": ["06-Bibles/large.md"],
        }
        monkeypatch.setattr("pipeline.CONFIG", test_config)

        result = load_bible_context()

        assert len(result) > 10000
        assert "Lorem ipsum" in result

    def test_file_with_special_yaml_chars(self, temp_vault, monkeypatch):
        """Should handle files with YAML-like content."""
        bible_dir = temp_vault / "06-Bibles"
        bible_dir.mkdir(parents=True, exist_ok=True)
        bible_file = bible_dir / "yaml_content.md"
        bible_file.write_text(
            "---\n"
            "title: Project Bible\n"
            "---\n\n"
            "# Goals:\n- Item 1\n- Item 2"
        )

        test_config = {
            "vault_path": temp_vault,
            "bible_files": ["06-Bibles/yaml_content.md"],
        }
        monkeypatch.setattr("pipeline.CONFIG", test_config)

        result = load_bible_context()

        assert "title: Project Bible" in result
        assert "# Goals:" in result

    def test_read_error_handled_gracefully(self, temp_vault, monkeypatch, caplog):
        """Should handle read errors gracefully."""
        bible_dir = temp_vault / "06-Bibles"
        bible_dir.mkdir(parents=True, exist_ok=True)
        bible_file = bible_dir / "test.md"
        bible_file.write_text("Content")

        test_config = {
            "vault_path": temp_vault,
            "bible_files": ["06-Bibles/test.md"],
        }
        monkeypatch.setattr("pipeline.CONFIG", test_config)

        # Mock open to raise an error
        original_open = open

        def mock_open_error(path, *args, **kwargs):
            if "test.md" in str(path):
                raise IOError("Permission denied")
            return original_open(path, *args, **kwargs)

        with patch("builtins.open", mock_open_error):
            result = load_bible_context()

        # Should return empty on error
        assert result == ""

    def test_separator_between_files(self, mock_config, temp_vault):
        """Multiple files should be separated by horizontal rule."""
        bible_dir = temp_vault / "06-Bibles"
        bible_dir.mkdir(parents=True, exist_ok=True)

        (bible_dir / "bible1.md").write_text("First file")
        (bible_dir / "bible2.md").write_text("Second file")

        result = load_bible_context()

        # Should have separator between files
        assert "\n\n---\n\n" in result
