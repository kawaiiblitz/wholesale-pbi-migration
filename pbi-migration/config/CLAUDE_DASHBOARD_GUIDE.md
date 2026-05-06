# Dashboard Development with Claude Code

This repo contains an AI BI Dashboard for Databricks.

## Critical Rules

**File Extension:** Dashboard files MUST use `.lvdash.json` extension (not `.json`). Files without this extension will be rejected on import.

**Git Workflow:** Always commit before and after major changes. This lets you roll back if something breaks.

## Dashboard JSON Structure

```json
{
  "datasets": [...],    // SQL query definitions
  "pages": [...],       // Page layouts and widgets
  "uiSettings": {...}   // Dashboard UI configuration
}
```

### Datasets

Each dataset has:
- `name`: 8-character hex identifier (e.g., "e924c6a9") - **MUST remain stable** as widgets reference these
- `displayName`: Human-readable name shown in the UI
- `queryLines`: Array of SQL query strings (one element per line)

### Pages

Each page contains:
- `displayName`: Page title
- `layout`: Array of positioned widgets with coordinates and visualization specs

## Naming Conventions

**ALWAYS check existing patterns before adding new datasets.** Use full names, not abbreviations:

- "Weekly Engaged Customers" - NOT "WEC"
- "High QPS Engaged Revenue T7D" - NOT "HQR"
- "Storage Optimized Weekly Active Customers" - NOT "SO WAC"

Check existing patterns:
```bash
jq '.datasets[] | select(.displayName | test("engaged|Engaged"; "i")) | .displayName' dashboard.lvdash.json
```

## SQL Patterns

**Workspace Filtering:** Always exclude internal Databricks workspaces:
```sql
WHERE salesforce_account_name NOT IN ('Databricks', 'Microsoft', 'Databricks Labs')
```

**Date Boundaries:** Exclude incomplete current day data:
```sql
WHERE CAST(_partition_date AS DATE) <= date_add(now(), -1)
```

## MCP Validation (CRITICAL)

**NEVER ask the user to verify something - use MCP tools yourself.**

Before delivering any dashboard changes:
1. Extract each modified SQL query from the JSON
2. Test each query via MCP (add `LIMIT 1` to make it fast)
3. Only deliver after ALL queries pass

```bash
# Test a query
mcp-cli call databricks/execute_parameterized_sql '{"statement": "SELECT * FROM my_table LIMIT 1", "parameters": []}'
```

## Table Widget Rules

**NEVER create table widgets from scratch.** Always:
1. Copy an existing working table widget exactly
2. Only change: `widget.name`, `queries[0].query.datasetName`, `spec.frame.title`, `position`
3. Keep ALL column properties - they're required for import validation

Required properties that MUST be present:
- `invisibleColumns: []` - even if empty
- All column properties including: fieldName, title, type, displayAs, visible, order, plus format-specific properties

## Counter Widget Rules

**Counters with comparison (target):**
- Use ACTUAL MEASURE columns from the dataset, NEVER COUNT(*)
- `"value"` encoding → the first MEASURE column
- `"target"` encoding → the second MEASURE column
- ALWAYS include `"change": {"type": "percent"}` inside target to show the ↑/↓ percentage
- Do NOT add `"displayName"` or `"scale"` inside target
- The ONLY valid properties inside `"target"` are `"fieldName"` and `"change"`

```json
"encodings": {
  "value": {"fieldName": "sum(first_measure)"},
  "target": {"fieldName": "sum(second_measure)", "change": {"type": "percent"}}
}
```

## Useful jq Commands

```bash
# List all datasets
jq -r '.datasets[] | "\(.name): \(.displayName)"' dashboard.lvdash.json

# Get page summary
jq '.pages[] | {page: .displayName, widgetCount: (.layout | length)}' dashboard.lvdash.json

# Find datasets by keyword
jq '.datasets[] | select(.displayName | contains("Revenue"))' dashboard.lvdash.json

# Examine specific dataset
jq '.datasets[] | select(.name == "e924c6a9")' dashboard.lvdash.json
```
