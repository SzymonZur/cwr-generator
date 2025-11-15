"""GitHub API client for fetching commits."""

import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from github import Github
from github.GithubException import GithubException, RateLimitExceededException
import time

logger = logging.getLogger(__name__)


class GitHubClient:
    """Client for interacting with GitHub API."""

    def __init__(self, token: str, max_retries: int = 3):
        """
        Initialize GitHub client.

        Args:
            token: GitHub personal access token
            max_retries: Maximum number of retries for rate-limited requests
        """
        self.token = token
        self.max_retries = max_retries
        self.github = Github(token)
        self._user = None

    @property
    def user(self):
        """Get the authenticated user."""
        if self._user is None:
            self._user = self.github.get_user()
        return self._user

    def _handle_rate_limit(self, func, *args, **kwargs):
        """Handle rate limiting with retries."""
        for attempt in range(self.max_retries):
            try:
                return func(*args, **kwargs)
            except RateLimitExceededException as e:
                if attempt < self.max_retries - 1:
                    reset_time = self.github.get_rate_limit().core.reset
                    wait_time = (
                        max(0, (reset_time - datetime.now()).total_seconds()) + 1
                    )
                    logger.warning(
                        f"Rate limit exceeded. Waiting {wait_time:.0f} seconds..."
                    )
                    time.sleep(wait_time)
                else:
                    raise
            except GithubException as e:
                logger.error(f"GitHub API error: {e}")
                raise

    def get_user_repositories(
        self,
        organizations: Optional[List[str]] = None,
        repositories: Optional[List[str]] = None,
    ) -> List[Any]:
        """
        Get repositories accessible to the authenticated user (including private repos).

        Args:
            organizations: Optional list of organization names to filter by (e.g., ["myorg"])
            repositories: Optional list of repository names to filter by (e.g., ["myorg/repo", "repo"])

        Returns:
            List of filtered repositories
        """
        logger.info("Fetching user repositories (including private)...")

        repos = []

        def fetch_repos():
            # Get all repos: owned, member, organization member
            # This includes both public and private repositories
            return list(
                self.user.get_repos(
                    affiliation="owner,collaborator,organization_member", sort="updated"
                )
            )

        all_repos = self._handle_rate_limit(fetch_repos)

        # Apply filters if specified
        if organizations or repositories:
            logger.info(
                f"Filtering repositories: orgs={organizations}, repos={repositories}"
            )

            filtered_repos = []
            for repo in all_repos:
                repo_full_name = repo.full_name
                repo_owner = (
                    repo_full_name.split("/")[0] if "/" in repo_full_name else None
                )
                repo_name = (
                    repo_full_name.split("/")[1]
                    if "/" in repo_full_name
                    else repo_full_name
                )

                # If repositories list is specified, use it (takes precedence)
                if repositories:
                    # Check if repo matches any in the repositories list
                    # Support both "org/repo" and "repo" formats
                    matches = False
                    for repo_filter in repositories:
                        if "/" in repo_filter:
                            # Full format: "org/repo"
                            if repo_filter.lower() == repo_full_name.lower():
                                matches = True
                                break
                        else:
                            # Just repo name: "repo" - matches if repo name matches
                            if repo_filter.lower() == repo_name.lower():
                                matches = True
                                break

                    if matches:
                        filtered_repos.append(repo)
                # If only organizations are specified
                elif organizations:
                    if repo_owner and repo_owner.lower() in [
                        org.lower() for org in organizations
                    ]:
                        filtered_repos.append(repo)
                    # Also include user's own repos if username matches (for personal repos)
                    elif repo_owner and repo_owner.lower() == self.user.login.lower():
                        # Check if user's login is in organizations list
                        if self.user.login.lower() in [
                            org.lower() for org in organizations
                        ]:
                            filtered_repos.append(repo)

            repos = filtered_repos
            logger.info(
                f"Filtered to {len(repos)} repositories (from {len(all_repos)} total)"
            )
        else:
            repos = all_repos

        # Log repository visibility for debugging
        public_count = sum(1 for repo in repos if not repo.private)
        private_count = sum(1 for repo in repos if repo.private)

        # Check which orgs the private repos belong to
        private_org_repos = {}
        for repo in repos:
            if repo.private and "/" in repo.full_name:
                org_name = repo.full_name.split("/")[0]
                if org_name not in private_org_repos:
                    private_org_repos[org_name] = 0
                private_org_repos[org_name] += 1

        logger.info(
            f"Found {len(repos)} repositories: {public_count} public, {private_count} private"
        )

        if private_org_repos:
            logger.info(
                f"Private repositories by organization: {dict(private_org_repos)}"
            )

        # Warn if no private repos found (might indicate token permissions issue)
        if private_count == 0 and len(repos) > 0:
            logger.warning(
                "No private repositories found. Make sure your GitHub token has 'repo' scope enabled."
            )
            logger.warning(
                "Token scopes required: 'repo' (Full control of private repositories)"
            )

        return repos

    def get_commits_for_year(
        self,
        year: int,
        username: Optional[str] = None,
        organizations: Optional[List[str]] = None,
        repositories: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get all commits authored by the user in the specified year.

        Args:
            year: Year to fetch commits for
            username: GitHub username (defaults to authenticated user)

        Returns:
            List of commit dictionaries with metadata
        """
        if username is None:
            username = self.user.login

        logger.info(f"Fetching commits for {username} in year {year}")

        # Use timezone-aware datetimes (UTC) to match GitHub API
        start_date = datetime(year, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        end_date = datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)

        commits = []
        repos = self.get_user_repositories(
            organizations=organizations, repositories=repositories
        )

        private_repos_checked = 0
        private_repos_with_commits = 0
        public_repos_checked = 0
        public_repos_with_commits = 0

        for repo in repos:
            try:
                repo_type = "private" if repo.private else "public"
                if repo.private:
                    private_repos_checked += 1
                else:
                    public_repos_checked += 1

                logger.info(f"Checking {repo.full_name} ({repo_type}) for commits...")

                def fetch_repo_commits():
                    # Get commits with pagination - fetch ALL commits, then filter by date
                    # GitHub API sometimes doesn't respect date filters well, so we fetch all and filter client-side
                    return repo.get_commits(author=username)

                repo_commits = self._handle_rate_limit(fetch_repo_commits)

                # Process commits with client-side date filtering
                repo_commit_count = 0
                total_checked = 0
                for commit in repo_commits:
                    try:
                        total_checked += 1
                        commit_date = commit.commit.author.date

                        # Ensure timezone-aware for comparison
                        if commit_date.tzinfo is None:
                            commit_date = commit_date.replace(tzinfo=timezone.utc)

                        # Client-side date filtering (backup in case API filtering fails)
                        if commit_date < start_date:
                            # Commits are typically in reverse chronological order
                            # If we hit a commit before start_date, we can break (but not always reliable)
                            # So we'll continue checking but log if we see old commits
                            if (
                                repo_commit_count > 100
                            ):  # Only break if we've seen many commits
                                logger.debug(
                                    f"Reached commits before {year} in {repo.full_name}, stopping"
                                )
                                break
                            continue

                        if commit_date > end_date:
                            continue  # Skip commits after end date

                        repo_commit_count += 1
                        commit_data = {
                            "sha": commit.sha,
                            "message": commit.commit.message,
                            "author": commit.commit.author.name,
                            "date": commit_date,
                            "repository": repo.full_name,
                            "url": commit.html_url,
                            "files_changed": None,  # Will be populated if needed
                        }

                        # Get file changes if available (skip to speed up - can be slow)
                        # Uncomment if you need file details:
                        # try:
                        #     files = commit.files
                        #     commit_data["files_changed"] = len(files)
                        #     commit_data["files"] = [
                        #         {
                        #             "filename": f.filename,
                        #             "additions": f.additions,
                        #             "deletions": f.deletions,
                        #             "changes": f.changes,
                        #         }
                        #         for f in files
                        #     ]
                        # except Exception as e:
                        #     logger.debug(f"Could not fetch file changes for {commit.sha}: {e}")

                        commits.append(commit_data)
                    except Exception as e:
                        logger.warning(
                            f"Error processing commit {commit.sha} from {repo.full_name}: {e}"
                        )
                        continue

                if repo_commit_count > 0:
                    logger.info(
                        f"Found {repo_commit_count} commits from {repo.full_name} ({repo_type}) in {year}"
                    )
                    if repo.private:
                        private_repos_with_commits += 1
                    else:
                        public_repos_with_commits += 1
                else:
                    logger.debug(
                        f"No commits found in {repo.full_name} ({repo_type}) for {year}"
                    )

            except GithubException as e:
                repo_type = "private" if repo.private else "public"
                error_msg = str(e)
                org_name = (
                    repo.full_name.split("/")[0] if "/" in repo.full_name else None
                )

                if "403" in error_msg or "Forbidden" in error_msg:
                    logger.error(
                        f"Permission denied accessing {repo.full_name} ({repo_type}): {e}"
                    )
                    logger.error(
                        f"  Make sure your token has 'repo' scope and access to this repository"
                    )
                elif "404" in error_msg or "Not Found" in error_msg:
                    logger.warning(
                        f"Repository {repo.full_name} ({repo_type}) not found or not accessible: {e}"
                    )
                else:
                    logger.warning(
                        f"Error fetching commits from {repo.full_name} ({repo_type}): {e}"
                    )
                continue
            except Exception as e:
                repo_type = "private" if repo.private else "public"
                logger.error(
                    f"Unexpected error accessing {repo.full_name} ({repo_type}): {e}"
                )
                continue

        # Summary logging
        logger.info(
            f"Repository summary: {public_repos_checked} public repos checked ({public_repos_with_commits} with commits), "
            f"{private_repos_checked} private repos checked ({private_repos_with_commits} with commits)"
        )

        logger.info(f"Found {len(commits)} commits for {username} in {year}")
        return commits

    def get_user_info(self) -> Dict[str, Any]:
        """Get information about the authenticated user."""
        return {
            "login": self.user.login,
            "name": self.user.name or self.user.login,
            "email": self.user.email,
            "avatar_url": self.user.avatar_url,
        }
