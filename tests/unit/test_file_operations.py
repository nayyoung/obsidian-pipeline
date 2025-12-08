"""
Tests for file operation functions: get_file_hash() and find_new_files().

HIGH PRIORITY: File I/O and change detection logic.
"""

import hashlib
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from pipeline import get_file_hash, find_new_files, CONFIG


class TestGetFileHash:
    """Tests for get_file_hash() function."""

    def test_returns_sha256_hash(self, tmp_path):
        """Should return a valid SHA-256 hash."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("Hello, World!")

        result = get_file_hash(file_path)

        # SHA-256 produces 64 hex characters
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_consistent_hash(self, tmp_path):
        """Same file should always produce same hash."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("Consistent content")

        hash1 = get_file_hash(file_path)
        hash2 = get_file_hash(file_path)

        assert hash1 == hash2

    def test_different_content_different_hash(self, tmp_path):
        """Different content should produce different hashes."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"

        file1.write_text("Content A")
        file2.write_text("Content B")

        hash1 = get_file_hash(file1)
        hash2 = get_file_hash(file2)

        assert hash1 != hash2

    def test_matches_hashlib_sha256(self, tmp_path):
        """Hash should match direct hashlib calculation."""
        content = b"Test content for hashing"
        file_path = tmp_path / "test.txt"
        file_path.write_bytes(content)

        result = get_file_hash(file_path)
        expected = hashlib.sha256(content).hexdigest()

        assert result == expected

    def test_empty_file(self, tmp_path):
        """Empty file should return valid hash."""
        file_path = tmp_path / "empty.txt"
        file_path.touch()

        result = get_file_hash(file_path)

        # SHA-256 of empty content
        expected = hashlib.sha256(b"").hexdigest()
        assert result == expected
        assert len(result) == 64

    def test_binary_file(self, tmp_path):
        """Binary file should be hashed correctly."""
        file_path = tmp_path / "binary.bin"
        binary_content = bytes(range(256))
        file_path.write_bytes(binary_content)

        result = get_file_hash(file_path)

        expected = hashlib.sha256(binary_content).hexdigest()
        assert result == expected

    def test_large_file(self, tmp_path):
        """Large file should be hashed (may be slow)."""
        file_path = tmp_path / "large.txt"
        # 1MB of data
        large_content = b"x" * (1024 * 1024)
        file_path.write_bytes(large_content)

        result = get_file_hash(file_path)

        expected = hashlib.sha256(large_content).hexdigest()
        assert result == expected

    def test_unicode_content(self, tmp_path):
        """File with unicode content should hash correctly."""
        file_path = tmp_path / "unicode.txt"
        file_path.write_text("Hello 日本語 🎉", encoding="utf-8")

        result = get_file_hash(file_path)

        expected = hashlib.sha256("Hello 日本語 🎉".encode("utf-8")).hexdigest()
        assert result == expected

    def test_nonexistent_file_raises(self, tmp_path):
        """Non-existent file should raise IOError."""
        file_path = tmp_path / "does_not_exist.txt"

        with pytest.raises((IOError, OSError)):
            get_file_hash(file_path)

    def test_permission_error(self, tmp_path, monkeypatch):
        """Permission error should be raised."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("content")

        # Mock open to raise permission error
        def mock_open(*args, **kwargs):
            raise PermissionError("Permission denied")

        monkeypatch.setattr("builtins.open", mock_open)

        with pytest.raises((IOError, OSError, PermissionError)):
            get_file_hash(file_path)


class TestFindNewFiles:
    """Tests for find_new_files() function."""

    @pytest.fixture
    def mock_config(self, temp_vault, monkeypatch):
        """Mock the CONFIG global with temp vault paths."""
        test_config = {
            "vault_path": temp_vault,
            "inbox_paths": {
                "claude": "00-Inbox/claude",
                "chatgpt": "00-Inbox/chatgpt",
                "gemini": "00-Inbox/gemini",
            },
            "staging_path": "01-Processed",
            "meta_path": "_meta",
        }
        monkeypatch.setattr("pipeline.CONFIG", test_config)
        return test_config

    def test_finds_new_txt_files(self, mock_config, temp_vault):
        """Should find new .txt files in inbox folders."""
        # Create a test file
        inbox = temp_vault / "00-Inbox" / "claude"
        test_file = inbox / "test-conversation.txt"
        test_file.write_text("Test conversation content")

        empty_log = {"processed_files": {}, "last_run": None}
        result = find_new_files(empty_log)

        assert len(result) == 1
        assert result[0]["path"] == test_file
        assert result[0]["source"] == "claude"
        assert "hash" in result[0]

    def test_finds_files_in_multiple_inboxes(self, mock_config, temp_vault):
        """Should find files across all inbox folders."""
        # Create files in different inboxes
        (temp_vault / "00-Inbox" / "claude" / "claude-file.txt").write_text("claude")
        (temp_vault / "00-Inbox" / "chatgpt" / "chatgpt-file.txt").write_text("chatgpt")
        (temp_vault / "00-Inbox" / "gemini" / "gemini-file.txt").write_text("gemini")

        empty_log = {"processed_files": {}, "last_run": None}
        result = find_new_files(empty_log)

        assert len(result) == 3
        sources = {f["source"] for f in result}
        assert sources == {"claude", "chatgpt", "gemini"}

    def test_skips_already_processed_files(self, mock_config, temp_vault):
        """Should skip files that are already processed with same hash."""
        inbox = temp_vault / "00-Inbox" / "claude"
        test_file = inbox / "processed-file.txt"
        test_file.write_text("Already processed content")

        # Calculate the hash
        file_hash = hashlib.sha256(b"Already processed content").hexdigest()

        # Log shows file already processed
        log = {
            "processed_files": {
                str(test_file): {
                    "hash": file_hash,
                    "processed_at": "2024-12-01T10:00:00",
                    "source": "claude",
                }
            },
            "last_run": "2024-12-01T10:00:00",
        }

        result = find_new_files(log)
        assert len(result) == 0

    def test_detects_modified_files(self, mock_config, temp_vault):
        """Should detect files that have been modified since processing."""
        inbox = temp_vault / "00-Inbox" / "claude"
        test_file = inbox / "modified-file.txt"
        test_file.write_text("New content after modification")

        # Log has old hash
        log = {
            "processed_files": {
                str(test_file): {
                    "hash": "old_hash_that_no_longer_matches",
                    "processed_at": "2024-12-01T10:00:00",
                    "source": "claude",
                }
            },
            "last_run": "2024-12-01T10:00:00",
        }

        result = find_new_files(log)
        assert len(result) == 1
        assert result[0]["path"] == test_file

    def test_ignores_non_txt_files(self, mock_config, temp_vault):
        """Should only find .txt files, ignore other extensions."""
        inbox = temp_vault / "00-Inbox" / "claude"

        # Create various file types
        (inbox / "file.txt").write_text("text file")
        (inbox / "file.md").write_text("markdown file")
        (inbox / "file.json").write_text("{}")
        (inbox / "file.pdf").write_bytes(b"pdf content")

        empty_log = {"processed_files": {}, "last_run": None}
        result = find_new_files(empty_log)

        assert len(result) == 1
        assert result[0]["path"].suffix == ".txt"

    def test_creates_missing_inbox_directory(self, mock_config, temp_vault, caplog):
        """Should create inbox directory if it doesn't exist."""
        # Remove one inbox
        new_inbox = temp_vault / "00-Inbox" / "new_source"
        # Add it to config
        mock_config["inbox_paths"]["new_source"] = "00-Inbox/new_source"

        empty_log = {"processed_files": {}, "last_run": None}
        result = find_new_files(empty_log)

        # Directory should be created
        assert new_inbox.exists()

    def test_handles_file_read_errors_gracefully(self, mock_config, temp_vault, monkeypatch):
        """Should skip files that can't be read and continue."""
        inbox = temp_vault / "00-Inbox" / "claude"
        good_file = inbox / "good-file.txt"
        bad_file = inbox / "bad-file.txt"

        good_file.write_text("good content")
        bad_file.write_text("bad content")

        # Mock get_file_hash to fail for bad file
        original_hash = get_file_hash

        def mock_hash(filepath):
            if "bad-file" in str(filepath):
                raise IOError("Cannot read file")
            return original_hash(filepath)

        monkeypatch.setattr("pipeline.get_file_hash", mock_hash)

        empty_log = {"processed_files": {}, "last_run": None}
        result = find_new_files(empty_log)

        # Should still find the good file
        assert len(result) == 1
        assert "good-file" in str(result[0]["path"])

    def test_empty_inbox_returns_empty_list(self, mock_config, temp_vault):
        """Empty inbox folders should return empty list."""
        empty_log = {"processed_files": {}, "last_run": None}
        result = find_new_files(empty_log)
        assert result == []

    def test_returns_correct_file_info_structure(self, mock_config, temp_vault):
        """Each result should have path, source, and hash keys."""
        inbox = temp_vault / "00-Inbox" / "claude"
        test_file = inbox / "test.txt"
        test_file.write_text("content")

        empty_log = {"processed_files": {}, "last_run": None}
        result = find_new_files(empty_log)

        assert len(result) == 1
        file_info = result[0]
        assert "path" in file_info
        assert "source" in file_info
        assert "hash" in file_info
        assert isinstance(file_info["path"], Path)
        assert isinstance(file_info["source"], str)
        assert isinstance(file_info["hash"], str)

    def test_handles_subdirectories_in_inbox(self, mock_config, temp_vault):
        """Files in subdirectories of inbox should not be found (glob *.txt is flat)."""
        inbox = temp_vault / "00-Inbox" / "claude"
        subdir = inbox / "subdir"
        subdir.mkdir()

        # File in inbox root
        (inbox / "root-file.txt").write_text("root")
        # File in subdirectory
        (subdir / "sub-file.txt").write_text("sub")

        empty_log = {"processed_files": {}, "last_run": None}
        result = find_new_files(empty_log)

        # Only root file should be found (*.txt doesn't recurse)
        assert len(result) == 1
        assert "root-file" in str(result[0]["path"])


class TestFindNewFilesEdgeCases:
    """Edge cases for find_new_files."""

    @pytest.fixture
    def mock_config(self, temp_vault, monkeypatch):
        """Mock the CONFIG global with temp vault paths."""
        test_config = {
            "vault_path": temp_vault,
            "inbox_paths": {
                "claude": "00-Inbox/claude",
            },
            "staging_path": "01-Processed",
            "meta_path": "_meta",
        }
        monkeypatch.setattr("pipeline.CONFIG", test_config)
        return test_config

    def test_unicode_filename(self, mock_config, temp_vault):
        """Files with unicode names should be handled."""
        inbox = temp_vault / "00-Inbox" / "claude"
        try:
            unicode_file = inbox / "日本語ファイル.txt"
            unicode_file.write_text("content")

            empty_log = {"processed_files": {}, "last_run": None}
            result = find_new_files(empty_log)

            assert len(result) == 1
        except OSError:
            pytest.skip("Unicode filenames not supported")

    def test_spaces_in_filename(self, mock_config, temp_vault):
        """Files with spaces in names should be handled."""
        inbox = temp_vault / "00-Inbox" / "claude"
        spaced_file = inbox / "file with spaces.txt"
        spaced_file.write_text("content")

        empty_log = {"processed_files": {}, "last_run": None}
        result = find_new_files(empty_log)

        assert len(result) == 1
        assert "file with spaces" in str(result[0]["path"])

    def test_special_chars_in_filename(self, mock_config, temp_vault):
        """Files with special characters should be handled."""
        inbox = temp_vault / "00-Inbox" / "claude"
        special_file = inbox / "file-with_special.chars.txt"
        special_file.write_text("content")

        empty_log = {"processed_files": {}, "last_run": None}
        result = find_new_files(empty_log)

        assert len(result) == 1
