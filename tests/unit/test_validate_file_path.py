"""
Tests for validate_file_path() function.

CRITICAL PRIORITY: This function prevents path traversal and vault boundary escape.
"""

import os
import pytest
from pathlib import Path

from pipeline import validate_file_path


class TestValidPathsWithinVault:
    """Test that valid paths within the vault are accepted."""

    def test_file_in_vault_root(self, temp_vault):
        """File directly in vault root should be valid."""
        file_path = temp_vault / "file.txt"
        file_path.touch()
        assert validate_file_path(file_path, temp_vault) is True

    def test_file_in_inbox(self, temp_vault):
        """File in inbox subdirectory should be valid."""
        file_path = temp_vault / "00-Inbox" / "claude" / "conversation.txt"
        file_path.touch()
        assert validate_file_path(file_path, temp_vault) is True

    def test_deeply_nested_file(self, temp_vault):
        """Deeply nested file should be valid."""
        deep_dir = temp_vault / "a" / "b" / "c" / "d" / "e"
        deep_dir.mkdir(parents=True)
        file_path = deep_dir / "file.txt"
        file_path.touch()
        assert validate_file_path(file_path, temp_vault) is True

    def test_vault_root_itself(self, temp_vault):
        """The vault root directory itself should be valid."""
        assert validate_file_path(temp_vault, temp_vault) is True


class TestPathTraversalAttempts:
    """Test that path traversal attacks are blocked."""

    def test_parent_directory_traversal(self, temp_vault):
        """Path traversal with .. should be rejected."""
        # Create a path that tries to escape vault
        malicious_path = temp_vault / ".." / "outside.txt"
        assert validate_file_path(malicious_path, temp_vault) is False

    def test_multiple_parent_traversal(self, temp_vault):
        """Multiple .. components should be rejected."""
        malicious_path = temp_vault / ".." / ".." / ".." / "etc" / "passwd"
        assert validate_file_path(malicious_path, temp_vault) is False

    def test_traversal_from_subdirectory(self, temp_vault):
        """Traversal from subdirectory should be rejected."""
        malicious_path = temp_vault / "00-Inbox" / ".." / ".." / "outside.txt"
        assert validate_file_path(malicious_path, temp_vault) is False

    def test_absolute_path_outside_vault(self, temp_vault):
        """Absolute path outside vault should be rejected."""
        malicious_path = Path("/etc/passwd")
        assert validate_file_path(malicious_path, temp_vault) is False

    def test_sibling_directory(self, temp_vault):
        """Sibling directory of vault should be rejected."""
        sibling_path = temp_vault.parent / "sibling_folder" / "file.txt"
        assert validate_file_path(sibling_path, temp_vault) is False


class TestSymlinkHandling:
    """Test handling of symbolic links (if filesystem supports them)."""

    @pytest.mark.skipif(os.name == "nt", reason="Symlinks require admin on Windows")
    def test_symlink_to_outside_rejected(self, temp_vault, tmp_path):
        """Symlink pointing outside vault should be rejected after resolution."""
        # Create a file outside the vault
        outside_file = tmp_path / "outside_secret.txt"
        outside_file.write_text("secret data")

        # Create a symlink inside vault pointing outside
        symlink_path = temp_vault / "sneaky_link"
        try:
            symlink_path.symlink_to(outside_file)
            # After resolving, this should point outside vault
            assert validate_file_path(symlink_path, temp_vault) is False
        except OSError:
            pytest.skip("Symlink creation not supported")

    @pytest.mark.skipif(os.name == "nt", reason="Symlinks require admin on Windows")
    def test_symlink_within_vault_accepted(self, temp_vault):
        """Symlink pointing to file within vault should be accepted."""
        # Create a real file
        real_file = temp_vault / "real_file.txt"
        real_file.write_text("real content")

        # Create a symlink within vault
        symlink_path = temp_vault / "link_to_real"
        try:
            symlink_path.symlink_to(real_file)
            assert validate_file_path(symlink_path, temp_vault) is True
        except OSError:
            pytest.skip("Symlink creation not supported")

    @pytest.mark.skipif(os.name == "nt", reason="Symlinks require admin on Windows")
    def test_symlink_directory_escape(self, temp_vault, tmp_path):
        """Directory symlink that escapes vault should be rejected."""
        # Create a directory outside vault
        outside_dir = tmp_path / "outside_dir"
        outside_dir.mkdir()
        (outside_dir / "secret.txt").write_text("secret")

        # Create a symlink to outside directory
        symlink_dir = temp_vault / "sneaky_dir"
        try:
            symlink_dir.symlink_to(outside_dir)
            # File through symlinked directory should be rejected
            file_through_link = symlink_dir / "secret.txt"
            assert validate_file_path(file_through_link, temp_vault) is False
        except OSError:
            pytest.skip("Symlink creation not supported")


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_nonexistent_file_within_vault(self, temp_vault):
        """Non-existent file path within vault boundaries should be valid."""
        # The function checks path containment, not existence
        nonexistent = temp_vault / "does_not_exist.txt"
        # Path resolution works even for non-existent paths (uses parent)
        # This behavior depends on implementation
        result = validate_file_path(nonexistent, temp_vault)
        # Should return True since path is within vault bounds
        assert result is True

    def test_empty_vault_path(self, temp_vault):
        """Test with unusual vault paths."""
        file_path = temp_vault / "file.txt"
        file_path.touch()
        # Normal case should work
        assert validate_file_path(file_path, temp_vault) is True

    def test_path_with_spaces(self, temp_vault):
        """Paths with spaces should work correctly."""
        spaced_dir = temp_vault / "path with spaces"
        spaced_dir.mkdir()
        file_path = spaced_dir / "file name.txt"
        file_path.touch()
        assert validate_file_path(file_path, temp_vault) is True

    def test_path_with_unicode(self, temp_vault):
        """Paths with unicode characters should work."""
        try:
            unicode_dir = temp_vault / "日本語フォルダ"
            unicode_dir.mkdir()
            file_path = unicode_dir / "ファイル.txt"
            file_path.touch()
            assert validate_file_path(file_path, temp_vault) is True
        except OSError:
            pytest.skip("Unicode filenames not supported on this filesystem")


class TestRelativeVsAbsolutePaths:
    """Test handling of relative and absolute paths."""

    def test_absolute_path_in_vault(self, temp_vault):
        """Absolute path within vault should be valid."""
        file_path = temp_vault / "00-Inbox" / "claude" / "file.txt"
        file_path.touch()
        # Use absolute path
        absolute_path = file_path.resolve()
        assert validate_file_path(absolute_path, temp_vault) is True

    def test_relative_path_resolution(self, temp_vault, monkeypatch):
        """Relative paths should be resolved correctly."""
        # Create a file
        file_path = temp_vault / "file.txt"
        file_path.touch()

        # Change to vault directory
        monkeypatch.chdir(temp_vault)

        # Use relative path
        relative_path = Path("file.txt")
        assert validate_file_path(relative_path, temp_vault) is True


class TestVaultBoundaryPrecision:
    """Test precise boundary checking."""

    def test_similar_named_sibling(self, tmp_path):
        """Vault with similar name shouldn't match sibling."""
        # Create /tmp/xxx/vault and /tmp/xxx/vault_extra
        vault = tmp_path / "vault"
        vault.mkdir()
        vault_extra = tmp_path / "vault_extra"
        vault_extra.mkdir()

        file_in_extra = vault_extra / "file.txt"
        file_in_extra.touch()

        # File in vault_extra should NOT be valid for vault
        assert validate_file_path(file_in_extra, vault) is False

    def test_vault_name_prefix_attack(self, tmp_path):
        """Ensure prefix matching doesn't cause false positives."""
        vault = tmp_path / "my_vault"
        vault.mkdir()
        attacker_vault = tmp_path / "my_vault_attacker"
        attacker_vault.mkdir()

        # File in attacker's vault
        evil_file = attacker_vault / "evil.txt"
        evil_file.touch()

        # Should NOT be valid
        assert validate_file_path(evil_file, vault) is False


class TestErrorHandling:
    """Test error handling for various failure modes."""

    def test_permission_error_handling(self, temp_vault, monkeypatch):
        """Test handling of permission errors during resolution."""
        file_path = temp_vault / "file.txt"
        file_path.touch()

        # Mock Path.resolve to raise OSError
        original_resolve = Path.resolve

        def mock_resolve(self, *args, **kwargs):
            if "file.txt" in str(self):
                raise OSError("Permission denied")
            return original_resolve(self, *args, **kwargs)

        monkeypatch.setattr(Path, "resolve", mock_resolve)

        # Should return False on error, not raise
        result = validate_file_path(file_path, temp_vault)
        assert result is False

    def test_runtime_error_handling(self, temp_vault, monkeypatch):
        """Test handling of RuntimeError (e.g., symlink loops)."""
        file_path = temp_vault / "file.txt"
        file_path.touch()

        # Mock to raise RuntimeError (symlink loop)
        original_resolve = Path.resolve

        def mock_resolve(self, *args, **kwargs):
            if "file.txt" in str(self):
                raise RuntimeError("Symlink loop detected")
            return original_resolve(self, *args, **kwargs)

        monkeypatch.setattr(Path, "resolve", mock_resolve)

        result = validate_file_path(file_path, temp_vault)
        assert result is False
