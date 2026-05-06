"""
Converts Power BI measures to Databricks Metrics View YAML
using a Claude serving endpoint on Databricks.
Handles two scenarios:
1. DAX expression available → convert DAX to Metrics View
2. DAX expression NOT available → infer from measure name + table columns, then convert
"""

import os
import requests
from metrics_view_docs import METRICS_VIEW_DOCS


SERVING_ENDPOINT = "databricks-claude-sonnet-4"

SYSTEM_PROMPT = f"""You are an expert in Power BI DAX and Databricks Metrics Views.

Here is the COMPLETE official Databricks Metrics View documentation:

{METRICS_VIEW_DOCS}

You have two tasks depending on input:

TASK 1 - If a DAX expression is provided:
Convert it to a Databricks Metrics View YAML definition following the official docs above.

TASK 2 - If NO DAX expression is provided (only measure name + table + columns):
First infer what the likely DAX expression is, then convert to Metrics View YAML.

Rules:
- Always use version 1.1
- Apply full semantic metadata: display_name, comment (include original DAX), format, synonyms
- Use MEASURE() for composed measures
- CALCULATE(..., ALL(...)) → use window measures with range: all, semiadditive: last (LOD pattern)
- RELATED() → use joins section
- Use snake_case for names
- Pick relevant dimensions (dates, countries, categories - NOT ids or free text)

Output format - ALWAYS output exactly two sections separated by "---DAX---" and "---YAML---":

---DAX---
<the DAX expression, either original or inferred>
---YAML---
<the Metrics View YAML>

No markdown fences, no explanations outside these sections."""


def _get_credentials():
    """Get Databricks workspace host and token."""
    workspace_host = os.environ.get(
        "DATABRICKS_HOST",
        os.environ.get("DB_HOST", ""),
    )
    token = os.environ.get(
        "DATABRICKS_TOKEN",
        os.environ.get("DB_TOKEN", ""),
    )

    if not workspace_host or not token:
        try:
            from databricks.sdk import WorkspaceClient
            w = WorkspaceClient()
            workspace_host = w.config.host
            token = w.config.token
        except Exception:
            return None, None

    return workspace_host.rstrip("/"), token


def _call_claude(user_message: str) -> str:
    """Call Claude via Databricks serving endpoint."""
    workspace_host, token = _get_credentials()
    if not workspace_host or not token:
        return "Error: No Databricks credentials available"

    url = f"{workspace_host}/serving-endpoints/{SERVING_ENDPOINT}/invocations"

    payload = {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        "max_tokens": 2000,
        "temperature": 0.1,
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=60)
        resp.raise_for_status()
        result = resp.json()
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        content = content.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            content = "\n".join(lines)
        return content.strip()
    except requests.exceptions.HTTPError as e:
        return f"Error calling endpoint: {e.response.status_code} - {e.response.text[:300]}"
    except Exception as e:
        return f"Error: {str(e)}"


def convert_measure_to_metrics_view(
    measure_name: str,
    table_name: str,
    columns: list[str] | None = None,
    dax_expression: str = "",
) -> dict:
    """Convert a measure to Metrics View YAML via Claude.

    Returns: {"dax": str, "yaml": str, "error": str}
    """
    columns_context = ""
    if columns:
        columns_context = f"\nAvailable columns in table '{table_name}': {', '.join(columns)}"

    if dax_expression and not dax_expression.startswith("//"):
        # Has real DAX expression
        user_message = f"""Convert this Power BI DAX measure to a Databricks Metrics View YAML definition.

Measure name: {measure_name}
Table: {table_name}
DAX Expression: {dax_expression}
{columns_context}

Generate a complete Metrics View YAML that is transversal across multiple initiatives.
Include appropriate dimensions from the available columns.
Use the ---DAX--- and ---YAML--- format."""
    else:
        # No DAX - infer it
        user_message = f"""Infer the most likely DAX expression for this Power BI measure, then convert it to a Databricks Metrics View YAML.

Measure name: {measure_name}
Table: {table_name}
{columns_context}

Based on the measure name and available columns, determine what this measure likely calculates.
Then generate the Metrics View YAML.
Use the ---DAX--- and ---YAML--- format."""

    raw_response = _call_claude(user_message)

    if raw_response.startswith("Error"):
        return {"dax": dax_expression, "yaml": "", "error": raw_response}

    # Parse response
    dax_part = dax_expression
    yaml_part = raw_response

    if "---DAX---" in raw_response and "---YAML---" in raw_response:
        parts = raw_response.split("---YAML---")
        yaml_part = parts[-1].strip() if len(parts) > 1 else ""
        dax_section = parts[0]
        if "---DAX---" in dax_section:
            dax_part = dax_section.split("---DAX---")[-1].strip()
    elif "---YAML---" in raw_response:
        yaml_part = raw_response.split("---YAML---")[-1].strip()

    return {"dax": dax_part, "yaml": yaml_part, "error": ""}
