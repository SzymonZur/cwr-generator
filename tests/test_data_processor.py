"""Tests for data processing and grouping."""

import unittest
from unittest.mock import Mock
from src.data_processor import DataProcessor
from src.jira_client import JiraClient


class TestDataProcessor(unittest.TestCase):
    """Test data processor."""

    def setUp(self):
        """Set up test fixtures."""
        self.jira_client = Mock(spec=JiraClient)
        self.jira_client.extract_ticket_keys = JiraClient.extract_ticket_keys
        self.processor = DataProcessor(self.jira_client)

    def test_group_by_project_single_ticket(self):
        """Test grouping commits by project with single ticket."""
        commits = [
            {
                "sha": "abc123",
                "message": "fix: bug FUI-0",
                "repository": "test/repo",
                "files": [],
            }
        ]
        tickets = {
            "FUI-0": {
                "key": "FUI-0",
                "project_key": "FUI",
                "project_name": "Feature UI",
                "summary": "Fix bug",
            }
        }

        linked_commits = self.processor.link_commits_to_tickets(commits, tickets)
        projects = self.processor.group_by_project(linked_commits)

        self.assertIn("FUI", projects)
        self.assertEqual(projects["FUI"]["metrics"]["total_commits"], 1)
        self.assertEqual(len(projects["FUI"]["tickets"]), 1)

    def test_group_by_project_multiple_tickets(self):
        """Test grouping with multiple tickets from same project."""
        commits = [
            {
                "sha": "abc123",
                "message": "fix: bug FUI-0",
                "repository": "test/repo",
                "files": [],
            },
            {
                "sha": "def456",
                "message": "feat: new feature FUI-1",
                "repository": "test/repo",
                "files": [],
            },
        ]
        tickets = {
            "FUI-0": {
                "key": "FUI-0",
                "project_key": "FUI",
                "project_name": "Feature UI",
                "summary": "Fix bug",
            },
            "FUI-1": {
                "key": "FUI-1",
                "project_key": "FUI",
                "project_name": "Feature UI",
                "summary": "New feature",
            },
        }

        linked_commits = self.processor.link_commits_to_tickets(commits, tickets)
        projects = self.processor.group_by_project(linked_commits)

        self.assertIn("FUI", projects)
        self.assertEqual(projects["FUI"]["metrics"]["total_commits"], 2)
        self.assertEqual(len(projects["FUI"]["tickets"]), 2)

    def test_group_by_project_unlinked_commits(self):
        """Test grouping unlinked commits by repository."""
        commits = [
            {
                "sha": "abc123",
                "message": "fix: bug without ticket",
                "repository": "test/repo",
                "files": [],
            }
        ]

        linked_commits = self.processor.link_commits_to_tickets(commits, {})
        projects = self.processor.group_by_project(linked_commits)

        # Should create an UNLINKED project
        unlinked_key = "UNLINKED-test/repo"
        self.assertIn(unlinked_key, projects)
        self.assertEqual(projects[unlinked_key]["metrics"]["total_commits"], 1)

    def test_deduplicate_commits(self):
        """Test deduplication of commits."""
        commits = [
            {"sha": "abc123", "message": "fix: bug", "repository": "test/repo"},
            {"sha": "def456", "message": "feat: feature", "repository": "test/repo"},
            {
                "sha": "abc123",  # Duplicate
                "message": "fix: bug",
                "repository": "test/repo",
            },
        ]

        unique = self.processor.deduplicate_commits(commits)

        # Should remove duplicate abc123
        self.assertEqual(len(unique), 2)
        self.assertEqual(unique[0]["sha"], "abc123")
        self.assertEqual(unique[1]["sha"], "def456")


if __name__ == "__main__":
    unittest.main()
