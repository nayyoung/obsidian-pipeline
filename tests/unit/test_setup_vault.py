"""
Tests for setup_vault() function.

LOW PRIORITY: Vault initialization script.
"""

import pytest
from pathlib import Path
from unittest.mock import patch
from datetime import datetime


class TestSetupVault:
    """Tests for setup_vault() function."""

    @pytest.fixture
    def mock_vault_path(self, tmp_path, monkeypatch):
        """Mock VAULT_PATH to use a temp directory."""
        vault_path = tmp_path / "TestVault"
        monkeypatch.setattr("setup_vault.VAULT_PATH", vault_path)
        return vault_path

    def test_creates_all_folders(self, mock_vault_path):
        """Should create all required folder structure."""
        from setup_vault import setup_vault, FOLDERS

        setup_vault()

        for folder in FOLDERS:
            folder_path = mock_vault_path / folder
            assert folder_path.exists(), f"Missing folder: {folder}"
            assert folder_path.is_dir()

    def test_creates_inbox_subfolders(self, mock_vault_path):
        """Should create inbox subfolders for each source."""
        from setup_vault import setup_vault

        setup_vault()

        assert (mock_vault_path / "00-Inbox" / "claude").exists()
        assert (mock_vault_path / "00-Inbox" / "chatgpt").exists()
        assert (mock_vault_path / "00-Inbox" / "gemini").exists()

    def test_creates_processing_folders(self, mock_vault_path):
        """Should create processing stage folders."""
        from setup_vault import setup_vault

        setup_vault()

        assert (mock_vault_path / "01-Processed").exists()
        assert (mock_vault_path / "02-Themes").exists()
        assert (mock_vault_path / "03-Decisions").exists()
        assert (mock_vault_path / "04-Actions").exists()
        assert (mock_vault_path / "05-Conflicts").exists()

    def test_creates_bibles_folder(self, mock_vault_path):
        """Should create Bibles folder."""
        from setup_vault import setup_vault

        setup_vault()

        assert (mock_vault_path / "06-Bibles").exists()

    def test_creates_meta_folder(self, mock_vault_path):
        """Should create meta folder."""
        from setup_vault import setup_vault

        setup_vault()

        assert (mock_vault_path / "_meta").exists()

    def test_creates_starter_bible(self, mock_vault_path):
        """Should create starter Bible file."""
        from setup_vault import setup_vault

        setup_vault()

        bible_path = mock_vault_path / "06-Bibles" / "Gumroad_Launch_Bible.md"
        assert bible_path.exists()

        content = bible_path.read_text()
        assert "# Gumroad Launch Bible" in content
        assert "title: Gumroad Launch Bible" in content
        assert "type: bible" in content

    def test_bible_contains_date(self, mock_vault_path):
        """Starter Bible should contain creation date."""
        from setup_vault import setup_vault

        setup_vault()

        bible_path = mock_vault_path / "06-Bibles" / "Gumroad_Launch_Bible.md"
        content = bible_path.read_text()

        today = datetime.now().strftime("%Y-%m-%d")
        assert f"created: {today}" in content

    def test_bible_contains_sections(self, mock_vault_path):
        """Starter Bible should contain all template sections."""
        from setup_vault import setup_vault

        setup_vault()

        bible_path = mock_vault_path / "06-Bibles" / "Gumroad_Launch_Bible.md"
        content = bible_path.read_text()

        assert "## Current Status" in content
        assert "## Goals" in content
        assert "## Key Decisions Made" in content
        assert "## Open Questions" in content
        assert "## Resources" in content

    def test_does_not_overwrite_existing_bible(self, mock_vault_path):
        """Should not overwrite existing Bible file."""
        from setup_vault import setup_vault

        # Create folder and existing Bible
        bible_dir = mock_vault_path / "06-Bibles"
        bible_dir.mkdir(parents=True)
        bible_path = bible_dir / "Gumroad_Launch_Bible.md"
        bible_path.write_text("# My Custom Bible\n\nCustom content")

        setup_vault()

        # Should preserve custom content
        content = bible_path.read_text()
        assert "My Custom Bible" in content
        assert "Custom content" in content

    def test_creates_gitignore(self, mock_vault_path):
        """Should create .gitignore file."""
        from setup_vault import setup_vault

        setup_vault()

        gitignore_path = mock_vault_path / ".gitignore"
        assert gitignore_path.exists()

    def test_gitignore_content(self, mock_vault_path):
        """Gitignore should contain appropriate patterns."""
        from setup_vault import setup_vault

        setup_vault()

        gitignore_path = mock_vault_path / ".gitignore"
        content = gitignore_path.read_text()

        assert ".obsidian/workspace.json" in content
        assert ".DS_Store" in content
        assert "*.bak" in content

    def test_does_not_overwrite_existing_gitignore(self, mock_vault_path):
        """Should not overwrite existing .gitignore."""
        from setup_vault import setup_vault

        # Create existing gitignore
        mock_vault_path.mkdir(parents=True)
        gitignore_path = mock_vault_path / ".gitignore"
        gitignore_path.write_text("# My custom gitignore\n*.custom")

        setup_vault()

        content = gitignore_path.read_text()
        assert "My custom gitignore" in content
        assert "*.custom" in content

    def test_handles_existing_folders(self, mock_vault_path):
        """Should handle already existing folders gracefully."""
        from setup_vault import setup_vault

        # Pre-create some folders
        (mock_vault_path / "00-Inbox" / "claude").mkdir(parents=True)
        (mock_vault_path / "01-Processed").mkdir(parents=True)

        # Should not raise an error
        setup_vault()

        # All folders should exist
        assert (mock_vault_path / "00-Inbox" / "claude").exists()
        assert (mock_vault_path / "01-Processed").exists()

    def test_continues_on_folder_error(self, mock_vault_path, monkeypatch):
        """Should continue creating other folders if one fails."""
        from setup_vault import setup_vault

        # Create a file where a folder should be (causes error)
        mock_vault_path.mkdir(parents=True)
        conflict_file = mock_vault_path / "01-Processed"
        conflict_file.write_text("I'm a file, not a folder")

        # Should not raise, should continue with other folders
        setup_vault()

        # Other folders should still be created
        assert (mock_vault_path / "00-Inbox" / "claude").exists()
        assert (mock_vault_path / "02-Themes").exists()

    def test_idempotent_execution(self, mock_vault_path):
        """Running setup multiple times should be safe."""
        from setup_vault import setup_vault

        # Run twice
        setup_vault()
        setup_vault()

        # Everything should still be there
        assert (mock_vault_path / "00-Inbox" / "claude").exists()
        assert (mock_vault_path / "06-Bibles" / "Gumroad_Launch_Bible.md").exists()
        assert (mock_vault_path / ".gitignore").exists()
