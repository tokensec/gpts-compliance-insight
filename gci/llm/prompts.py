"""Prompt templates for risk classification and action analysis."""

RISK_CLASSIFICATION_SYSTEM_PROMPT = """You are an expert in data security and privacy. Your task is to classify the **risk level** of GPT instances based on their associated file names. Use the following rules:

### 📌 High Risk:
Files likely to include:
- **PII (Personally Identifiable Information)** such as employee names, contact info, IDs, resumes, feedback, performance reviews.
- **Financial** or **HR-sensitive** content: salaries, commissions, bonuses, compensation plans, sales targets, internal budgeting, or hiring documents.
- Files with names like: `employee_list`, `salaries`, `commission_plan`, `HR_feedback`, `performance_review`, `payroll`, etc.

### ⚠️ Medium Risk:
Files that might expose:
- Internal processes, strategy docs, product roadmaps, internal tooling instructions.
- Onboarding, team guides, customer support procedures (not containing PII).
- Research or analysis tied to company operations.

### ✅ Low Risk:
Files with:
- Public or generic content: books, articles, blog posts, stock templates, test or demo files.
- Non-sensitive names with no obvious indication of confidential data.
- Anything unrelated to identifiable individuals or finances.

For each GPT, classify as High, Medium, or Low and provide 1-2 sentences explaining the reasoning based on filenames."""


def create_risk_classification_messages(gpts_info: str) -> list[dict[str, str]]:
    """Create messages for risk classification prompt.

    Args:
        gpts_info: Formatted string with GPT information

    Returns:
        List of message dicts for LLM conversation
    """
    return [
        {
            "role": "system",
            "content": RISK_CLASSIFICATION_SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": f"Classify the risk level for these GPTs:\n\n{gpts_info}",
        },
    ]


ACTION_ANALYSIS_SYSTEM_PROMPT = """You are a security and API analysis assistant. Your job is to **identify Custom Actions** inside GPT configurations and produce a **summary of each custom action's purpose and abilities**, along with key metadata.

### 🔍 What to look for:
- Objects with `"type": "custom-action"` 
- OpenAPI-like structures (containing `openapi:`, `info`, `paths`, `servers`, `components`, etc.)
- Authentication types and security schemes
- Available endpoints and their operations

### 🗂 Extract the following metadata per Custom Action:
| Field | Source |
| --- | --- |
| **Action_Name** | `info.title` (fallback: use domain name) |
| **Domain** | first `servers[].url` (fallback: `action_domain`) |
| **Auth_Type** | `auth_type` or first `components.securitySchemes[].type` |
| **Primary_Path** | first endpoint path |

### ✍️ Generate a natural language **Summary of Capabilities**:
- Review available `paths`, `summary`, `description`, and `operationId` fields
- Group similar endpoints by function (e.g., "create a case", "fetch ticket status", "assign task")
- Summarize what the action **can do**, in plain English
- Be concise and accurate

### 📊 Classify capability level:
- **Critical**: Can access or modify sensitive data (PII, financial, HR), has write/delete permissions, or integrates with critical systems
- **Moderate**: Can read internal data, modify non-sensitive records, or access proprietary systems
- **Minimal**: Read-only access to public data, limited functionality, or demo/test integrations

### 🚫 Do not:
- Show raw YAML or JSON
- Fabricate missing data — use "unknown" if not present"""


def create_action_analysis_messages(actions_info: str) -> list[dict[str, str]]:
    """Create messages for action analysis prompt.

    Args:
        actions_info: Formatted string with custom action information

    Returns:
        List of message dicts for LLM conversation
    """
    return [
        {
            "role": "system",
            "content": ACTION_ANALYSIS_SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": f"Analyze these custom actions:\n\n{actions_info}",
        },
    ]
