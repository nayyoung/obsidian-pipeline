"""
Tests for parse_source_date() function.

HIGH PRIORITY: Date parsing with various formats and fallback behavior.
"""

import os
import time
from datetime import datetime
from pathlib import Path

import pytest

from pipeline import parse_source_date


class TestValidDateFormats:
    """Test parsing of valid date formats in filenames."""

    def test_standard_date_format(self, tmp_path):
        """Standard YYYY-MM-DD format should be extracted."""
        file_path = tmp_path / "2024-12-07-topic-name.txt"
        file_path.touch()
        result = parse_source_date(file_path)
        assert result == "2024-12-07"

    def test_date_with_simple_topic(self, tmp_path):
        """Date followed by simple topic should work."""
        file_path = tmp_path / "2024-01-15-meeting-notes.txt"
        file_path.touch()
        result = parse_source_date(file_path)
        assert result == "2024-01-15"

    def test_date_with_multiple_hyphens_in_topic(self, tmp_path):
        """Date followed by topic with multiple hyphens should work."""
        file_path = tmp_path / "2024-06-30-gumroad-launch-strategy-v2.txt"
        file_path.touch()
        result = parse_source_date(file_path)
        assert result == "2024-06-30"

    def test_date_only_filename(self, tmp_path):
        """Filename that is only a date should work."""
        file_path = tmp_path / "2024-12-25.txt"
        file_path.touch()
        result = parse_source_date(file_path)
        assert result == "2024-12-25"

    def test_boundary_dates(self, tmp_path):
        """Test boundary dates (start/end of year, month)."""
        test_cases = [
            ("2024-01-01-new-year.txt", "2024-01-01"),
            ("2024-12-31-end-of-year.txt", "2024-12-31"),
            ("2024-02-29-leap-day.txt", "2024-02-29"),  # 2024 is a leap year
        ]
        for filename, expected in test_cases:
            file_path = tmp_path / filename
            file_path.touch()
            result = parse_source_date(file_path)
            assert result == expected, f"Failed for {filename}"


class TestInvalidDateFormats:
    """Test fallback behavior for invalid date formats."""

    def test_no_date_prefix(self, tmp_path):
        """Filename without date should fallback to file mtime."""
        file_path = tmp_path / "random-topic-name.txt"
        file_path.touch()

        result = parse_source_date(file_path)

        # Should be a valid date string
        datetime.strptime(result, "%Y-%m-%d")
        # Should be today's date (since file was just created)
        assert result == datetime.now().strftime("%Y-%m-%d")

    def test_invalid_month(self, tmp_path):
        """Invalid month (13) should fallback to file mtime."""
        file_path = tmp_path / "2024-13-07-topic.txt"
        file_path.touch()
        result = parse_source_date(file_path)
        # Should fallback to today (file mtime)
        assert result == datetime.now().strftime("%Y-%m-%d")

    def test_invalid_day(self, tmp_path):
        """Invalid day (32) should fallback to file mtime."""
        file_path = tmp_path / "2024-12-32-topic.txt"
        file_path.touch()
        result = parse_source_date(file_path)
        assert result == datetime.now().strftime("%Y-%m-%d")

    def test_invalid_february_date(self, tmp_path):
        """Invalid February date (Feb 30) should fallback."""
        file_path = tmp_path / "2024-02-30-topic.txt"
        file_path.touch()
        result = parse_source_date(file_path)
        assert result == datetime.now().strftime("%Y-%m-%d")

    def test_non_leap_year_feb_29(self, tmp_path):
        """Feb 29 on non-leap year should fallback."""
        file_path = tmp_path / "2023-02-29-topic.txt"  # 2023 is not a leap year
        file_path.touch()
        result = parse_source_date(file_path)
        assert result == datetime.now().strftime("%Y-%m-%d")

    def test_two_digit_year(self, tmp_path):
        """Two-digit year should fallback to file mtime."""
        file_path = tmp_path / "24-12-07-topic.txt"
        file_path.touch()
        result = parse_source_date(file_path)
        # Two-digit year doesn't match len(year) == 4 check
        assert result == datetime.now().strftime("%Y-%m-%d")

    def test_single_digit_month(self, tmp_path):
        """Single-digit month should fallback."""
        file_path = tmp_path / "2024-1-07-topic.txt"
        file_path.touch()
        result = parse_source_date(file_path)
        # len(month) != 2
        assert result == datetime.now().strftime("%Y-%m-%d")

    def test_single_digit_day(self, tmp_path):
        """Single-digit day should fallback."""
        file_path = tmp_path / "2024-12-7-topic.txt"
        file_path.touch()
        result = parse_source_date(file_path)
        # len(day) != 2
        assert result == datetime.now().strftime("%Y-%m-%d")


class TestFileMtimeFallback:
    """Test fallback to file modification time."""

    def test_fallback_uses_file_mtime(self, tmp_path):
        """When no date in filename, should use file mtime."""
        file_path = tmp_path / "no-date-here.txt"
        file_path.touch()

        # Set a specific modification time (2024-06-15)
        target_time = datetime(2024, 6, 15, 12, 0, 0).timestamp()
        os.utime(file_path, (target_time, target_time))

        result = parse_source_date(file_path)
        assert result == "2024-06-15"

    def test_fallback_with_old_file(self, tmp_path):
        """Older file should return its modification date."""
        file_path = tmp_path / "old-file.txt"
        file_path.touch()

        # Set modification time to 2020-01-01
        target_time = datetime(2020, 1, 1, 12, 0, 0).timestamp()
        os.utime(file_path, (target_time, target_time))

        result = parse_source_date(file_path)
        assert result == "2020-01-01"


class TestEdgeCases:
    """Test edge cases and unusual filenames."""

    def test_filename_with_only_hyphens(self, tmp_path):
        """Filename with only hyphens should fallback."""
        file_path = tmp_path / "----.txt"
        file_path.touch()
        result = parse_source_date(file_path)
        # Should return valid date (fallback)
        datetime.strptime(result, "%Y-%m-%d")

    def test_empty_stem(self, tmp_path):
        """File with empty stem should fallback."""
        file_path = tmp_path / ".txt"
        file_path.touch()
        result = parse_source_date(file_path)
        datetime.strptime(result, "%Y-%m-%d")

    def test_very_long_filename(self, tmp_path):
        """Very long filename should still extract date if present."""
        long_topic = "a" * 200
        file_path = tmp_path / f"2024-12-07-{long_topic}.txt"
        file_path.touch()
        result = parse_source_date(file_path)
        assert result == "2024-12-07"

    def test_date_with_underscores_not_matched(self, tmp_path):
        """Date with underscores instead of hyphens should fallback."""
        file_path = tmp_path / "2024_12_07_topic.txt"
        file_path.touch()
        result = parse_source_date(file_path)
        # Underscores don't split correctly, should fallback
        assert result == datetime.now().strftime("%Y-%m-%d")

    def test_unicode_in_filename(self, tmp_path):
        """Unicode characters in filename after date should work."""
        try:
            file_path = tmp_path / "2024-12-07-日本語トピック.txt"
            file_path.touch()
            result = parse_source_date(file_path)
            assert result == "2024-12-07"
        except OSError:
            pytest.skip("Unicode filenames not supported")

    def test_spaces_in_filename(self, tmp_path):
        """Spaces in filename should fallback since split uses hyphens."""
        file_path = tmp_path / "2024 12 07 topic.txt"
        file_path.touch()
        result = parse_source_date(file_path)
        # Spaces don't split as hyphens do
        assert result == datetime.now().strftime("%Y-%m-%d")


class TestPathTypes:
    """Test with different path types."""

    def test_pathlib_path(self, tmp_path):
        """pathlib.Path object should work."""
        file_path = tmp_path / "2024-12-07-test.txt"
        file_path.touch()
        result = parse_source_date(file_path)
        assert result == "2024-12-07"

    def test_absolute_path(self, tmp_path):
        """Absolute path should work."""
        file_path = (tmp_path / "2024-12-07-test.txt").resolve()
        file_path.touch()
        result = parse_source_date(file_path)
        assert result == "2024-12-07"


class TestCurrentDateFallback:
    """Test ultimate fallback to current date."""

    def test_stat_error_fallback(self, tmp_path, monkeypatch):
        """If stat() fails, should fallback to current date."""
        file_path = tmp_path / "no-date.txt"
        file_path.touch()

        # Mock stat to raise an error
        original_stat = Path.stat

        def mock_stat(self):
            if "no-date.txt" in str(self):
                raise OSError("Permission denied")
            return original_stat(self)

        monkeypatch.setattr(Path, "stat", mock_stat)

        result = parse_source_date(file_path)
        # Should fallback to current date
        assert result == datetime.now().strftime("%Y-%m-%d")
