"""Data processing: linking commits to Jira tickets and grouping by project."""

import logging
from typing import List, Dict, Any, Set, Optional
from collections import defaultdict
from datetime import datetime

logger = logging.getLogger(__name__)


class DataProcessor:
    """Process and link GitHub commits with Jira tickets."""

    def __init__(self, jira_client):
        """
        Initialize data processor.

        Args:
            jira_client: JiraClient instance
        """
        self.jira_client = jira_client

    def link_commits_to_tickets(
        self, commits: List[Dict[str, Any]], tickets: Dict[str, Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Link commits to their associated Jira tickets.

        Args:
            commits: List of commit dictionaries
            tickets: Dictionary mapping ticket keys to ticket details

        Returns:
            List of commits with linked ticket information
        """
        linked_commits = []

        for commit in commits:
            commit_message = commit.get("message", "")
            ticket_keys = self.jira_client.extract_ticket_keys(commit_message)

            linked_commit = commit.copy()
            linked_commit["ticket_keys"] = list(ticket_keys)
            linked_commit["tickets"] = [
                tickets[key] for key in ticket_keys if key in tickets
            ]

            linked_commits.append(linked_commit)

        logger.info(f"Linked {len(linked_commits)} commits to tickets")
        return linked_commits

    def group_by_project(
        self, linked_commits: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Group commits by Jira project key.

        If a commit has a ticket key pattern (e.g., "FUI-123"), it will be grouped
        under that project even if the ticket doesn't exist in Jira. This allows
        the AI to summarize based on commit messages.

        Args:
            linked_commits: List of commits with linked ticket information

        Returns:
            Dictionary mapping project keys to project data
        """
        projects = defaultdict(
            lambda: {
                "project_key": None,
                "project_name": None,
                "commits": [],
                "tickets": {},
                "metrics": {
                    "total_commits": 0,
                    "total_files_changed": 0,
                    "total_additions": 0,
                    "total_deletions": 0,
                    "unique_tickets": set(),
                },
            }
        )

        # Process commits
        for commit in linked_commits:
            ticket_keys = commit.get("ticket_keys", [])

            if ticket_keys:
                # Group by project from ticket keys
                # Extract unique project keys from all ticket keys in this commit
                project_keys_found = set()
                for ticket_key in ticket_keys:
                    # Extract project key from ticket key (e.g., "FUI-0" -> "FUI")
                    project_key = ticket_key.split("-")[0]
                    project_keys_found.add(project_key)

                    # Get ticket details if available
                    tickets = commit.get("tickets", [])
                    for ticket in tickets:
                        if ticket["key"] == ticket_key:
                            projects[project_key]["project_key"] = project_key
                            projects[project_key]["project_name"] = ticket.get(
                                "project_name", project_key
                            )
                            projects[project_key]["tickets"][ticket_key] = ticket
                            projects[project_key]["metrics"]["unique_tickets"].add(
                                ticket_key
                            )

                    # Always track the ticket key, even if ticket doesn't exist
                    projects[project_key]["metrics"]["unique_tickets"].add(ticket_key)

                # Add commit to each project it references
                # (commits can appear multiple times if they reference multiple tickets)
                for project_key in project_keys_found:
                    # Initialize project if not already done
                    if projects[project_key]["project_key"] is None:
                        projects[project_key]["project_key"] = project_key
                        # Try to get project name from Jira if available
                        project_info = self.jira_client.get_project_info(project_key)
                        if project_info:
                            projects[project_key]["project_name"] = project_info.get(
                                "name", project_key
                            )
                        else:
                            # Use project key as name if we can't fetch it
                            projects[project_key]["project_name"] = project_key

                    # Add commit to project (allows duplicates if commit references multiple tickets)
                    projects[project_key]["commits"].append(commit)
                    projects[project_key]["metrics"]["total_commits"] += 1

                    # Update file metrics
                    files = commit.get("files", [])
                    if files:
                        projects[project_key]["metrics"]["total_files_changed"] += len(
                            files
                        )
                        for file_info in files:
                            projects[project_key]["metrics"][
                                "total_additions"
                            ] += file_info.get("additions", 0)
                            projects[project_key]["metrics"][
                                "total_deletions"
                            ] += file_info.get("deletions", 0)
            else:
                # Unlinked commits - group by repository
                repo = commit.get("repository", "Unknown")
                project_key = f"UNLINKED-{repo}"

                projects[project_key]["project_key"] = project_key
                projects[project_key]["project_name"] = f"Unlinked Work - {repo}"
                projects[project_key]["commits"].append(commit)
                projects[project_key]["metrics"]["total_commits"] += 1

                # Update file metrics
                files = commit.get("files", [])
                if files:
                    projects[project_key]["metrics"]["total_files_changed"] += len(
                        files
                    )
                    for file_info in files:
                        projects[project_key]["metrics"][
                            "total_additions"
                        ] += file_info.get("additions", 0)
                        projects[project_key]["metrics"][
                            "total_deletions"
                        ] += file_info.get("deletions", 0)

        # Convert sets to lists for JSON serialization
        for project_data in projects.values():
            project_data["metrics"]["unique_tickets"] = len(
                project_data["metrics"]["unique_tickets"]
            )

        # Merge unlinked projects with existing projects from the same repository
        projects = self._merge_unlinked_projects(projects)

        logger.info(f"Grouped data into {len(projects)} projects")
        return dict(projects)

    def _merge_unlinked_projects(
        self, projects: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Merge unlinked projects (UNLINKED-*) into existing projects from the same repository.

        Args:
            projects: Dictionary of projects

        Returns:
            Dictionary with merged projects
        """
        # Build a map of repository -> project_key for non-unlinked projects
        repo_to_project = {}
        for project_key, project_data in projects.items():
            if not project_key.startswith("UNLINKED-"):
                # Get unique repositories from commits in this project
                repos = set()
                for commit in project_data.get("commits", []):
                    repo = commit.get("repository")
                    if repo:
                        repos.add(repo)

                # Map each repository to this project
                for repo in repos:
                    if repo not in repo_to_project:
                        repo_to_project[repo] = project_key
                    # If multiple projects share a repo, prefer the one with more commits
                    elif len(projects[repo_to_project[repo]]["commits"]) < len(
                        project_data["commits"]
                    ):
                        repo_to_project[repo] = project_key

        # Merge unlinked projects into matching projects
        projects_to_remove = []
        for project_key, project_data in list(projects.items()):
            if project_key.startswith("UNLINKED-"):
                # Extract repository from unlinked project key (UNLINKED-repo -> repo)
                repo = project_key.replace("UNLINKED-", "", 1)

                # Check if there's a matching project for this repository
                if repo in repo_to_project:
                    target_project_key = repo_to_project[repo]
                    target_project = projects[target_project_key]

                    # Merge commits
                    target_project["commits"].extend(project_data["commits"])
                    target_project["metrics"]["total_commits"] += project_data[
                        "metrics"
                    ]["total_commits"]
                    target_project["metrics"]["total_files_changed"] += project_data[
                        "metrics"
                    ]["total_files_changed"]
                    target_project["metrics"]["total_additions"] += project_data[
                        "metrics"
                    ]["total_additions"]
                    target_project["metrics"]["total_deletions"] += project_data[
                        "metrics"
                    ]["total_deletions"]

                    logger.info(
                        f"Merged unlinked project {project_key} ({len(project_data['commits'])} commits) "
                        f"into {target_project_key}"
                    )
                    projects_to_remove.append(project_key)

        # Remove merged unlinked projects
        for project_key in projects_to_remove:
            del projects[project_key]

        return projects

    def deduplicate_commits(
        self, commits: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Remove duplicate commits based on SHA.

        Args:
            commits: List of commit dictionaries

        Returns:
            Deduplicated list of commits
        """
        seen_shas = set()
        unique_commits = []

        for commit in commits:
            sha = commit.get("sha")
            if sha and sha not in seen_shas:
                seen_shas.add(sha)
                unique_commits.append(commit)

        if len(unique_commits) < len(commits):
            logger.info(
                f"Deduplicated: {len(commits)} -> {len(unique_commits)} commits"
            )

        return unique_commits

    def process_data(
        self,
        commits: List[Dict[str, Any]],
        tickets: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Main processing function: link commits to tickets and group by project.

        Args:
            commits: List of commit dictionaries
            tickets: Optional dictionary of ticket details

        Returns:
            Dictionary mapping project keys to project data
        """
        logger.info(
            "Processing data: linking commits to tickets and grouping by project"
        )

        # Deduplicate commits
        unique_commits = self.deduplicate_commits(commits)

        # Always extract ticket keys from commits, even if tickets dict is empty
        # This ensures commits with ticket references (like "GENC-0") are grouped
        # by project even if the ticket doesn't exist in Jira
        tickets_dict = tickets if tickets is not None else {}
        linked_commits = self.link_commits_to_tickets(unique_commits, tickets_dict)

        # Group by project
        projects = self.group_by_project(linked_commits)

        return projects

    def get_project_summary_data(
        self, project_key: str, project_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Prepare summary data for a project to be used in AI summarization.

        Args:
            project_key: Project key
            project_data: Project data dictionary

        Returns:
            Dictionary with summary data
        """
        commits = project_data.get("commits", [])
        tickets = project_data.get("tickets", {})

        # Collect all text for summarization
        commit_messages = [c.get("message", "") for c in commits]
        ticket_summaries = [t.get("summary", "") for t in tickets.values()]
        ticket_descriptions = [
            t.get("description", "") for t in tickets.values() if t.get("description")
        ]

        return {
            "project_key": project_key,
            "project_name": project_data.get("project_name", project_key),
            "commit_messages": commit_messages,
            "ticket_summaries": ticket_summaries,
            "ticket_descriptions": ticket_descriptions,
            "metrics": project_data.get("metrics", {}),
        }
