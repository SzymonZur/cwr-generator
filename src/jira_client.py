"""Jira API client for fetching ticket details."""

import re
import logging
from typing import List, Dict, Any, Set, Optional
from jira import JIRA
from jira.exceptions import JIRAError
import time

logger = logging.getLogger(__name__)


class JiraClient:
    """Client for interacting with Jira API."""

    # Pattern to match Jira ticket keys: TEXT-NUMBER (e.g., FUI-0, PROJ-123)
    TICKET_PATTERN = re.compile(r"\b([A-Z][A-Z0-9]+-\d+)\b")

    def __init__(self, url: str, email: str, api_token: str, max_retries: int = 3):
        """
        Initialize Jira client.

        Args:
            url: Jira instance URL (e.g., https://company.atlassian.net)
            email: Jira account email
            api_token: Jira API token
            max_retries: Maximum number of retries for rate-limited requests
        """
        self.url = url
        self.email = email
        self.api_token = api_token
        self.max_retries = max_retries
        self.jira = JIRA(
            server=url, basic_auth=(email, api_token), max_retries=max_retries
        )

    @staticmethod
    def extract_ticket_keys(text: str) -> Set[str]:
        """
        Extract Jira ticket keys from text (commit messages, PR descriptions, etc.).

        Args:
            text: Text to search for ticket keys

        Returns:
            Set of unique ticket keys found (e.g., {'FUI-0', 'PROJ-123'})
        """
        if not text:
            return set()

        matches = JiraClient.TICKET_PATTERN.findall(text.upper())
        return set(matches)

    def _handle_rate_limit(self, func, *args, **kwargs):
        """Handle rate limiting with retries."""
        for attempt in range(self.max_retries):
            try:
                return func(*args, **kwargs)
            except JIRAError as e:
                if e.status_code == 429:  # Rate limit
                    if attempt < self.max_retries - 1:
                        wait_time = (attempt + 1) * 2  # Exponential backoff
                        logger.warning(
                            f"Rate limit exceeded. Waiting {wait_time} seconds..."
                        )
                        time.sleep(wait_time)
                    else:
                        raise
                else:
                    raise
            except Exception as e:
                logger.error(f"Jira API error: {e}")
                raise

    def get_ticket(self, ticket_key: str) -> Optional[Dict[str, Any]]:
        """
        Get details for a specific Jira ticket.

        Args:
            ticket_key: Jira ticket key (e.g., 'FUI-0')

        Returns:
            Dictionary with ticket details or None if not found
        """
        try:

            def fetch_ticket():
                return self.jira.issue(ticket_key)

            issue = self._handle_rate_limit(fetch_ticket)

            return {
                "key": issue.key,
                "summary": issue.fields.summary,
                "description": issue.fields.description or "",
                "project_key": issue.fields.project.key,
                "project_name": issue.fields.project.name,
                "issue_type": issue.fields.issuetype.name,
                "status": issue.fields.status.name,
                "created": issue.fields.created,
                "updated": issue.fields.updated,
                "assignee": (
                    issue.fields.assignee.displayName if issue.fields.assignee else None
                ),
                "url": f"{self.url}/browse/{issue.key}",
            }
        except JIRAError as e:
            if e.status_code == 404:
                logger.warning(f"Ticket {ticket_key} not found")
                return None
            raise
        except Exception as e:
            logger.error(f"Error fetching ticket {ticket_key}: {e}")
            return None

    def get_tickets(self, ticket_keys: Set[str]) -> Dict[str, Dict[str, Any]]:
        """
        Get details for multiple Jira tickets.

        Args:
            ticket_keys: Set of ticket keys to fetch

        Returns:
            Dictionary mapping ticket keys to their details
        """
        logger.info(f"Fetching {len(ticket_keys)} Jira tickets...")

        tickets = {}
        for ticket_key in ticket_keys:
            ticket = self.get_ticket(ticket_key)
            if ticket:
                tickets[ticket_key] = ticket

        logger.info(f"Successfully fetched {len(tickets)} tickets")
        return tickets

    def get_project_info(self, project_key: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a Jira project.

        Args:
            project_key: Project key (e.g., 'FUI')

        Returns:
            Dictionary with project information or None if not found
        """
        try:

            def fetch_project():
                return self.jira.project(project_key)

            project = self._handle_rate_limit(fetch_project)

            return {
                "key": project.key,
                "name": project.name,
                "description": getattr(project, "description", "") or "",
            }
        except JIRAError as e:
            if e.status_code == 404:
                logger.warning(f"Project {project_key} not found")
                return None
            raise
        except Exception as e:
            logger.error(f"Error fetching project {project_key}: {e}")
            return None

    def extract_tickets_from_commits(self, commits: List[Dict[str, Any]]) -> Set[str]:
        """
        Extract all unique Jira ticket keys from a list of commits.

        Args:
            commits: List of commit dictionaries

        Returns:
            Set of unique ticket keys
        """
        ticket_keys = set()

        for commit in commits:
            message = commit.get("message", "")
            keys = self.extract_ticket_keys(message)
            ticket_keys.update(keys)

        logger.info(f"Extracted {len(ticket_keys)} unique ticket keys from commits")
        return ticket_keys
