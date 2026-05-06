"""
Robust parser for Power BI Tabular Model (model.bim / TMSL) files.
Handles both older (1100-1200) and newer (1500+) compatibility levels.
"""

import json
from typing import Any


def safe_get(obj: dict | None, *keys, default=None) -> Any:
    """Safely traverse nested dicts."""
    current = obj
    for k in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(k, default)
    return current


def parse_bim(raw: str) -> dict:
    """Parse a model.bim JSON string and return a structured dict of all sections."""
    data = json.loads(raw)

    # The model can be at the top level or nested under "model"
    # Older TMSL wraps in {"name": ..., "compatibilityLevel": ..., "model": {...}}
    # Newer may have the model block directly or inside a "database" wrapper.
    if "model" in data:
        model = data["model"]
        top = data
    elif "database" in data:
        model = safe_get(data, "database", "model") or {}
        top = data.get("database", data)
    else:
        # Assume the whole thing IS the model
        model = data
        top = data

    result = {
        "raw": data,
        "model_info": _parse_model_info(top, model),
        "data_sources": _parse_data_sources(model),
        "tables": _parse_tables(model),
        "columns": _parse_columns(model),
        "measures": _parse_measures(model),
        "calculated_columns": _parse_calculated_columns(model),
        "calculated_tables": _parse_calculated_tables(model),
        "partitions": _parse_partitions(model),
        "relationships": _parse_relationships(model),
        "roles": _parse_roles(model),
        "perspectives": _parse_perspectives(model),
        "hierarchies": _parse_hierarchies(model),
        "kpis": _parse_kpis(model),
        "annotations": _parse_annotations(top, model),
        "expressions": _parse_expressions(model),
        "cultures": _parse_cultures(model),
    }

    result["summary"] = _build_summary(result)
    return result


# ---------------------------------------------------------------------------
# Model info
# ---------------------------------------------------------------------------

def _parse_model_info(top: dict, model: dict) -> dict:
    return {
        "name": top.get("name", model.get("name", "N/A")),
        "description": top.get("description", model.get("description", "")),
        "compatibilityLevel": top.get("compatibilityLevel", model.get("compatibilityLevel", "N/A")),
        "culture": model.get("culture", top.get("culture", "N/A")),
        "defaultMode": model.get("defaultMode", "N/A"),
        "defaultPowerBIDataSourceVersion": model.get("defaultPowerBIDataSourceVersion", "N/A"),
        "discourageImplicitMeasures": model.get("discourageImplicitMeasures", "N/A"),
        "sourceQueryCulture": model.get("sourceQueryCulture", "N/A"),
    }


# ---------------------------------------------------------------------------
# Data sources
# ---------------------------------------------------------------------------

def _parse_data_sources(model: dict) -> list[dict]:
    sources = model.get("dataSources", [])
    results = []
    for ds in sources:
        results.append({
            "name": ds.get("name", ""),
            "type": ds.get("type", "N/A"),
            "connectionString": ds.get("connectionString", ""),
            "impersonationMode": ds.get("impersonationMode", "N/A"),
            "account": ds.get("account", ""),
            "credential": _summarise_credential(ds.get("credential", {})),
            "description": ds.get("description", ""),
            "annotations": _collect_annotations(ds),
        })
    return results


def _summarise_credential(cred: dict) -> str:
    if not cred:
        return ""
    kind = cred.get("kind", cred.get("AuthenticationKind", ""))
    path = cred.get("path", "")
    return f"{kind} ({path})" if path else str(kind)


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------

def _parse_tables(model: dict) -> list[dict]:
    tables = model.get("tables", [])
    results = []
    for t in tables:
        is_calculated = any(
            p.get("source", {}).get("type") == "calculated"
            or "expression" in p.get("source", {})
            for p in t.get("partitions", [])
            if isinstance(p.get("source"), dict)
        )
        # Also check for top-level "type" == "calculationGroup"
        table_type = t.get("type", "calculated" if is_calculated else "regular")

        results.append({
            "name": t.get("name", ""),
            "description": t.get("description", ""),
            "type": table_type,
            "isHidden": t.get("isHidden", False),
            "lineageTag": t.get("lineageTag", ""),
            "dataCategory": t.get("dataCategory", ""),
            "columns_count": len(t.get("columns", [])),
            "measures_count": len(t.get("measures", [])),
            "partitions_count": len(t.get("partitions", [])),
            "hierarchies_count": len(t.get("hierarchies", [])),
        })
    return results


# ---------------------------------------------------------------------------
# Columns
# ---------------------------------------------------------------------------

def _parse_columns(model: dict) -> list[dict]:
    rows = []
    for t in model.get("tables", []):
        tname = t.get("name", "")
        for c in t.get("columns", []):
            rows.append({
                "table": tname,
                "name": c.get("name", ""),
                "dataType": c.get("dataType", "N/A"),
                "type": c.get("type", "data"),
                "expression": _flatten_expression(c.get("expression")),
                "formatString": c.get("formatString", ""),
                "isHidden": c.get("isHidden", False),
                "isKey": c.get("isKey", False),
                "isNameInferred": c.get("isNameInferred", False),
                "isDataTypeInferred": c.get("isDataTypeInferred", False),
                "displayFolder": c.get("displayFolder", ""),
                "sortByColumn": c.get("sortByColumn", ""),
                "summarizeBy": c.get("summarizeBy", ""),
                "sourceColumn": c.get("sourceColumn", ""),
                "description": c.get("description", ""),
                "lineageTag": c.get("lineageTag", ""),
                "dataCategory": c.get("dataCategory", ""),
            })
    return rows


# ---------------------------------------------------------------------------
# Measures
# ---------------------------------------------------------------------------

def _parse_measures(model: dict) -> list[dict]:
    rows = []
    for t in model.get("tables", []):
        tname = t.get("name", "")
        for m in t.get("measures", []):
            rows.append({
                "table": tname,
                "name": m.get("name", ""),
                "expression": _flatten_expression(m.get("expression")),
                "formatString": m.get("formatString", ""),
                "displayFolder": m.get("displayFolder", ""),
                "description": m.get("description", ""),
                "isHidden": m.get("isHidden", False),
                "lineageTag": m.get("lineageTag", ""),
                "annotations": _collect_annotations(m),
                "kpi": m.get("kpi"),
            })
    return rows


# ---------------------------------------------------------------------------
# Calculated columns
# ---------------------------------------------------------------------------

def _parse_calculated_columns(model: dict) -> list[dict]:
    rows = []
    for t in model.get("tables", []):
        tname = t.get("name", "")
        for c in t.get("columns", []):
            if c.get("type") == "calculated" or c.get("expression"):
                rows.append({
                    "table": tname,
                    "name": c.get("name", ""),
                    "dataType": c.get("dataType", "N/A"),
                    "expression": _flatten_expression(c.get("expression")),
                    "formatString": c.get("formatString", ""),
                    "displayFolder": c.get("displayFolder", ""),
                    "isHidden": c.get("isHidden", False),
                    "description": c.get("description", ""),
                })
    return rows


# ---------------------------------------------------------------------------
# Calculated tables
# ---------------------------------------------------------------------------

def _parse_calculated_tables(model: dict) -> list[dict]:
    rows = []
    for t in model.get("tables", []):
        for p in t.get("partitions", []):
            src = p.get("source", {})
            if isinstance(src, dict) and src.get("type") == "calculated":
                rows.append({
                    "table": t.get("name", ""),
                    "expression": _flatten_expression(src.get("expression")),
                    "description": t.get("description", ""),
                })
                break
    return rows


# ---------------------------------------------------------------------------
# Partitions / Queries
# ---------------------------------------------------------------------------

def _parse_partitions(model: dict) -> list[dict]:
    rows = []
    for t in model.get("tables", []):
        tname = t.get("name", "")
        for p in t.get("partitions", []):
            src = p.get("source", {})
            if isinstance(src, dict):
                src_type = src.get("type", "N/A")
                expression = _flatten_expression(src.get("expression", src.get("query", "")))
            elif isinstance(src, str):
                src_type = "inline"
                expression = src
            else:
                src_type = "N/A"
                expression = ""
            rows.append({
                "table": tname,
                "partition": p.get("name", ""),
                "mode": p.get("mode", "N/A"),
                "sourceType": src_type,
                "expression": expression,
                "dataSource": p.get("dataSource", src.get("dataSource", "") if isinstance(src, dict) else ""),
            })
    return rows


# ---------------------------------------------------------------------------
# Relationships
# ---------------------------------------------------------------------------

def _parse_relationships(model: dict) -> list[dict]:
    rels = model.get("relationships", [])
    rows = []
    for r in rels:
        rows.append({
            "name": r.get("name", ""),
            "fromTable": r.get("fromTable", ""),
            "fromColumn": r.get("fromColumn", ""),
            "toTable": r.get("toTable", ""),
            "toColumn": r.get("toColumn", ""),
            "fromCardinality": r.get("fromCardinality", "many"),
            "toCardinality": r.get("toCardinality", "one"),
            "crossFilteringBehavior": r.get("crossFilteringBehavior", "oneDirection"),
            "isActive": r.get("isActive", True),
            "securityFilteringBehavior": r.get("securityFilteringBehavior", ""),
            "joinOnDateBehavior": r.get("joinOnDateBehavior", ""),
            "relyOnReferentialIntegrity": r.get("relyOnReferentialIntegrity", False),
        })
    return rows


# ---------------------------------------------------------------------------
# Roles (RLS)
# ---------------------------------------------------------------------------

def _parse_roles(model: dict) -> list[dict]:
    roles = model.get("roles", [])
    rows = []
    for role in roles:
        table_perms = []
        for tp in role.get("tablePermissions", []):
            table_perms.append({
                "table": tp.get("name", ""),
                "filterExpression": _flatten_expression(tp.get("filterExpression")),
                "metadataPermission": tp.get("metadataPermission", ""),
            })
        rows.append({
            "name": role.get("name", ""),
            "description": role.get("description", ""),
            "modelPermission": role.get("modelPermission", ""),
            "tablePermissions": table_perms,
            "annotations": _collect_annotations(role),
        })
    return rows


# ---------------------------------------------------------------------------
# Perspectives
# ---------------------------------------------------------------------------

def _parse_perspectives(model: dict) -> list[dict]:
    perps = model.get("perspectives", [])
    rows = []
    for p in perps:
        tables = []
        for pt in p.get("tables", []):
            tables.append({
                "table": pt.get("name", ""),
                "columns": [c.get("name", "") for c in pt.get("columns", [])],
                "measures": [m.get("name", "") for m in pt.get("measures", [])],
                "hierarchies": [h.get("name", "") for h in pt.get("hierarchies", [])],
            })
        rows.append({
            "name": p.get("name", ""),
            "description": p.get("description", ""),
            "tables": tables,
        })
    return rows


# ---------------------------------------------------------------------------
# Hierarchies
# ---------------------------------------------------------------------------

def _parse_hierarchies(model: dict) -> list[dict]:
    rows = []
    for t in model.get("tables", []):
        tname = t.get("name", "")
        for h in t.get("hierarchies", []):
            levels = []
            for lv in h.get("levels", []):
                levels.append({
                    "name": lv.get("name", ""),
                    "ordinal": lv.get("ordinal", 0),
                    "column": lv.get("column", ""),
                    "lineageTag": lv.get("lineageTag", ""),
                })
            rows.append({
                "table": tname,
                "name": h.get("name", ""),
                "description": h.get("description", ""),
                "isHidden": h.get("isHidden", False),
                "lineageTag": h.get("lineageTag", ""),
                "levels": levels,
                "displayFolder": h.get("displayFolder", ""),
            })
    return rows


# ---------------------------------------------------------------------------
# KPIs
# ---------------------------------------------------------------------------

def _parse_kpis(model: dict) -> list[dict]:
    rows = []
    for t in model.get("tables", []):
        tname = t.get("name", "")
        for m in t.get("measures", []):
            kpi = m.get("kpi")
            if kpi:
                rows.append({
                    "table": tname,
                    "measure": m.get("name", ""),
                    "targetExpression": _flatten_expression(kpi.get("targetExpression")),
                    "targetFormatString": kpi.get("targetFormatString", ""),
                    "statusGraphic": kpi.get("statusGraphic", ""),
                    "statusExpression": _flatten_expression(kpi.get("statusExpression")),
                    "trendGraphic": kpi.get("trendGraphic", ""),
                    "trendExpression": _flatten_expression(kpi.get("trendExpression")),
                    "annotations": _collect_annotations(kpi),
                })
    return rows


# ---------------------------------------------------------------------------
# Annotations (model-level and per-object)
# ---------------------------------------------------------------------------

def _parse_annotations(top: dict, model: dict) -> dict:
    return {
        "model": _collect_annotations(model) + _collect_annotations(top),
        "tables": {
            t.get("name", ""): _collect_annotations(t)
            for t in model.get("tables", [])
            if t.get("annotations")
        },
    }


def _collect_annotations(obj: dict) -> list[dict]:
    if not isinstance(obj, dict):
        return []
    anns = obj.get("annotations", [])
    if isinstance(anns, list):
        return [{"name": a.get("name", ""), "value": a.get("value", "")} for a in anns]
    if isinstance(anns, dict):
        return [{"name": k, "value": v} for k, v in anns.items()]
    return []


# ---------------------------------------------------------------------------
# Shared M expressions
# ---------------------------------------------------------------------------

def _parse_expressions(model: dict) -> list[dict]:
    exprs = model.get("expressions", [])
    rows = []
    for e in exprs:
        rows.append({
            "name": e.get("name", ""),
            "kind": e.get("kind", ""),
            "expression": _flatten_expression(e.get("expression")),
            "description": e.get("description", ""),
            "lineageTag": e.get("lineageTag", ""),
            "annotations": _collect_annotations(e),
        })
    return rows


# ---------------------------------------------------------------------------
# Cultures / Translations
# ---------------------------------------------------------------------------

def _parse_cultures(model: dict) -> list[dict]:
    cultures = model.get("cultures", [])
    rows = []
    for c in cultures:
        translations = {}
        lo = c.get("linguisticMetadata") or {}
        obj_trans = c.get("translations", {})
        # Newer format: translations is a dict of objects
        if isinstance(obj_trans, dict):
            translations = obj_trans
        elif isinstance(obj_trans, list):
            for tr in obj_trans:
                translations[tr.get("name", "")] = tr
        rows.append({
            "name": c.get("name", ""),
            "linguisticMetadata": bool(lo),
            "translations": translations,
        })
    return rows


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def _build_summary(result: dict) -> dict:
    calc_cols = len(result["calculated_columns"])
    regular_cols = len(result["columns"]) - calc_cols
    return {
        "tables": len(result["tables"]),
        "columns": len(result["columns"]),
        "regular_columns": regular_cols,
        "calculated_columns": calc_cols,
        "measures": len(result["measures"]),
        "calculated_tables": len(result["calculated_tables"]),
        "relationships": len(result["relationships"]),
        "roles": len(result["roles"]),
        "perspectives": len(result["perspectives"]),
        "hierarchies": len(result["hierarchies"]),
        "kpis": len(result["kpis"]),
        "data_sources": len(result["data_sources"]),
        "partitions": len(result["partitions"]),
        "expressions": len(result["expressions"]),
        "cultures": len(result["cultures"]),
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _flatten_expression(expr) -> str:
    """Expressions in BIM files can be a string or a list of strings."""
    if expr is None:
        return ""
    if isinstance(expr, list):
        return "\n".join(str(e) for e in expr)
    return str(expr)
