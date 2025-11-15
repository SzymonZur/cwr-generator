"""Main CLI interface for Creative Work Report Generator."""

import click
import logging
import sys
import time
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils import load_config, setup_logging, get_template_path
from src.github_client import GitHubClient
from src.jira_client import JiraClient
from src.data_processor import DataProcessor
from src.text_processor import TextProcessor
from src.report_generator import ReportGenerator


@click.command()
@click.option(
    "--year",
    type=int,
    default=None,
    help="Year to fetch data for (default: current year)",
)
@click.option(
    "--output",
    type=click.Path(),
    default=None,
    help="Output file path (default: report_YYYY.xlsx)",
)
@click.option(
    "--github-token", envvar="GITHUB_TOKEN", help="GitHub personal access token"
)
@click.option("--jira-url", envvar="JIRA_URL", help="Jira instance URL")
@click.option("--jira-email", envvar="JIRA_EMAIL", help="Jira account email")
@click.option("--jira-token", envvar="JIRA_API_TOKEN", help="Jira API token")
@click.option("--openai-key", envvar="OPENAI_API_KEY", help="OpenAI API key")
@click.option("--company-name", envvar="COMPANY_NAME", help="Company name for report")
@click.option(
    "--organizations",
    multiple=True,
    help="Filter by organization names (can specify multiple: --organizations org1 --organizations org2)",
)
@click.option(
    "--repositories",
    multiple=True,
    help='Filter by repository names in format "org/repo" or "repo" (can specify multiple: --repositories org1/repo1 --repositories repo2)',
)
@click.option("--config", type=click.Path(), help="Path to config file")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
def main(
    year,
    output,
    github_token,
    jira_url,
    jira_email,
    jira_token,
    openai_key,
    company_name,
    organizations,
    repositories,
    config,
    verbose,
):
    """Generate Creative Work Report from GitHub and Jira data."""

    # Setup logging
    log_level = "DEBUG" if verbose else "INFO"
    setup_logging(log_level)
    logger = logging.getLogger(__name__)

    try:
        # Load configuration
        cfg = load_config(config)

        # Override with CLI arguments
        if github_token:
            cfg["github"]["token"] = github_token
        if jira_url:
            cfg["jira"]["url"] = jira_url
        if jira_email:
            cfg["jira"]["email"] = jira_email
        if jira_token:
            cfg["jira"]["api_token"] = jira_token
        if openai_key:
            cfg["openai"]["api_key"] = openai_key
        if company_name:
            cfg["report"]["company_name"] = company_name

        # Handle organization and repository filters
        # Empty lists mean "search all"
        orgs_filter = (
            list(organizations)
            if organizations
            else (cfg["github"].get("organizations") or [])
        )
        repos_filter = (
            list(repositories)
            if repositories
            else (cfg["github"].get("repositories") or [])
        )

        # Convert empty lists to None for "search all" behavior
        orgs_filter = orgs_filter if orgs_filter else None
        repos_filter = repos_filter if repos_filter else None

        if orgs_filter:
            logger.info(f"Filtering by organizations: {orgs_filter}")
        if repos_filter:
            logger.info(f"Filtering by repositories: {repos_filter}")
        if not orgs_filter and not repos_filter:
            logger.info("No filters specified - searching all repositories")

        # Validate required configuration
        if not cfg["github"].get("token"):
            raise ValueError(
                "GitHub token is required. Set GITHUB_TOKEN environment variable or use --github-token"
            )
        if not cfg["jira"].get("url"):
            raise ValueError(
                "Jira URL is required. Set JIRA_URL environment variable or use --jira-url"
            )
        if not cfg["jira"].get("email"):
            raise ValueError(
                "Jira email is required. Set JIRA_EMAIL environment variable or use --jira-email"
            )
        if not cfg["jira"].get("api_token"):
            raise ValueError(
                "Jira API token is required. Set JIRA_API_TOKEN environment variable or use --jira-token"
            )
        # OpenAI API key is optional - will use simple text processing if not provided
        if not cfg["openai"].get("api_key"):
            logger.warning(
                "OpenAI API key not provided. Summaries will be generated using simple text processing (no AI)."
            )

        # Set year
        if year is None:
            year = cfg["report"].get("default_year") or datetime.now().year

        # Set output path
        if output is None:
            output = Path(f"report_{year}.xlsx")
        else:
            output = Path(output)

        logger.info(f"Generating Creative Work Report for year {year}")

        # Initialize clients
        logger.info("Initializing clients...")
        github_client = GitHubClient(
            token=cfg["github"]["token"],
            max_retries=cfg["github"].get("max_retries", 3),
        )

        jira_client = JiraClient(
            url=cfg["jira"]["url"],
            email=cfg["jira"]["email"],
            api_token=cfg["jira"]["api_token"],
            max_retries=cfg["jira"].get("max_retries", 3),
        )

        # Get user info
        user_info = github_client.get_user_info()
        employee_name = user_info.get("name", user_info.get("login", "User"))
        company = cfg["report"].get("company_name", "")

        logger.info(f"Employee: {employee_name}")

        # Fetch data from GitHub
        logger.info("Fetching data from GitHub...")
        commits = github_client.get_commits_for_year(
            year,
            organizations=orgs_filter if orgs_filter else None,
            repositories=repos_filter if repos_filter else None,
        )
        logger.info(f"Found {len(commits)} commits for year {year}")

        # Extract Jira ticket keys
        logger.info("Extracting Jira ticket keys...")
        all_ticket_keys = jira_client.extract_tickets_from_commits(commits)

        logger.info(f"Found {len(all_ticket_keys)} unique Jira ticket keys")

        # Fetch Jira tickets
        tickets = {}
        if all_ticket_keys:
            logger.info("Fetching Jira ticket details...")
            tickets = jira_client.get_tickets(all_ticket_keys)
            logger.info(f"Fetched {len(tickets)} tickets")

        # Process data
        logger.info("Processing and grouping data...")
        data_processor = DataProcessor(jira_client)
        projects = data_processor.process_data(commits, tickets)

        logger.info(f"Grouped into {len(projects)} projects")

        # Generate summaries
        logger.info("Generating summaries...")
        openai_key = cfg["openai"].get("api_key")
        use_ai = openai_key is not None and openai_key != ""

        if not use_ai:
            logger.warning(
                "OpenAI API key not provided. Using simple text processing for summaries."
            )

        text_processor = TextProcessor(
            api_key=openai_key,
            model=cfg["openai"].get("model", "gpt-5"),
            max_tokens=cfg["openai"].get("max_tokens", 50000),
            use_ai=use_ai,
        )

        project_summaries = {}
        project_count = len(projects)
        for idx, (project_key, project_data) in enumerate(projects.items(), 1):
            logger.info(
                f"Generating summary {idx}/{project_count} for {project_key}..."
            )
            summary_data = data_processor.get_project_summary_data(
                project_key, project_data
            )
            summary = text_processor.generate_project_summary(summary_data)
            project_summaries[project_key] = summary

            # Add delay between AI requests to avoid rate limits (only if using AI)
            if text_processor.use_ai and idx < project_count:
                delay = 2  # 2 second delay between requests
                logger.debug(f"Waiting {delay} seconds before next AI request...")
                time.sleep(delay)

        logger.info("Summaries generated")

        # Generate report
        logger.info("Generating Excel report...")
        template_path = get_template_path()
        report_generator = ReportGenerator(template_path)

        report_generator.generate_report(
            employee_name=employee_name,
            company_name=company,
            year=year,
            projects=projects,
            project_summaries=project_summaries,
        )

        report_generator.save_report(output)

        logger.info(f"Report generated successfully: {output}")
        click.echo(f"✓ Report generated: {output}")
        click.echo(f"  - Year: {year}")
        click.echo(f"  - Employee: {employee_name}")
        click.echo(f"  - Projects: {len(projects)}")
        click.echo(f"  - Commits: {len(commits)}")
        click.echo(f"  - Tickets: {len(tickets)}")

    except Exception as e:
        logger.error(f"Error generating report: {e}", exc_info=True)
        click.echo(f"✗ Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
