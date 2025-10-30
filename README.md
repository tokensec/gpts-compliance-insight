## 🧩 GPTs Compliance Insights (GCI)

An open-source project led by Sharon Shama and developed by Gil Portnoy

### 🔍 Overview

**GPTs Compliance Insights (GCI)** is a CLI open-source tool built to help enterprises and developers maintain transparency and compliance across their custom GPTs.

Leveraging OpenAI’s **Compliance API**, the tool automatically generates clear, concise, and structured reports about your GPT configurations, shared users, and linked files - enabling efficient auditing and risk assessment.

<p align="left">
  <img src="https://github.com/user-attachments/assets/1ec54c28-d3d4-4039-860f-4015e8a10290" alt="Custom Action Demo" width="45%">
  <img src="https://github.com/user-attachments/assets/5801965d-23df-42a4-a736-4cb68e1b9ba6" alt="Risk Scoring Demo" width="45%">
</p>


**Note**: This tool requires an **OpenAI Enterprise account** with access to the Compliance API. The Compliance API is not available for standard OpenAI accounts.

## Prerequisites

- Python 3.9+
- **OpenAI Enterprise account** with Compliance API access
- OpenAI Compliance API key and workspace ID ([How to generate API key](https://help.openai.com/en/articles/9261474-compliance-api-for-enterprise-customers))
- (Optional) LLM API key for risk analysis (OpenAI, Anthropic, or AWS Bedrock)

## Installation

### Step 1: Clone the repository

```bash
git clone https://github.com/your-org/gpts-compliance-insights.git
cd gpts-compliance-insights
```

### Step 2: Install dependencies

```bash
# Using pip
pip install -e .

# Or using uv (faster alternative, optional - install with: pip install uv)
uv sync
uv pip install -e .
```

### Step 3: Configure environment variables

```bash
# Required: OpenAI Compliance API credentials
export GCI_OPENAI_API_KEY="your-openai-compliance-api-key"
export GCI_OPENAI_WORKSPACE_ID="your-workspace-id"

# Optional: For risk analysis features
export GCI_LLM_PROVIDER="openai"  # Options: openai, anthropic, bedrock
export OPENAI_API_KEY="your-openai-api-key"  # For GPT models
export ANTHROPIC_API_KEY="your-anthropic-api-key"  # For Claude models
export AWS_REGION="us-east-1"  # For AWS Bedrock
export AWS_PROFILE="your-aws-profile"  # For AWS Bedrock
```

## Usage

### Download GPT Configurations

The `download` command fetches all GPT configurations from your OpenAI workspace and stores them locally for offline analysis. This reduces API calls and speeds up subsequent operations.

```bash
# Download and cache GPT data locally
gci download

# Data is saved in ~/.gci/cache/ for offline use

# Force refresh the cache
gci download --force

# Download from a specific workspace
gci download --workspace-id ws_abc123
```

### List and Search GPTs

View and search through your downloaded GPT configurations.

```bash
# List all GPTs (TUI mode by default)
gci list

# Search for specific GPTs
gci list --search "employee"

# Disable TUI for simple table output
gci list --no-tui

# Export to different formats
gci list --format json --output gpts.json
gci list --format csv --output gpts.csv
```

### Risk Classification

Analyze GPTs for security risks, PII exposure, and compliance issues using LLM analysis.

**Privacy Note**: All analysis is performed using your own LLM provider. Your GPT data is processed locally and sent only to the LLM provider you configure.

```bash
# Analyze all GPTs for risks
gci risk-classifier

# Use different LLM providers
gci risk-classifier --llm-provider anthropic --llm-model claude-3-sonnet-20240229
gci risk-classifier --llm-provider openai --llm-model gpt-4-turbo

# Export risk reports
gci risk-classifier --format json --output risk_report.json
gci risk-classifier --format csv --output risk_report.csv

# Analyze specific GPTs
gci risk-classifier --search "HR" --format table

# Process in batches for large workspaces
gci risk-classifier --batch-size 10 --limit 50
```

### Custom Actions Analysis

Identify and analyze external API integrations and custom actions in your GPTs using the same LLM provider configuration.

```bash
# Analyze all custom actions and API integrations
gci custom-actions

# Use different LLM providers (same as risk-classifier)
gci custom-actions --llm-provider anthropic --llm-model claude-3-sonnet-20240229

# Export detailed analysis
gci custom-actions --format json --output actions_report.json
gci custom-actions --format csv --output actions_report.csv

# Filter by GPT name
gci custom-actions --search "sales" --format table
```

## Environment Variables

### Required

```bash
GCI_OPENAI_API_KEY        # OpenAI Compliance API key (Enterprise accounts only)
GCI_OPENAI_WORKSPACE_ID   # OpenAI workspace ID
```

### Optional

```bash
GCI_LLM_PROVIDER      # LLM provider (default: openai)
GCI_LLM_MODEL         # Model name (default: gpt-4-turbo)
GCI_LLM_TEMPERATURE   # Model temperature (default: 0.1)
GCI_OUTPUT_DIR        # Output directory (default: ./reports)

# Provider-specific - see LiteLLM docs for your provider's requirements
OPENAI_API_KEY        # For OpenAI models
ANTHROPIC_API_KEY     # For Anthropic models
AWS_REGION            # For AWS Bedrock
AWS_PROFILE           # For AWS Bedrock
```

#### LLM Support

GCI uses [LiteLLM](https://docs.litellm.ai/docs/providers) which supports 100+ LLM providers including OpenAI, Anthropic, AWS Bedrock, Google Vertex AI, Azure, Ollama (local models), and many more. Configure your provider using standard environment variables as documented by LiteLLM.

## Examples

### Basic Workflow

```bash
# 1. Download GPT data
gci download

# 2. View GPTs interactively
gci list

# 3. Analyze security risks
gci risk-classifier

# 4. Export reports
gci risk-classifier --format csv --output gpt_risks.csv
gci custom-actions --format csv --output api_integrations.csv
```

### Using Different LLM Providers

```bash
# OpenAI GPT-4
gci risk-classifier --llm-provider openai --llm-model gpt-4-turbo

# Anthropic Claude
export ANTHROPIC_API_KEY="your-key"
gci risk-classifier --llm-provider anthropic --llm-model claude-3-opus-20240229

# AWS Bedrock
AWS_REGION=us-east-1 AWS_PROFILE=prod gci risk-classifier \
  --llm-provider bedrock \
  --llm-model anthropic.claude-3-sonnet-20240229-v1:0

# See LiteLLM docs for configuring other providers like Ollama, Azure, Google Vertex AI, etc.
```

### Batch Processing Multiple Workspaces

```bash
for ws in ws_prod ws_dev ws_staging; do
  echo "Processing workspace: $ws"
  gci download --workspace-id $ws
  gci risk-classifier --workspace-id $ws --format json --output "${ws}_risk.json"
  gci custom-actions --workspace-id $ws --format csv --output "${ws}_actions.csv"
done
```

## Troubleshooting

### Common Issues

1. **"TUI mode not working"**: 
   - TUI is enabled by default for `gci list`
   - Use `gci list --no-tui` to disable TUI
   - Ensure data is cached first with `gci download`
   - TUI not available for risk-classifier or custom-actions

2. **"Risk classifier fails"**: 
   - Ensure you have configured an LLM API key:
     - For OpenAI: `export OPENAI_API_KEY="your-key"`
     - For Anthropic: `export ANTHROPIC_API_KEY="your-key"`
     - For AWS Bedrock: Configure AWS credentials
   - Ensure you have downloaded GPT data first: `gci download`

3. **"No GPTs found"**: 
   - Run `gci download` first to fetch and cache GPT data
   - Check that your workspace has GPTs configured

4. **"Authentication error"**: 
   - Verify your OpenAI Compliance API credentials:
   ```bash
   echo $GCI_OPENAI_API_KEY
   echo $GCI_OPENAI_WORKSPACE_ID
   ```
   - Ensure your API key has access to the Compliance API

5. **"UV not found"**:
   - UV is an optional faster alternative to pip
   - Just use pip instead: `pip install -e .`

## License

MIT
