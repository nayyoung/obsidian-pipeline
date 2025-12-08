"""
Integration tests for process_file() function.

MEDIUM PRIORITY: End-to-end processing of conversation files.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pipeline import process_file


class TestProcessFileDryRun:
    """Tests for process_file() in dry run mode."""

    @pytest.fixture
    def file_info(self, temp_vault):
        """Create a test file and return file_info dict."""
        inbox = temp_vault / "00-Inbox" / "claude"
        inbox.mkdir(parents=True, exist_ok=True)
        test_file = inbox / "2024-12-07-test-conversation.txt"
        test_file.write_text("User: Hello\n\nAssistant: Hi there!")
        return {
            "path": test_file,
            "source": "claude",
            "hash": "abc123",
        }

    def test_dry_run_returns_true(self, file_info, temp_vault, monkeypatch):
        """Dry run should return True without making API calls."""
        test_config = {
            "vault_path": temp_vault,
            "staging_path": "01-Processed",
        }
        monkeypatch.setattr("pipeline.CONFIG", test_config)

        result = process_file(
            file_info=file_info,
            bible_context="",
            client=None,  # No client needed for dry run
            dry_run=True,
        )

        assert result is True

    def test_dry_run_does_not_create_files(self, file_info, temp_vault, monkeypatch):
        """Dry run should not create any output files."""
        test_config = {
            "vault_path": temp_vault,
            "staging_path": "01-Processed",
        }
        monkeypatch.setattr("pipeline.CONFIG", test_config)

        staging_dir = temp_vault / "01-Processed"
        initial_files = list(staging_dir.glob("**/*")) if staging_dir.exists() else []

        process_file(
            file_info=file_info,
            bible_context="",
            client=None,
            dry_run=True,
        )

        final_files = list(staging_dir.glob("**/*")) if staging_dir.exists() else []
        assert len(final_files) == len(initial_files)


class TestProcessFileWithMockedAPI:
    """Tests for process_file() with mocked API."""

    @pytest.fixture
    def mock_config(self, temp_vault, monkeypatch):
        """Set up test configuration."""
        test_config = {
            "vault_path": temp_vault,
            "staging_path": "01-Processed",
            "model": "test-model",
            "max_tokens": 4096,
        }
        monkeypatch.setattr("pipeline.CONFIG", test_config)
        return test_config

    @pytest.fixture
    def file_info(self, temp_vault):
        """Create a test file and return file_info dict."""
        inbox = temp_vault / "00-Inbox" / "claude"
        inbox.mkdir(parents=True, exist_ok=True)
        test_file = inbox / "2024-12-07-test-conversation.txt"
        test_file.write_text(
            "User: What should our launch strategy be?\n\n"
            "Assistant: Here's a comprehensive approach..."
        )
        return {
            "path": test_file,
            "source": "claude",
            "hash": "abc123",
        }

    @pytest.fixture
    def mock_extraction_response(self):
        """Return a mock successful extraction."""
        return {
            "items": [
                {
                    "type": "theme",
                    "title": "Launch Strategy",
                    "content": "A comprehensive launch approach.",
                    "key_quote": "Here's a comprehensive approach",
                    "related_themes": ["[[Product Launch]]"],
                    "confidence": "high",
                },
                {
                    "type": "action",
                    "title": "Create Marketing Plan",
                    "content": "Develop detailed marketing materials.",
                    "key_quote": "comprehensive approach",
                    "related_themes": ["[[Marketing]]"],
                    "confidence": "medium",
                },
            ],
            "conversation_summary": "Discussion about launch strategy.",
            "primary_themes": ["[[Launch Strategy]]"],
        }

    def test_successful_processing(
        self, mock_config, file_info, mock_extraction_response, temp_vault
    ):
        """Successful processing should create output files."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(text=json.dumps(mock_extraction_response))
        ]
        mock_client.messages.create.return_value = mock_response

        result = process_file(
            file_info=file_info,
            bible_context="Project context here",
            client=mock_client,
            dry_run=False,
        )

        assert result is True

        # Should have created staging directory
        staging_dir = temp_vault / "01-Processed" / "2024-12-07"
        assert staging_dir.exists()

        # Should have created item files
        md_files = list(staging_dir.glob("*.md"))
        # 2 items + 1 summary = 3 files
        assert len(md_files) == 3

        # Should have theme file
        theme_files = [f for f in md_files if f.name.startswith("theme-")]
        assert len(theme_files) == 1

        # Should have action file
        action_files = [f for f in md_files if f.name.startswith("action-")]
        assert len(action_files) == 1

        # Should have summary file
        summary_files = [f for f in md_files if f.name.startswith("_summary-")]
        assert len(summary_files) == 1

    def test_api_error_returns_false(self, mock_config, file_info, temp_vault):
        """API error should return False."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(text=json.dumps({"items": [], "error": "API failed"}))
        ]
        mock_client.messages.create.return_value = mock_response

        result = process_file(
            file_info=file_info,
            bible_context="",
            client=mock_client,
            dry_run=False,
        )

        assert result is False

    def test_empty_extraction_still_succeeds(self, mock_config, file_info, temp_vault):
        """Empty extraction (no items) should still return True."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(
                text=json.dumps(
                    {
                        "items": [],
                        "conversation_summary": "Nothing interesting.",
                        "primary_themes": [],
                    }
                )
            )
        ]
        mock_client.messages.create.return_value = mock_response

        result = process_file(
            file_info=file_info,
            bible_context="",
            client=mock_client,
            dry_run=False,
        )

        assert result is True

        # Should still create summary file
        staging_dir = temp_vault / "01-Processed" / "2024-12-07"
        summary_files = list(staging_dir.glob("_summary-*.md"))
        assert len(summary_files) == 1

    def test_uses_correct_source_date_from_filename(
        self, mock_config, temp_vault, mock_extraction_response
    ):
        """Should extract date from filename for staging directory."""
        inbox = temp_vault / "00-Inbox" / "claude"
        inbox.mkdir(parents=True, exist_ok=True)
        test_file = inbox / "2024-01-15-specific-date.txt"
        test_file.write_text("User: Test\n\nAssistant: Response")

        file_info = {"path": test_file, "source": "claude", "hash": "xyz"}

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(text=json.dumps(mock_extraction_response))
        ]
        mock_client.messages.create.return_value = mock_response

        process_file(
            file_info=file_info,
            bible_context="",
            client=mock_client,
            dry_run=False,
        )

        # Staging directory should use date from filename
        staging_dir = temp_vault / "01-Processed" / "2024-01-15"
        assert staging_dir.exists()

    def test_bible_context_passed_to_api(
        self, mock_config, file_info, mock_extraction_response
    ):
        """Bible context should be passed to the API call."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(text=json.dumps(mock_extraction_response))
        ]
        mock_client.messages.create.return_value = mock_response

        bible_context = "# Project Bible\n\nImportant project context."

        process_file(
            file_info=file_info,
            bible_context=bible_context,
            client=mock_client,
            dry_run=False,
        )

        # Check the API was called with bible context in the prompt
        call_args = mock_client.messages.create.call_args
        user_message = call_args[1]["messages"][0]["content"]
        assert "Important project context" in user_message


class TestProcessFileErrorHandling:
    """Tests for error handling in process_file()."""

    @pytest.fixture
    def mock_config(self, temp_vault, monkeypatch):
        """Set up test configuration."""
        test_config = {
            "vault_path": temp_vault,
            "staging_path": "01-Processed",
            "model": "test-model",
            "max_tokens": 4096,
        }
        monkeypatch.setattr("pipeline.CONFIG", test_config)
        return test_config

    def test_missing_file_returns_false(self, mock_config, temp_vault):
        """Missing conversation file should return False."""
        file_info = {
            "path": temp_vault / "nonexistent.txt",
            "source": "claude",
            "hash": "abc",
        }

        result = process_file(
            file_info=file_info,
            bible_context="",
            client=MagicMock(),
            dry_run=False,
        )

        assert result is False

    def test_unreadable_file_returns_false(self, mock_config, temp_vault, monkeypatch):
        """Unreadable file should return False."""
        inbox = temp_vault / "00-Inbox" / "claude"
        inbox.mkdir(parents=True, exist_ok=True)
        test_file = inbox / "test.txt"
        test_file.write_text("Content")

        file_info = {"path": test_file, "source": "claude", "hash": "abc"}

        # Mock read_conversation to raise an error
        def mock_read_error(path):
            raise IOError("Permission denied")

        monkeypatch.setattr("pipeline.read_conversation", mock_read_error)

        result = process_file(
            file_info=file_info,
            bible_context="",
            client=MagicMock(),
            dry_run=False,
        )

        assert result is False

    def test_continues_on_item_write_error(
        self, mock_config, temp_vault, monkeypatch
    ):
        """Should continue processing even if one item fails to write."""
        inbox = temp_vault / "00-Inbox" / "claude"
        inbox.mkdir(parents=True, exist_ok=True)
        test_file = inbox / "2024-12-07-test.txt"
        test_file.write_text("Content")

        file_info = {"path": test_file, "source": "claude", "hash": "abc"}

        extraction = {
            "items": [
                {"type": "theme", "title": "Good Item", "content": "Works"},
                {"type": "action", "title": "Bad Item", "content": "Fails"},
            ],
            "conversation_summary": "Test",
            "primary_themes": [],
        }

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=json.dumps(extraction))]
        mock_client.messages.create.return_value = mock_response

        # Make write_staged_item fail for "Bad Item"
        original_write = None

        def mock_write(item, *args, **kwargs):
            if item["title"] == "Bad Item":
                raise IOError("Write failed")
            # Get the original function
            from pipeline import write_staged_item as original

            return original(item, *args, **kwargs)

        # Use patch to mock the function
        with patch("pipeline.write_staged_item", side_effect=mock_write):
            result = process_file(
                file_info=file_info,
                bible_context="",
                client=mock_client,
                dry_run=False,
            )

        # Should still return True (partial success)
        assert result is True


class TestProcessFileChatGPTFormat:
    """Tests for processing ChatGPT format files."""

    @pytest.fixture
    def mock_config(self, temp_vault, monkeypatch):
        """Set up test configuration."""
        test_config = {
            "vault_path": temp_vault,
            "staging_path": "01-Processed",
            "model": "test-model",
            "max_tokens": 4096,
        }
        monkeypatch.setattr("pipeline.CONFIG", test_config)
        return test_config

    def test_processes_chatgpt_json_format(self, mock_config, temp_vault):
        """Should correctly process ChatGPT JSON exports."""
        inbox = temp_vault / "00-Inbox" / "chatgpt"
        inbox.mkdir(parents=True, exist_ok=True)
        test_file = inbox / "2024-12-07-chat.txt"

        chatgpt_export = {
            "title": "Test Chat",
            "mapping": {
                "node1": {
                    "message": {
                        "author": {"role": "user"},
                        "content": {"parts": ["What is Python?"]},
                    }
                },
                "node2": {
                    "message": {
                        "author": {"role": "assistant"},
                        "content": {"parts": ["Python is a programming language."]},
                    }
                },
            },
        }
        test_file.write_text(json.dumps(chatgpt_export))

        file_info = {"path": test_file, "source": "chatgpt", "hash": "abc"}

        mock_extraction = {
            "items": [{"type": "insight", "title": "Python Info", "content": "About Python"}],
            "conversation_summary": "Discussion about Python",
            "primary_themes": [],
        }

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=json.dumps(mock_extraction))]
        mock_client.messages.create.return_value = mock_response

        result = process_file(
            file_info=file_info,
            bible_context="",
            client=mock_client,
            dry_run=False,
        )

        assert result is True

        # Verify the normalized content was passed to API
        call_args = mock_client.messages.create.call_args
        user_message = call_args[1]["messages"][0]["content"]
        assert "What is Python?" in user_message
        assert "Python is a programming language" in user_message
