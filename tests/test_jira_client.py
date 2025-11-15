"""Tests for Jira ticket extraction."""

import unittest
from src.jira_client import JiraClient


class TestJiraClient(unittest.TestCase):
    """Test Jira client ticket extraction."""

    def test_extract_ticket_keys_simple(self):
        """Test extracting simple ticket keys."""
        text = "fix: bug in something FUI-0"
        keys = JiraClient.extract_ticket_keys(text)
        self.assertEqual(keys, {"FUI-0"})

    def test_extract_ticket_keys_multiple(self):
        """Test extracting multiple ticket keys."""
        text = "fix: bug FUI-0 and PROJ-123"
        keys = JiraClient.extract_ticket_keys(text)
        self.assertEqual(keys, {"FUI-0", "PROJ-123"})

    def test_extract_ticket_keys_various_formats(self):
        """Test extracting tickets in various formats."""
        text = "fix: bug in something FUI-0 | [PROJ-123] ABC-456: description"
        keys = JiraClient.extract_ticket_keys(text)
        self.assertEqual(keys, {"FUI-0", "PROJ-123", "ABC-456"})

    def test_extract_ticket_keys_case_insensitive(self):
        """Test that extraction is case-insensitive."""
        text = "fix: bug fui-0 and ProJ-123"
        keys = JiraClient.extract_ticket_keys(text)
        self.assertEqual(keys, {"FUI-0", "PROJ-123"})

    def test_extract_ticket_keys_no_match(self):
        """Test with no ticket keys."""
        text = "fix: bug in something"
        keys = JiraClient.extract_ticket_keys(text)
        self.assertEqual(keys, set())

    def test_extract_ticket_keys_empty(self):
        """Test with empty text."""
        keys = JiraClient.extract_ticket_keys("")
        self.assertEqual(keys, set())

    def test_extract_ticket_keys_none(self):
        """Test with None."""
        keys = JiraClient.extract_ticket_keys(None)
        self.assertEqual(keys, set())


if __name__ == "__main__":
    unittest.main()
