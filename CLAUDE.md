# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

GPTs Compliance Insights (GCI) is a Python CLI tool for auditing OpenAI GPT configurations for compliance, security risks, and data exposure using the OpenAI Compliance API.

## Commands

### Development Setup
```bash
# Install dependencies
uv sync

# Activate virtual environment (if needed)
source .venv/bin/activate
```

### CLI Usage
```bash
# Main CLI entry point
gci --help

# Download GPT data from workspace
gci download [--workspace-id <id>]

# List GPTs with various output formats
gci list [--search <term>] [--format table|json|csv|tui]

# Analyze security risks
gci risk-classifier [--llm-provider <provider>] [--format <format>] [--output <file>]

# Analyze custom actions/API integrations
gci custom-actions [--format <format>] [--output <file>]
```

### Development Commands
```bash
# Type checking (strict mode enabled)
pyright

# Code linting and formatting
ruff check
ruff format

# Check specific directory
pyright gci/
ruff check gci/
```

## Architecture

### CLI Structure
- **Entry point**: `gci/cli/main.py` - Typer-based CLI application
- **Commands**: `gci/cli/commands/` - Individual command implementations
  - `download.py` - GPT data downloading and caching
  - `list.py` - GPT listing with search and export
  - `list_tui.py` - Interactive TUI using Textual framework
  - `risk.py` - Risk classification using LLM analysis
  - `action.py` - Custom action analysis

### Core Components
- **API Client** (`gci/api/client.py`): OpenAI Compliance API integration with retry logic, rate limiting, and comprehensive error handling
- **Cache Layer** (`gci/cache/`): Disk-based caching to minimize API calls and improve performance
- **LLM Integration** (`gci/llm/`): Multi-provider LLM support (OpenAI, Anthropic, AWS Bedrock) for risk analysis
- **Models** (`gci/models/`): Pydantic data models matching OpenAI Compliance API responses
- **Services** (`gci/services/`): Business logic for risk classification and action analysis

### Key Models
- **GPT** (`gci/models/gpt.py`): Complete GPT structure with configurations, files, tools, and sharing settings
- **Risk** (`gci/models/risk.py`): Risk assessment results with severity levels and explanations
- **Action** (`gci/models/action.py`): Custom action analysis with API endpoint details

## Configuration

### Required Environment Variables
```bash
GCI_OPENAI_API_KEY="your-openai-compliance-api-key"  # OpenAI Compliance API key
GCI_OPENAI_WORKSPACE_ID="your-workspace-id"  # OpenAI workspace ID
```

### Optional Environment Variables
```bash
GCI_LLM_PROVIDER="openai|anthropic|bedrock"  # Default: openai
GCI_LLM_MODEL="model-name"                   # Default: gpt-4-turbo
GCI_LLM_TEMPERATURE="0.1"                    # Default: 0.1
GCI_OUTPUT_DIR="./reports"                   # Default: ./reports
ANTHROPIC_API_KEY="for-claude-models"        # For Anthropic provider
AWS_REGION="us-east-1"                       # For Bedrock provider
AWS_PROFILE="profile-name"                   # For Bedrock provider
```

## Development Patterns

### Error Handling
- Comprehensive exception hierarchy in `gci/exceptions.py`
- API errors mapped to specific exception types (AuthenticationError, RateLimitError, etc.)
- Backoff retry logic with exponential backoff for transient failures

### Data Flow
1. **Download**: API client fetches GPT data → Cache manager stores locally
2. **List**: Cache provides data → Formatters output in various formats (JSON, CSV, TUI)
3. **Risk Analysis**: Cache provides GPT data → LLM client analyzes → Risk models store results
4. **Action Analysis**: Cache provides GPT data → Service extracts custom actions → Analysis results

### Output Formats
- **table**: Rich table output for terminal viewing
- **json**: JSON format for programmatic use
- **csv**: CSV format for spreadsheet applications
- **tui**: Interactive Textual-based interface
- **xlsx**: Excel format (for risk classifier)

### Caching Strategy
- GPT data cached locally using diskcache
- Cache keys based on workspace ID and API parameters
- Automatic cache invalidation and refresh capabilities
- Reduces API calls and improves performance

## Testing

Currently no test suite exists. When adding tests, use pytest with the dev dependencies already configured in pyproject.toml.