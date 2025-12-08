"""
Shared fixtures for Obsidian Pipeline tests.
"""

import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add the obsidian-pipeline directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "obsidian-pipeline"))


@pytest.fixture
def temp_vault(tmp_path):
    """Create a temporary vault directory structure."""
    vault = tmp_path / "TestVault"
    vault.mkdir()

    # Create inbox directories
    (vault / "00-Inbox" / "claude").mkdir(parents=True)
    (vault / "00-Inbox" / "chatgpt").mkdir(parents=True)
    (vault / "00-Inbox" / "gemini").mkdir(parents=True)

    # Create other directories
    (vault / "01-Processed").mkdir()
    (vault / "06-Bibles").mkdir()
    (vault / "_meta").mkdir()

    return vault


@pytest.fixture
def sample_config(temp_vault):
    """Create a sample config dictionary for testing."""
    return {
        "vault_path": temp_vault,
        "inbox_paths": {
            "claude": "00-Inbox/claude",
            "chatgpt": "00-Inbox/chatgpt",
            "gemini": "00-Inbox/gemini",
        },
        "staging_path": "01-Processed",
        "bibles_path": "06-Bibles",
        "meta_path": "_meta",
        "bible_files": ["06-Bibles/test_bible.md"],
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 4096,
    }


@pytest.fixture
def empty_processing_log():
    """Return an empty processing log."""
    return {"processed_files": {}, "last_run": None}


@pytest.fixture
def sample_processing_log():
    """Return a sample processing log with entries."""
    return {
        "processed_files": {
            "/vault/inbox/old_file.txt": {
                "hash": "abc123def456",
                "processed_at": "2024-12-01T10:00:00",
                "source": "claude",
            }
        },
        "last_run": "2024-12-01T10:00:00",
    }


@pytest.fixture
def sample_chatgpt_json():
    """Return a sample ChatGPT export JSON structure."""
    return {
        "title": "Test Conversation",
        "mapping": {
            "node1": {
                "message": {
                    "author": {"role": "user"},
                    "content": {"parts": ["Hello, how are you?"]},
                }
            },
            "node2": {
                "message": {
                    "author": {"role": "assistant"},
                    "content": {"parts": ["I'm doing well, thank you!"]},
                }
            },
        },
    }


@pytest.fixture
def sample_extraction_response():
    """Return a sample successful API extraction response."""
    return {
        "items": [
            {
                "type": "theme",
                "title": "Test Theme",
                "content": "This is a test theme extracted from the conversation.",
                "key_quote": "This is the key quote from the conversation.",
                "related_themes": ["[[Related Theme]]"],
                "confidence": "high",
            },
            {
                "type": "decision",
                "title": "Test Decision",
                "content": "A decision was made during this conversation.",
                "key_quote": "We decided to go with option A.",
                "related_themes": ["[[Test Theme]]"],
                "confidence": "medium",
            },
        ],
        "conversation_summary": "This was a test conversation about various topics.",
        "primary_themes": ["[[Test Theme]]", "[[Related Theme]]"],
    }


@pytest.fixture
def mock_anthropic_client(sample_extraction_response):
    """Create a mock Anthropic client."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=json.dumps(sample_extraction_response))]
    mock_client.messages.create.return_value = mock_response
    return mock_client


@pytest.fixture
def sample_conversation_file(temp_vault):
    """Create a sample conversation file in the vault."""
    inbox = temp_vault / "00-Inbox" / "claude"
    file_path = inbox / "2024-12-07-test-conversation.txt"
    file_path.write_text(
        "User: What is the meaning of life?\n\n"
        "Assistant: The meaning of life is a philosophical question...\n\n"
        "User: That's interesting. Tell me more.\n\n"
        "Assistant: There are many perspectives on this topic..."
    )
    return file_path


@pytest.fixture
def sample_bible_file(temp_vault):
    """Create a sample Bible file in the vault."""
    bible_path = temp_vault / "06-Bibles" / "test_bible.md"
    bible_path.write_text(
        "---\n"
        "title: Test Bible\n"
        "type: bible\n"
        "---\n\n"
        "# Test Bible\n\n"
        "This is a test project context file.\n"
    )
    return bible_path
