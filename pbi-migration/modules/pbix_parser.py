"""
Parser for Power BI .pbix files.
Extracts the file as a ZIP and parses Report/Layout for visualizations
and DataModel for the tabular model (using pbixray for DAX extraction).
"""

import io
import json
import re
import zipfile
from collections import defaultdict


def _extract_measures_from_datamodel(file_bytes: bytes) -> dict:
    """Extract measure DAX expressions from the DataModel using pbixray.

    Returns: {("TableName", "MeasureName"): "DAX expression"}
    """
    measures = {}
    try:
        from pbixray import PBIXRay
        model = PBIXRay(io.BytesIO(file_bytes))

        # pbixray exposes DAX measures via .dax_measures property (returns DataFrame)
        if hasattr(model, 'dax_measures') and model.dax_measures is not None:
            mdf = model.dax_measures
            if hasattr(mdf, 'iterrows'):
                for _, row in mdf.iterrows():
                    table = str(row.get('TableName', ''))
                    name = str(row.get('Name', ''))
                    expr = str(row.get('Expression', ''))
                    if table and name and expr and expr != 'nan':
                        measures[(table, name)] = expr
    except ImportError:
        pass  # pbixray not available
    except Exception as e:
        # Store error for debugging
        measures["_error"] = str(e)
    return measures


def parse_pbix(file_bytes: bytes) -> dict:
    """Parse a .pbix file (ZIP) and return structured visualization + model data."""
    with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
        names = zf.namelist()
        layout_data = _read_layout(zf, names)
        has_data_model = "DataModel" in names
        images = [n for n in names if n.startswith("Report/StaticResources/")]

    # Extract measure DAX from DataModel via pbixray
    datamodel_measures = _extract_measures_from_datamodel(file_bytes)

    result = {
        "pages": [],
        "visuals_by_page": {},
        "tables_used": {},
        "measures_used": [],
        "measure_expressions": datamodel_measures,  # {(table, measure): DAX}
        "all_fields": [],
        "summary": {},
        "images": images,
        "has_data_model": has_data_model,
        "files_in_pbix": names,
    }

    if layout_data is None:
        return result

    pages = layout_data.get("sections", [])
    table_fields = defaultdict(lambda: {"columns": set(), "measures": set()})
    all_visuals = []

    for page in pages:
        page_name = page.get("displayName", "Sin nombre")
        page_visuals = []

        for vc in page.get("visualContainers", []):
            visual_info = _parse_visual_container(vc)
            visual_info["page"] = page_name
            page_visuals.append(visual_info)
            all_visuals.append(visual_info)

            # Collect table/field references
            for field in visual_info["fields"]:
                tbl = field["table"]
                col = field["field"]
                ftype = field["type"]
                if ftype == "measure":
                    table_fields[tbl]["measures"].add(col)
                else:
                    table_fields[tbl]["columns"].add(col)

        result["pages"].append({
            "name": page_name,
            "ordinal": page.get("ordinal", 0),
            "displayOption": page.get("displayOption", ""),
            "width": page.get("width", 0),
            "height": page.get("height", 0),
            "visual_count": len(page_visuals),
        })
        result["visuals_by_page"][page_name] = page_visuals

    # Convert sets to sorted lists
    tables_used = {}
    for tbl, info in sorted(table_fields.items()):
        tables_used[tbl] = {
            "columns": sorted(info["columns"]),
            "measures": sorted(info["measures"]),
        }
    result["tables_used"] = tables_used

    # Flatten all fields
    seen = set()
    for v in all_visuals:
        for f in v["fields"]:
            key = (f["table"], f["field"], f["type"])
            if key not in seen:
                seen.add(key)
                result["all_fields"].append(f)

    # Measures list
    result["measures_used"] = [
        {"table": tbl, "measure": m}
        for tbl, info in sorted(table_fields.items())
        for m in sorted(info["measures"])
    ]

    # Summary
    result["summary"] = {
        "pages": len(pages),
        "total_visuals": len(all_visuals),
        "tables": len(tables_used),
        "total_columns": sum(len(v["columns"]) for v in tables_used.values()),
        "total_measures": sum(len(v["measures"]) for v in tables_used.values()),
        "images": len(images),
        "visual_types": _count_visual_types(all_visuals),
    }

    return result


def _read_layout(zf: zipfile.ZipFile, names: list) -> dict | None:
    """Read and parse Report/Layout from the ZIP."""
    if "Report/Layout" not in names:
        return None

    raw = zf.read("Report/Layout")

    # Try different encodings
    for encoding in ["utf-16-le", "utf-8-sig", "utf-8", "latin-1"]:
        try:
            text = raw.decode(encoding)
            # Strip BOM if present
            if text and text[0] == '\ufeff':
                text = text[1:]
            return json.loads(text)
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue

    return None


def _parse_visual_container(vc: dict) -> dict:
    """Parse a single visual container to extract type, fields, and position."""
    config_str = vc.get("config", "{}")
    try:
        config = json.loads(config_str)
    except json.JSONDecodeError:
        config = {}

    sv = config.get("singleVisual", {})
    svg = config.get("singleVisualGroup", {})
    vis_type = sv.get("visualType", svg.get("visualType", "group"))

    # Position
    x = vc.get("x", 0)
    y = vc.get("y", 0)
    width = vc.get("width", 0)
    height = vc.get("height", 0)

    # Extract fields from prototypeQuery
    fields = _extract_fields_from_query(sv.get("prototypeQuery", {}))

    # Extract field names from projections for role mapping
    field_roles = _extract_field_roles(sv)

    # Title
    title = ""
    objects = sv.get("objects", {})
    title_obj = objects.get("title", [{}])
    if isinstance(title_obj, list) and title_obj:
        props = title_obj[0].get("properties", {})
        title_text = props.get("text", {})
        if isinstance(title_text, dict):
            title = title_text.get("expr", {}).get("Literal", {}).get("Value", "")
            if title.startswith("'") and title.endswith("'"):
                title = title[1:-1]

    return {
        "visual_type": vis_type,
        "title": title,
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "fields": fields,
        "field_roles": field_roles,
    }


def _extract_fields_from_query(query: dict) -> list[dict]:
    """Extract table.field references from a prototypeQuery Select."""
    fields = []
    selects = query.get("Select", [])

    # Build alias -> Entity map from the From clause
    alias_map = {}
    for frm in query.get("From", []):
        alias_map[frm.get("Name", "")] = frm.get("Entity", "")

    for sel in selects:
        for key in ["Column", "Measure", "Aggregation"]:
            if key not in sel:
                continue

            item = sel[key]
            field_type = "measure" if key == "Measure" else "column"

            # Direct SourceRef
            expr = item.get("Expression", {})
            entity = _get_entity(expr, alias_map)

            # For Aggregation, the column is nested deeper
            if key == "Aggregation" and not entity:
                inner = expr.get("Column", {})
                entity = _get_entity(inner.get("Expression", {}), alias_map)
                prop = inner.get("Property", sel.get("Name", ""))
                field_type = "aggregation"
            else:
                prop = item.get("Property", sel.get("Name", ""))

            if entity and prop:
                fields.append({
                    "table": entity,
                    "field": prop,
                    "type": field_type,
                    "alias": sel.get("Name", ""),
                })

    return fields


def _get_entity(expr: dict, alias_map: dict = None) -> str:
    """Get entity name from a SourceRef expression, resolving aliases."""
    source_ref = expr.get("SourceRef", {})
    # Try direct Entity first
    entity = source_ref.get("Entity", "")
    if entity:
        return entity
    # Resolve Source alias via From clause
    source = source_ref.get("Source", "")
    if source and alias_map:
        return alias_map.get(source, "")
    return ""


def _extract_field_roles(sv: dict) -> list[dict]:
    """Extract field role assignments (Category, Values, etc.)."""
    roles = []
    projections = sv.get("projections", {})
    for role_name, items in projections.items():
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict):
                    roles.append({
                        "role": role_name,
                        "queryRef": item.get("queryRef", ""),
                        "active": item.get("active", True),
                    })
    return roles


def _count_visual_types(visuals: list[dict]) -> dict:
    """Count occurrences of each visual type."""
    counts = defaultdict(int)
    for v in visuals:
        counts[v["visual_type"]] += 1
    return dict(sorted(counts.items(), key=lambda x: -x[1]))


# Friendly names for visual types
VISUAL_TYPE_NAMES = {
    "tableEx": "Table",
    "pivotTable": "Matrix / Pivot Table",
    "columnChart": "Column Chart",
    "barChart": "Bar Chart",
    "lineChart": "Line Chart",
    "areaChart": "Area Chart",
    "lineStackedColumnComboChart": "Combo Chart (Line + Column)",
    "lineClusteredColumnComboChart": "Combo Chart (Line + Clustered Column)",
    "clusteredBarChart": "Clustered Bar Chart",
    "clusteredColumnChart": "Clustered Column Chart",
    "stackedBarChart": "Stacked Bar Chart",
    "stackedColumnChart": "Stacked Column Chart",
    "hundredPercentStackedBarChart": "100% Stacked Bar Chart",
    "hundredPercentStackedColumnChart": "100% Stacked Column Chart",
    "waterfallChart": "Waterfall Chart",
    "funnelChart": "Funnel Chart",
    "scatterChart": "Scatter Chart",
    "pieChart": "Pie Chart",
    "donutChart": "Donut Chart",
    "treemap": "Treemap",
    "map": "Map",
    "filledMap": "Filled Map",
    "shapeMap": "Shape Map",
    "gauge": "Gauge",
    "card": "Card",
    "multiRowCard": "Multi-Row Card",
    "kpi": "KPI",
    "slicer": "Slicer",
    "textbox": "Text Box",
    "image": "Image",
    "shape": "Shape",
    "actionButton": "Button",
    "bookmarkNavigator": "Bookmark Navigator",
    "pageNavigator": "Page Navigator",
    "decompositionTreeVisual": "Decomposition Tree",
    "keyInfluencers": "Key Influencers",
    "qnaVisual": "Q&A Visual",
    "scriptVisual": "R/Python Script Visual",
    "ArcGISMap": "ArcGIS Map",
    "group": "Visual Group",
}


def get_visual_type_name(vtype: str) -> str:
    """Return a friendly name for a visual type."""
    return VISUAL_TYPE_NAMES.get(vtype, vtype)
