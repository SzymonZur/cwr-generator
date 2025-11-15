"""Utility functions for the Creative Work Report Generator"""

import os
import yaml
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load configuration from YAML file and environment variables."""
    # Load .env file if it exists
    try:
        from dotenv import load_dotenv
        env_path = Path(__file__).parent.parent / ".env"
        load_dotenv(env_path)
    except ImportError:
        pass  # python-dotenv not available
    
    if config_path is None:
        config_path = Path(__file__).parent.parent / "config" / "config.yaml"
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Override with environment variables
    if os.getenv("GITHUB_TOKEN"):
        config["github"]["token"] = os.getenv("GITHUB_TOKEN")
    
    if os.getenv("JIRA_URL"):
        config["jira"]["url"] = os.getenv("JIRA_URL")
    if os.getenv("JIRA_EMAIL"):
        config["jira"]["email"] = os.getenv("JIRA_EMAIL")
    if os.getenv("JIRA_API_TOKEN"):
        config["jira"]["api_token"] = os.getenv("JIRA_API_TOKEN")
    
    if os.getenv("OPENAI_API_KEY"):
        config["openai"]["api_key"] = os.getenv("OPENAI_API_KEY")
    
    if os.getenv("COMPANY_NAME"):
        config["report"]["company_name"] = os.getenv("COMPANY_NAME")
    
    # Handle GitHub organization/repository filters from environment
    if os.getenv("GITHUB_ORGANIZATIONS"):
        orgs = [org.strip() for org in os.getenv("GITHUB_ORGANIZATIONS").split(",") if org.strip()]
        config["github"]["organizations"] = orgs
    
    if os.getenv("GITHUB_REPOSITORIES"):
        repos = [repo.strip() for repo in os.getenv("GITHUB_REPOSITORIES").split(",") if repo.strip()]
        config["github"]["repositories"] = repos
    
    return config


def setup_logging(level: str = "INFO", format_string: Optional[str] = None):
    """Set up logging configuration."""
    if format_string is None:
        format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format=format_string,
        datefmt="%Y-%m-%d %H:%M:%S"
    )


def get_year_range(year: int) -> tuple[datetime, datetime]:
    """Get start and end datetime for a given year."""
    start = datetime(year, 1, 1, 0, 0, 0)
    end = datetime(year, 12, 31, 23, 59, 59)
    return start, end


def format_date_for_excel(date: datetime) -> str:
    """Format date as DD MM YYYY for Excel."""
    return date.strftime("%d %m %Y")


def get_template_path() -> Path:
    """Get the path to the Excel template."""
    return Path(__file__).parent.parent / "templates" / "PL_time_report.xlsx"

