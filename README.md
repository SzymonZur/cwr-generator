# Creative Work Report Generator

A Python application that generates Creative Work Reports in XLSX format by analyzing your GitHub commits and linking them to Jira tickets. The system extracts commit data, identifies Jira ticket references, and generates professional summaries using AI.

## Features

- 🔍 **GitHub Integration**: Fetches all commits for a specified year from your GitHub repositories
- 🎫 **Jira Integration**: Links commits to Jira tickets using conventional commit messages
- 🤖 **AI Summarization**: Generates professional project summaries using OpenAI (optional, with fallback)
- 📊 **Excel Reports**: Generates formatted XLSX reports matching your template
- 🔧 **Flexible Filtering**: Filter by organizations and/or repositories
- 🚀 **CLI Script**: Simple command-line interface for generating reports

## Requirements

- Python 3.10 or higher
- GitHub Personal Access Token (with `repo` scope)
- Jira API Token
- OpenAI API Key (optional - will use simple text processing if not provided)

## Installation

1. **Clone the repository** (if applicable) or navigate to the project directory:
   ```bash
   cd cwr-generator
   ```

2. **Create a virtual environment**:
   ```bash
   python3.12 -m venv venv
   ```
   
   > **Note**: If you don't have Python 3.12, use `python3` or `python3.10`/`python3.11` instead.

3. **Activate the virtual environment**:
   
   On macOS/Linux:
   ```bash
   source venv/bin/activate
   ```
   
   On Windows:
   ```bash
   venv\Scripts\activate
   ```

4. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## Configuration

### 1. Create API Tokens

#### GitHub Personal Access Token

1. Go to [GitHub Settings > Developer settings > Personal access tokens > Tokens (classic)](https://github.com/settings/tokens)
2. Click **"Generate new token (classic)"**
3. Give it a descriptive name (e.g., "Creative Work Report Generator")
4. Select the following scopes:
   - ✅ **`repo`** (Full control of private repositories) - **Required for private repos**
   - ✅ **`read:user`** (Read user profile data)
5. Click **"Generate token"**
6. **Copy the token immediately** - you won't be able to see it again!

> **⚠️ Important for SSO Organizations**: If you need access to private organizations with SSO you must authorize the token:
> 1. After creating the token, GitHub will show a banner if SSO authorization is needed
> 2. Click **"Authorize"** next to the organization name
> 3. Complete the SSO authorization flow
> 4. The token must show as "Authorized" for each SSO-protected organization

#### Jira API Token

1. Go to [Atlassian Account Settings > Security > API tokens](https://id.atlassian.com/manage-profile/security/api-tokens)
2. Click **"Create API token"**
3. Give it a label (e.g., "Creative Work Report Generator")
4. Click **"Create"**
5. **Copy the token immediately** - you won't be able to see it again!

You'll also need:
- Your Jira instance URL (e.g., `https://yourcompany.atlassian.net`)
- Your Jira account email address

#### OpenAI API Key (Optional)

1. Go to [OpenAI Platform > API Keys](https://platform.openai.com/api-keys)
2. Click **"Create new secret key"**
3. Give it a name (e.g., "Creative Work Report Generator")
4. Click **"Create secret key"**
5. **Copy the key immediately** - you won't be able to see it again!

> **Note**: If you don't provide an OpenAI API key, the system will use simple text processing for summaries (no AI).

### 2. Set Environment Variables

Create a `.env` file in the project root (or export them in your shell):

```bash
# GitHub
GITHUB_TOKEN=ghp_your_github_token_here

# Jira
JIRA_URL=https://yourcompany.atlassian.net
JIRA_EMAIL=your.email@example.com
JIRA_API_TOKEN=your_jira_token_here

# OpenAI (optional)
OPENAI_API_KEY=sk-your_openai_key_here

# Company name (optional)
COMPANY_NAME=Your Company Name

# Filtering (optional - see Filtering section below)
GITHUB_ORGANIZATIONS=myorg,anotherorg
GITHUB_REPOSITORIES=myorg/my-repo
```

Alternatively, you can configure these in `config/config.yaml` (see below).

### 3. Configure `config/config.yaml` (Optional)

Edit `config/config.yaml` to set default values:

```yaml
github:
  organizations: ["myorg", "anotherorg"]  # Filter by organizations
  repositories: ["myorg/my-repo"]  # Filter by specific repositories

openai:
  model: "gpt-5.1"
  max_tokens: 500

report:
  company_name: "Your Company Name"
  default_year: null 
```

> **Note**: Environment variables override config file values. CLI arguments override both.

## Usage

Run the script directly from the command line:

```bash
# Activate virtual environment first
source venv/bin/activate

# Basic usage (uses current year and config/env defaults)
python -m src.main

# Specify year
python -m src.main --year 2024

# Specify output file
python -m src.main --year 2024 --output report_2024.xlsx

# Override tokens via CLI
python -m src.main --year 2024 \
  --github-token ghp_your_token \
  --jira-url https://yourcompany.atlassian.net \
  --jira-email your.email@example.com \
  --jira-token your_jira_token \
  --openai-key sk_your_key

# Filter by organizations
python -m src.main --year 2024 \
  --organizations myorg \
  --organizations anotherorg

# Filter by specific repositories
python -m src.main --year 2024 \
  --repositories myorg/my-repo \
  --repositories myorg/another-repo

# Verbose logging
python -m src.main --year 2024 --verbose
```

#### CLI Options

- `--year`: Year to fetch data for (default: current year)
- `--output`: Output file path (default: `report_YYYY.xlsx`)
- `--github-token`: GitHub personal access token
- `--jira-url`: Jira instance URL
- `--jira-email`: Jira account email
- `--jira-token`: Jira API token
- `--openai-key`: OpenAI API key (optional)
- `--company-name`: Company name for report
- `--organizations`: Filter by organization names (can specify multiple)
- `--repositories`: Filter by repository names (can specify multiple)
- `--config`: Path to custom config file
- `--verbose` / `-v`: Enable verbose logging

#### Filtering Rules

- **Repositories filter takes precedence**: If both `organizations` and `repositories` are specified, only repositories matching the `repositories` list will be searched.
- **Empty = All**: If no filters are specified (empty lists), all accessible repositories will be searched.
- **Case insensitive**: Matching is case-insensitive.

#### Repository Format

- **Full format**: `"org/repo"` - matches exactly `org/repo`
- **Short format**: `"repo"` - matches any repository with that name (any organization)

### Examples

```bash
# Search only in "myorg" organization
python -m src.main --year 2024 --organizations myorg

# Search only specific repositories
python -m src.main --year 2024 --repositories myorg/my-repo

# Search all (default behavior)
python -m src.main --year 2024
```

## Testing

The project includes unit tests using Python's built-in `unittest` framework. To run the tests:

### Run All Tests

```bash
# Activate virtual environment first
source venv/bin/activate

# Run all tests
python -m unittest discover -s tests -p "test_*.py"

# Or use the shorter form
python -m unittest discover
```

### Run Specific Test Files

```bash
# Run tests for a specific module
python -m unittest tests.test_report_generator
python -m unittest tests.test_data_processor
python -m unittest tests.test_jira_client

# Or run individual test files directly
python -m unittest tests/test_report_generator.py
python -m unittest tests/test_data_processor.py
python -m unittest tests/test_jira_client.py
```

### Run Specific Test Methods

```bash
# Run a specific test method
python -m unittest tests.test_report_generator.TestReportGenerator.test_load_template
```

### Verbose Output

```bash
# Run tests with verbose output
python -m unittest discover -v
```

## How It Works

1. **Fetch Commits**: Retrieves all commits from your GitHub repositories for the specified year
2. **Extract Ticket Keys**: Parses commit messages to find Jira ticket references (format: `TEXT-NUMBER`, e.g., `FUI-0`, `PROJ-123`)
3. **Fetch Jira Tickets**: Retrieves ticket details from Jira for all found ticket keys
4. **Group by Project**: Groups commits and tickets by Jira project key
5. **Generate Summaries**: Creates professional summaries for each project using AI (or simple text processing)
6. **Generate Report**: Populates the XLSX template with project data and summaries

## Output

The generated report is saved as an XLSX file (default: `report_YYYY.xlsx`) with:
- Employee information
- Company name
- Year range
- Project entries with:
  - Project number and name
  - Creative work description
  - Technical summary
  - Time allocations

## Project Structure

```
cwr-generator/
├── src/
│   ├── __init__.py
│   ├── main.py              # CLI entry point
│   ├── github_client.py    # GitHub API client
│   ├── jira_client.py       # Jira API client
│   ├── data_processor.py   # Data processing and grouping
│   ├── text_processor.py   # AI text processing
│   ├── report_generator.py # XLSX report generation
│   └── utils.py            # Utility functions
├── config/
│   └── config.yaml         # Configuration file
├── templates/
│   └── PL_time_report.xlsx
├── tests/
│   └── ...                 # Unit tests
├── venv/                   # Virtual environment (gitignored)
├── .env                    # Environment variables (gitignored)
├── requirements.txt        # Python dependencies
└── README.md               # This file
```
