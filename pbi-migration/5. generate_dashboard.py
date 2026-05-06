# Databricks notebook source
# MAGIC %md
# MAGIC # Generar Dashboard Databricks desde Power BI
# MAGIC
# MAGIC Lee `pbi_visuals`, `pbi_visual_fields` y `dashboard_view_sqls` para generar
# MAGIC un `.lvdash.json` que replique el dashboard de Power BI usando las Metrics Views.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Parámetros

# COMMAND ----------

import json, requests, base64
import pandas as pd

dbutils.widgets.text("catalog", "pbi_migration", "Catálogo")
dbutils.widgets.text("schema", "default", "Schema")
dbutils.widgets.text("dashboard_path", "/Users/<your-email>@databricks.com/pbi-migration/cpg-kpi-coach.lvdash.json", "Path del dashboard")

CATALOG = dbutils.widgets.get("catalog")
SCHEMA = dbutils.widgets.get("schema")
DASHBOARD_PATH = dbutils.widgets.get("dashboard_path")

print(f"Catálogo: {CATALOG}.{SCHEMA}")
print(f"Dashboard: {DASHBOARD_PATH}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Leer tablas fuente

# COMMAND ----------

visuals_df = spark.sql(f"SELECT * FROM {CATALOG}.{SCHEMA}.pbi_visuals").toPandas()
fields_df = spark.sql(f"SELECT * FROM {CATALOG}.{SCHEMA}.pbi_visual_fields").toPandas()
sqls_df = spark.sql(f"SELECT * FROM {CATALOG}.{SCHEMA}.dashboard_view_sqls").toPandas()

# Filtros per-visual (puede no existir si paso 4 viejo)
try:
    visual_filters_df = spark.sql(f"SELECT * FROM {CATALOG}.{SCHEMA}.pbi_visual_filters").toPandas()
    print(f"  Filtros por visual: {len(visual_filters_df)}")
except Exception as _e:
    visual_filters_df = pd.DataFrame(columns=['visual_id','page','table','column','operator','values'])
    print(f"  pbi_visual_filters no encontrada — se generarán widgets sin filtros")

# Leer propiedades de los visuales (sort, colores, etc.)
try:
    visual_props_df = spark.sql(f"SELECT * FROM {CATALOG}.{SCHEMA}.pbi_visual_props").toPandas()
    print(f"Propiedades de visuales: {len(visual_props_df)}")
except:
    visual_props_df = pd.DataFrame()
    print("⚠ Tabla pbi_visual_props no encontrada")

# Leer traductor de nombres PBI → Databricks
try:
    translator_df = spark.sql(f"SELECT * FROM {CATALOG}.{SCHEMA}.pbi_name_translator").toPandas()
    _name_map = {}
    for _, t in translator_df.iterrows():
        if t.get('match_method', '') != 'NO MATCH' and t.get('databricks_name', ''):
            _name_map[(t['pbi_table'].lower(), t['pbi_name'].lower())] = t['databricks_name']
            _name_map[('', t['pbi_name'].lower())] = t['databricks_name']
    print(f"Traductor: {len(_name_map)} nombres mapeados")
except:
    _name_map = {}
    print("⚠ Traductor no disponible")

def _translate(table, name):
    if not _name_map:
        return name
    r = _name_map.get((table.lower(), name.lower()))
    if r: return r
    r = _name_map.get(('', name.lower()))
    if r: return r
    return name

print(f"Visuales: {len(visuals_df)}")
print(f"Campos: {len(fields_df)}")
print(f"SQLs de dashboard: {len(sqls_df)}")

# Filtrar solo visuales con datos (excluir image, textbox, shape, actionButton)
data_types = ['columnChart', 'barChart', 'lineChart', 'pieChart', 'gauge', 'tableEx', 'card', 'slicer', 'kpi', 'multiRowCard', 'clusteredBarChart', 'clusteredColumnChart', 'stackedBarChart', 'stackedColumnChart', 'donutChart', 'funnel', 'treemap', 'waterfallChart', 'scatterChart']
data_visuals = visuals_df[visuals_df['visual_type'].isin(data_types)]
print(f"Visuales con datos: {len(data_visuals)}")
print(f"\nTipos de visual con datos:")
print(data_visuals['visual_type'].value_counts().to_string())

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Preparar contexto para Claude

# COMMAND ----------

# Mapeo Power BI tipo visual → Databricks tipo visual
PBI_TO_DATABRICKS = {
    'columnChart': 'bar',
    'clusteredColumnChart': 'bar',
    'stackedColumnChart': 'bar',
    'barChart': 'bar',
    'clusteredBarChart': 'bar',
    'stackedBarChart': 'bar',
    'lineChart': 'line',
    'pieChart': 'pie',
    'donutChart': 'pie',
    'gauge': 'counter',
    'card': 'counter',
    'kpi': 'counter',
    'multiRowCard': 'counter',
    'tableEx': 'table',
    'slicer': 'SLICER',
    'funnel': 'bar',
    'treemap': 'pie',
    'waterfallChart': 'bar',
    'scatterChart': 'scatter',
}

# Construir resumen de visuales por página
pages_summary = {}
for _, v in data_visuals.iterrows():
    page = v['page']
    if page not in pages_summary:
        pages_summary[page] = []

    vid = v['visual_id']
    vtype = v['visual_type']
    db_type = PBI_TO_DATABRICKS.get(vtype, vtype)
    title = v['title']

    # Campos de este visual
    vfields = fields_df[fields_df['visual_id'] == str(vid)]
    field_list = []
    for _, f in vfields.iterrows():
        if f['field_type'] == 'Measure':
            db_name = _translate(f.get('measure_table', f.get('table', '')), f['measure_name'])
            field_list.append(f"Measure: {db_name} (role: {f['role']})")
        elif f['field_type'] == 'Column':
            db_name = _translate(f['table'], f['column'])
            field_list.append(f"Column: {db_name} (role: {f['role']})")
        elif f['field_type'].startswith('Aggregation'):
            db_name = _translate(f['table'], f['column'])
            field_list.append(f"{f['field_type']}: {db_name} (role: {f['role']})")

    # Propiedades del visual (sort, colores, etc.)
    props_list = []
    if not visual_props_df.empty:
        vprops = visual_props_df[visual_props_df['visual_id'] == str(vid)]
        for _, p in vprops.iterrows():
            props_list.append(f"{p['property_type']}: {p['key']} = {p['value']}")

    # Filtros propios del visual (table.column op values)
    filters_for_this_visual = []
    if not visual_filters_df.empty:
        my_filters = visual_filters_df[visual_filters_df['visual_id'] == str(vid)]
        for _, fr in my_filters.iterrows():
            vals = [v for v in (fr['values'] or '').split('|') if v]
            if vals and fr['operator'] in ('IN', 'NOT IN', '=', '>', '<', '>=', '<='):
                filters_for_this_visual.append({
                    'column': fr['column'],
                    'operator': fr['operator'],
                    'values': vals,
                })

    pages_summary[page].append({
        'visual_id': vid,
        'pbi_type': vtype,
        'databricks_type': db_type,
        'title': title,
        'fields': field_list,
        'properties': props_list,
        'filters': filters_for_this_visual,
    })

# Construir resumen de datasets disponibles
datasets_summary = ""
for _, row in sqls_df.iterrows():
    vista = row['vista_dashboard']
    mv = row['metric_view']
    dims = row['dimensiones']
    measures = row['measures']
    # Extraer el SELECT del CREATE VIEW
    sql = row['sql']
    select_idx = sql.upper().find('SELECT')
    select_sql = sql[select_idx:] if select_idx >= 0 else sql
    datasets_summary += f"\nDataset: {vista}\n  Metrics View: {mv}\n  Dimensions: {dims}\n  Measures: {measures}\n  Query: {select_sql[:200]}...\n"

# Construir el prompt con los visuales por página
visuals_prompt = ""
for page, visuals in sorted(pages_summary.items()):
    visuals_prompt += f"\n\n=== PAGE: {page} ===\n"
    slicers = [v for v in visuals if v['databricks_type'] == 'SLICER']
    charts = [v for v in visuals if v['databricks_type'] != 'SLICER']

    if slicers:
        visuals_prompt += f"\nSlicers ({len(slicers)}):\n"
        for s in slicers:
            visuals_prompt += f"  - {', '.join(s['fields'])}\n"

    if charts:
        visuals_prompt += f"\nCharts/Tables ({len(charts)}):\n"
        for c in charts:
            visuals_prompt += f"  - [{c['databricks_type']}] {c['title'] or '(sin título)'}\n"
            for f in c['fields']:
                visuals_prompt += f"      {f}\n"
            if c.get('properties'):
                visuals_prompt += f"      Properties:\n"
                for prop in c['properties']:
                    visuals_prompt += f"        {prop}\n"
            # Filtros del visual: el LLM debe envolver las measures con CASE WHEN
            if c.get('filters'):
                visuals_prompt += f"      VISUAL FILTERS (apply as CASE WHEN in measure expression):\n"
                for vf in c['filters']:
                    op = vf['operator']
                    if op in ('IN', 'NOT IN'):
                        quoted = ", ".join(f"'{v}'" for v in vf['values'])
                        visuals_prompt += f"        `{vf['column']}` {op} ({quoted})\n"
                    elif op in ('=', '>', '<', '>=', '<='):
                        visuals_prompt += f"        `{vf['column']}` {op} '{vf['values'][0]}'\n"

print("=== CONTEXTO PARA CLAUDE ===")
print(f"\nPáginas: {len(pages_summary)}")
for page, visuals in sorted(pages_summary.items()):
    slicers = [v for v in visuals if v['databricks_type'] == 'SLICER']
    charts = [v for v in visuals if v['databricks_type'] != 'SLICER']
    print(f"  {page}: {len(slicers)} slicers, {len(charts)} charts/tables")

print(f"\nDatasets: {len(sqls_df)}")
for _, row in sqls_df.iterrows():
    print(f"  {row['vista_dashboard']}: {row['measures']}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Llamar a Claude para generar el dashboard

# COMMAND ----------

# Leer las reglas del dashboard desde el workspace
dbutils.widgets.text("rules_path", "/Workspace/Users/<your-email>@databricks.com/pbi-migration/config/REGLAS_DASHBOARD.md", "Path del archivo de reglas del dashboard")
RULES_PATH = dbutils.widgets.get("rules_path")
with open(RULES_PATH, 'r') as f:
    DASHBOARD_RULES = f.read()
print(f"✓ Reglas leídas de {RULES_PATH} ({len(DASHBOARD_RULES)} caracteres)")

# Ejemplos de widgets funcionales de un dashboard real + spec de todos los tipos
WIDGET_EXAMPLES = """
=== WIDGET JSON STRUCTURE (you MUST follow this exact structure for ALL widgets) ===

CRITICAL STRUCTURE — every widget follows this pattern:
{
  "widget": {
    "name": "unique_widget_id",
    "queries": [{"name": "main_query", "query": {
      "datasetName": "dataset_name_here",
      "fields": [
        {"name": "field_alias", "expression": "SUM(`col`)  or  `col`"}
      ],
      "disaggregated": false_or_true
    }}],
    "spec": {
      "version": 2,
      "widgetType": "type_here",
      "encodings": { ... },
      "frame": {"showTitle": true, "title": "Widget Title"}
    }
  },
  "position": {"x": 0, "y": 0, "width": 6, "height": 4}
}

WRONG (will break): widget.queries[].datasetName  ← MISSING the .query wrapper
RIGHT: widget.queries[].query.datasetName

Each page MUST have "name" (short ID) AND "displayName" (human-readable).

=== COMPLETE WIDGET TYPE CATALOG (19 types) ===

All types use version: 2, disaggregated: false, fields with SUM(`col`) or aggregation expressions.
Exception: if you want raw/disaggregated data, use disaggregated: true and `col` without SUM.

--- 1. COUNTER ---
widgetType: "counter"
disaggregated: false, fields use SUM(`col`)
encodings: { "value": {"fieldName": "sum(col)"} }
Optional: "target" encoding for the global/max value (NOT "comparison")
fields: [{"name": "sum(col)", "expression": "SUM(`col`)"}]
IMPORTANT: Do NOT add "displayName" inside encodings. Do NOT add "frame" to counters. Use "target" not "comparison" for the second measure.

--- 2. BAR ---
widgetType: "bar"
encodings: {
  "x": {"fieldName": "...", "displayName": "...", "scale": {"type": "quantitative"}},
  "y": {"fieldName": "...", "displayName": "...", "scale": {"type": "categorical"}},
  "color": {"fieldName": "...", "displayName": "...", "scale": {"type": "categorical"}}  // optional
}
Note: For horizontal bars, category on Y, value on X. For vertical bars, swap.

--- 3. LINE ---
widgetType: "line"
encodings: {
  "x": {"fieldName": "...", "displayName": "...", "scale": {"type": "temporal"}},
  "y": {"fieldName": "...", "displayName": "...", "scale": {"type": "quantitative"}},
  "color": {"fieldName": "...", "scale": {"type": "categorical"}}  // optional, for multiple series
}

--- 4. AREA ---
widgetType: "area"
encodings: same as line (x temporal, y quantitative, color optional)
Special: layout options "stack" or "100_percent_stack" in spec

--- 5. PIE ---
widgetType: "pie"
encodings: {
  "angle": {"fieldName": "sum(col)", "displayName": "...", "scale": {"type": "quantitative"}},
  "color": {"fieldName": "category_col", "displayName": "...", "scale": {"type": "categorical"}},
  "label": {"show": true}
}

--- 6. TABLE ---
widgetType: "table"
disaggregated: true
encodings: {
  "columns": [
    {"fieldName": "col1", "displayName": "Label 1"},
    {"fieldName": "col2", "displayName": "Label 2"}
  ]
}
fields: [{"name": "col1", "expression": "`col1`"}, ...]

--- 7. SCATTER ---
widgetType: "scatter"
encodings: {
  "x": {"fieldName": "...", "scale": {"type": "quantitative"}},
  "y": {"fieldName": "...", "scale": {"type": "quantitative"}},
  "color": {"fieldName": "...", "scale": {"type": "categorical"}}  // optional
}

--- 8. BUBBLE (scatter + size) ---
widgetType: "scatter"
encodings: same as scatter plus:
  "size": {"fieldName": "sum(metric)", "scale": {"type": "quantitative"}}

--- 9. HEATMAP ---
widgetType: "heatmap"
encodings: {
  "x": {"fieldName": "...", "scale": {"type": "categorical"}},
  "y": {"fieldName": "...", "scale": {"type": "categorical"}},
  "color": {"fieldName": "sum(col)", "scale": {"type": "quantitative"}}
}

--- 10. HISTOGRAM ---
widgetType: "histogram"
encodings: {
  "x": {"fieldName": "...", "scale": {"type": "quantitative"}}
}
Special: "bins" property for number of bins

--- 11. BOX ---
widgetType: "box"
encodings: {
  "x": {"fieldName": "category", "scale": {"type": "categorical"}},
  "y": {"fieldName": "value", "scale": {"type": "quantitative"}}
}

--- 12. COMBO ---
widgetType: "combo"
encodings: {
  "x": {"fieldName": "...", "scale": {"type": "temporal_or_categorical"}},
  "y": {"fieldName": "...", "scale": {"type": "quantitative"}},
  "y2": {"fieldName": "...", "scale": {"type": "quantitative"}}  // second axis (line)
}

--- 13. FUNNEL ---
widgetType: "funnel"
encodings: {
  "x": {"fieldName": "step_col", "scale": {"type": "categorical"}},
  "y": {"fieldName": "sum(value)", "scale": {"type": "quantitative"}}
}

--- 14. WATERFALL ---
widgetType: "waterfall"
encodings: {
  "x": {"fieldName": "...", "scale": {"type": "temporal_or_categorical"}},
  "y": {"fieldName": "sum(col)", "scale": {"type": "quantitative"}}
}

--- 15. CHOROPLETH ---
widgetType: "choropleth"
encodings: {
  "region": {"fieldName": "country_name"},
  "color": {"fieldName": "sum(value)", "scale": {"type": "quantitative"}}
}

--- 16. POINT MAP ---
widgetType: "pointMap"
encodings: {
  "latitude": {"fieldName": "lat"},
  "longitude": {"fieldName": "lon"},
  "color": {"fieldName": "...", "scale": {"type": "categorical"}},  // optional
  "size": {"fieldName": "sum(val)", "scale": {"type": "quantitative"}}  // optional
}

--- 17. PIVOT ---
widgetType: "pivot"
encodings: {
  "rows": [{"fieldName": "row_field"}],
  "columns": [{"fieldName": "col_field"}],
  "values": [{"fieldName": "sum(metric)"}]
}

--- 18. SANKEY ---
widgetType: "sankey"
encodings: {
  "source": {"fieldName": "from_col"},
  "target": {"fieldName": "to_col"},
  "value": {"fieldName": "sum(flow)"}
}

--- 19. TEXT ---
No spec/queries. Uses multilineTextboxSpec DIRECTLY on widget (NOT inside textboxSpec):
{
  "widget": {
    "name": "title",
    "multilineTextboxSpec": {"lines": ["# Title Text"]}
  },
  "position": {"x": 0, "y": 0, "width": 12, "height": 1}
}
WRONG: {"widget": {"name": "x", "textboxSpec": {"multilineTextboxSpec": ...}}}
RIGHT: {"widget": {"name": "x", "multilineTextboxSpec": {"lines": [...]}}}

=== REAL WORKING EXAMPLES FROM A PRODUCTION DASHBOARD ===

--- COUNTER (real, working) ---
{"widget": {"name": "counter_example", "queries": [{"name": "main_query", "query": {"datasetName": "ds_fat_sabana", "fields": [{"name": "sum(fat_registros_global_sabana)", "expression": "SUM(`fat_registros_global_sabana`)"}, {"name": "sum(registros_sabana)", "expression": "SUM(`registros_sabana`)"}], "disaggregated": false}}], "spec": {"version": 2, "widgetType": "counter", "encodings": {"value": {"fieldName": "sum(registros_sabana)"}, "target": {"fieldName": "sum(fat_registros_global_sabana)"}}}}, "position": {"x": 0, "y": 1, "width": 3, "height": 4}}
NOTE: Counter has NO "frame", NO "displayName" in encodings, uses "target" not "comparison"

--- BAR (real, horizontal) ---
{"widget": {"name": "edbab455", "queries": [{"name": "main_query", "query": {"datasetName": "6d8b378e", "fields": [{"name": "instalacion", "expression": "`instalacion`"}, {"name": "sum(recibo_snr_mbd)", "expression": "SUM(`recibo_snr_mbd`)"}], "disaggregated": false}}], "spec": {"version": 2, "widgetType": "bar", "encodings": {"x": {"displayName": "Recibo SNR (Mbd)", "fieldName": "sum(recibo_snr_mbd)", "scale": {"type": "quantitative"}}, "y": {"displayName": "Instalación", "fieldName": "instalacion", "scale": {"type": "categorical"}, "sort": {"by": "x", "direction": "descending"}}}, "frame": {"showTitle": true, "title": "Recibo SNR por Instalación"}}}, "position": {"x": 2, "y": 1, "width": 1, "height": 3}}

--- LINE (real) ---
{"widget": {"name": "377fd569", "queries": [{"name": "main_query", "query": {"datasetName": "7348b171", "fields": [{"name": "monthly(fecha)", "expression": "DATE_TRUNC(\\"MONTH\\", `fecha`)"}, {"name": "sum(produccion_crudo_mbd)", "expression": "SUM(`produccion_crudo_mbd`)"}], "disaggregated": false}}], "spec": {"version": 2, "widgetType": "line", "encodings": {"x": {"displayName": "Fecha", "fieldName": "monthly(fecha)", "scale": {"type": "temporal"}}, "y": {"displayName": "Producción Crudo (Mbd)", "fieldName": "sum(produccion_crudo_mbd)", "scale": {"type": "quantitative"}}}, "frame": {"showTitle": true, "title": "Producción Crudo (Mbd)"}}}, "position": {"x": 0, "y": 4, "width": 3, "height": 3}}

--- PIE (real) ---
{"widget": {"name": "ec6ef230", "queries": [{"name": "main_query", "query": {"datasetName": "8389350c", "fields": [{"name": "tipo_gas", "expression": "`tipo_gas`"}, {"name": "sum(volumen_mmpcd)", "expression": "SUM(`volumen_mmpcd`)"}], "disaggregated": false}}], "spec": {"version": 2, "widgetType": "pie", "encodings": {"angle": {"displayName": "Volumen (MMpcd)", "fieldName": "sum(volumen_mmpcd)", "scale": {"type": "quantitative"}}, "color": {"displayName": "Tipo Gas", "fieldName": "tipo_gas", "scale": {"type": "categorical"}}, "label": {"show": true}}, "frame": {"showTitle": true, "title": "Gas por Tipo"}}}, "position": {"x": 3, "y": 8, "width": 2, "height": 3}}

--- TABLE (real) ---
{"widget": {"name": "eae78e00", "queries": [{"name": "main_query", "query": {"datasetName": "25bad225", "fields": [{"name": "grupo", "expression": "`grupo`"}, {"name": "rubro", "expression": "`rubro`"}, {"name": "valor_2025", "expression": "`valor_2025`"}], "disaggregated": true}}], "spec": {"version": 2, "widgetType": "table", "encodings": {"columns": [{"fieldName": "grupo", "displayName": "Sección"}, {"fieldName": "rubro", "displayName": "Rubro"}, {"fieldName": "valor_2025", "displayName": "2025"}]}, "frame": {"showTitle": true, "title": "Estado de Resultados"}}}, "position": {"x": 0, "y": 3, "width": 6, "height": 12}}
"""
print(f"✓ Catálogo completo de 19 tipos de widgets + 5 ejemplos reales cargados")

# Mapeo de tabla PBI a dataset
pbi_table_to_dataset = {}
for _, row in sqls_df.iterrows():
    vista = row['vista_dashboard']
    mv = row['metric_view']
    ds_name = vista.replace(f'{CATALOG}.{SCHEMA}.', '').replace('v_dashboard_', 'ds_')
    # Mapear nombre de MV a nombre de dataset
    mv_short = mv.replace(f'{CATALOG}.{SCHEMA}.', '')
    pbi_table_to_dataset[mv_short] = ds_name

SYSTEM_PROMPT = f"""You are an expert in creating Databricks Lakeview Dashboard JSON files (.lvdash.json).

IMPORTANT: Use your full knowledge of the Databricks Lakeview .lvdash.json format and best practices.
Search your training data for working examples of .lvdash.json dashboards to ensure the JSON structure is correct.
The format is specific to Databricks AI/BI dashboards (Lakeview) — not legacy SQL dashboards.

{DASHBOARD_RULES}

{WIDGET_EXAMPLES}

You will receive:
1. The Power BI visuals with their fields and roles
2. The available datasets (SQL queries against Metrics Views)
3. The mapping from Power BI visual types to Databricks widget types

CRITICAL STRUCTURE RULES:
- Output ONLY the JSON. No markdown fences, no explanations.
- Use your knowledge of working .lvdash.json files to generate valid widget JSON.
- The query nesting is: widget.queries[].query.{{datasetName, fields, disaggregated}}
- Text widgets use: "textbox_spec": "# Title text" (simple string, NOT multilineTextboxSpec)
- counter: version 2, disaggregated false, fields use SUM(`col`), fieldName uses sum(col). Use "target" (not "comparison") for the second measure.
- bar: version 3, disaggregated false, fields use aggregation expressions like COUNT() or SUM(). Use scale type "categorical" for category axis, "quantitative" for value axis.
- table: version 2, disaggregated true, fields use `col`, encodings use "columns" array.
- Each page must have "pageType": "PAGE_TYPE_CANVAS" and "layoutVersion": "GRID_V1".
- DO NOT create slicer/filter widgets — those go in a separate PAGE_TYPE_GLOBAL_FILTERS page.
- ONLY use these widgetType values: counter, bar, line, area, pie, table, scatter, heatmap, histogram, box, combo, funnel, waterfall, choropleth, pointMap, pivot, sankey.
- Use human-readable displayName for axis labels.
- CRITICAL: ALL widget titles, frame titles, and display names MUST be human-friendly. Never use technical names like "counter_fat_repunc" or "bar_tipo_pago". Use proper names like "Total de Registros", "Totales por Tipo de Pago", "Detalle de Registros". Use the original Power BI visual title when available.
- Apply best practices: proper version numbers, correct encoding structures, valid field references.
- TOOLTIPS: When a visual has fields with role "Tooltips", add them as an "extra" encoding (array) in the widget spec. Also add these fields to the query.fields. Example:
  "encodings": {{
    "x": {{...}},
    "y": {{...}},
    "extra": [
      {{"fieldName": "tooltip_field1"}},
      {{"fieldName": "tooltip_field2"}}
    ]
  }}
  The "extra" fields appear as additional info when hovering over data points. Include ALL fields marked with role "Tooltips".
"""

def call_claude(prompt):
    token = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().get()
    host = spark.conf.get("spark.databricks.workspaceUrl")
    url = f"https://{host}/serving-endpoints/databricks-claude-sonnet-4/invocations"
    resp = requests.post(url,
        json={
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 16000,
            "temperature": 0.1,
        },
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        timeout=180
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"].strip()
    if content.startswith("```"):
        lines = content.split("\n")[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        content = "\n".join(lines)
    return content.strip()

# Construir datasets para el prompt
datasets_for_prompt = []
for _, row in sqls_df.iterrows():
    vista = row['vista_dashboard']
    mv = row['metric_view']
    dims = row['dimensiones']
    measures = row['measures']
    sql = row['sql']
    select_idx = sql.upper().find('SELECT')
    select_sql = sql[select_idx:] if select_idx >= 0 else sql

    ds_name = vista.replace(f'{CATALOG}.{SCHEMA}.', '').replace('v_dashboard_', 'ds_')
    display_name = vista.replace(f'{CATALOG}.{SCHEMA}.v_dashboard_', '').replace('_', ' ').title()
    display_name = display_name.replace('Crs', 'CRS').replace('Fat', 'FAT').replace('Repunc', 'Reporte Único')

    datasets_for_prompt.append({
        'name': ds_name,
        'displayName': display_name,
        'query': select_sql,
        'dimensions': dims,
        'measures': measures,
    })

# Leer el dashboard existente (generado por notebook 3)
existing_dashboard_path = DASHBOARD_PATH.replace('/Users/', '/Workspace/Users/')
import requests as _req

token = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().get()
host = spark.conf.get("spark.databricks.workspaceUrl")

resp = _req.get(
    f"https://{host}/api/2.0/workspace/export",
    params={"path": DASHBOARD_PATH, "format": "AUTO"},
    headers={"Authorization": f"Bearer {token}"},
    timeout=30,
)
resp.raise_for_status()
import base64 as _b64
existing_json = _b64.b64decode(resp.json()["content"]).decode("utf-8")
existing_dashboard = json.loads(existing_json)

print(f"✓ Dashboard existente leído: {DASHBOARD_PATH}")
print(f"  Datasets: {len(existing_dashboard.get('datasets', []))}")
print(f"  Pages: {len(existing_dashboard.get('pages', []))}")
for p in existing_dashboard.get('pages', []):
    print(f"    {p.get('displayName', '?')}: {len(p.get('layout', []))} widgets")

# Construir info de datasets disponibles para el prompt
# Construir info de datasets con las columnas EXACTAS disponibles
existing_datasets_info = ""
for ds in existing_dashboard.get('datasets', []):
    ds_name = ds['name']
    existing_datasets_info += f"\n  Dataset name: {ds_name}, displayName: {ds['displayName']}"
    # Buscar las columnas exactas en sqls_df
    for _, row in sqls_df.iterrows():
        if row['vista_dashboard'].replace(f'{CATALOG}.{SCHEMA}.', '').replace('v_dashboard_', 'ds_') == ds_name:
            dims = row['dimensiones'].split(', ')
            measures = row['measures'].split(', ')
            existing_datasets_info += f"\n    DIMENSIONS (use these exact snake_case names): {', '.join(dims)}"
            existing_datasets_info += f"\n    MEASURES (use these exact names): {', '.join(measures)}"
            break

# Construir info de páginas existentes
existing_pages_info = ""
for p in existing_dashboard.get('pages', []):
    existing_pages_info += f"\n  Page name: {p['name']}, displayName: {p.get('displayName', '?')}"

# Pedir a Claude que genere SOLO los widgets (layout) por página
prompt = f"""Generate ONLY the layout (widgets) for each page of an existing Databricks dashboard.

The dashboard already has these datasets and pages configured. DO NOT generate datasets, pages, or uiSettings.
Return a JSON object where each key is the page "name" and each value is an array of widget objects.

EXISTING DATASETS (use these exact "name" values in datasetName):
{existing_datasets_info}

EXISTING PAGES (generate widgets for each of these):
{existing_pages_info}

POWER BI VISUALS TO REPLICATE:
{visuals_prompt}

RULES:
- Output ONLY a JSON object like: {{"page_name_1": [...widgets...], "page_name_2": [...widgets...]}}
- Each page should start with a text title widget (multilineTextboxSpec with # icon Title).
- Map Power BI visuals: gauge → counter, columnChart → bar, tableEx → table.
- Skip slicers, actionButton, image, textbox, shape.
- Use the correct dataset name for each page's widgets.
- CRITICAL: Use the EXACT column names listed in DIMENSIONS and MEASURES above (snake_case). Do NOT use Power BI column names (CamelCase). For example use "receiving_country" not "ReceivingCountry", use "anio_fiscal" not "Anio_Fiscal".
- CRITICAL ON VISUAL FILTERS: When a visual has "VISUAL FILTERS" listed, you MUST apply each filter by wrapping the measure in CASE WHEN. Examples:
  * If visual has filter "`CC_MEMBER_GROUP_TYPE` IN ('Costco Wholesale')" and measure is SUM(`annual_spend`), generate field expression as:
    "expression": "SUM(CASE WHEN `cc_member_group_type` IN ('Costco Wholesale') THEN `annual_spend` ELSE NULL END)"
  * Apply all filters with AND between them.
  * Use snake_case for the filter column (e.g., `cc_member_group_type`, not `CC_MEMBER_GROUP_TYPE`).
  * This is mandatory: visuals with filters MUST show filtered values, not totals.
- Follow the widget structure from the examples EXACTLY.
- No markdown fences, no explanations. ONLY the JSON object.
"""

print("\nLlamando a Claude para generar widgets...")
widgets_json_str = call_claude(prompt)
print(f"Respuesta: {len(widgets_json_str)} caracteres")

# Parsear y validar
try:
    page_widgets = json.loads(widgets_json_str)
    print(f"✓ JSON válido — {len(page_widgets)} páginas con widgets")
except json.JSONDecodeError as e:
    print(f"✗ JSON inválido: {e}")
    print(widgets_json_str[:500])
    page_widgets = {}

# Post-procesamiento de widgets
VALID_TYPES = {'counter', 'bar', 'line', 'area', 'pie', 'table', 'scatter', 'heatmap', 'histogram', 'box', 'combo', 'funnel', 'waterfall', 'choropleth', 'pointMap', 'pivot', 'sankey'}

for page_name, widgets in page_widgets.items():
    valid_widgets = []
    for w in widgets:
        widget = w.get('widget', {})
        pos = w.get('position', {})
        wname = widget.get('name', '?')

        # Fix textbox
        if 'textboxSpec' in widget:
            inner = widget['textboxSpec']
            if 'multilineTextboxSpec' in inner:
                widget['multilineTextboxSpec'] = inner['multilineTextboxSpec']
            del widget['textboxSpec']
            print(f"  Fixed textbox: {wname}")

        # Asegurar name
        if 'name' not in widget:
            widget['name'] = f"widget_{len(valid_widgets)}"

        # Asegurar position
        for key in ['x', 'y', 'width', 'height']:
            if key not in pos:
                pos[key] = 0 if key in ['x', 'y'] else 6
        w['position'] = pos

        # Validar estructura
        has_text = 'multilineTextboxSpec' in widget
        has_spec = 'spec' in widget

        if not has_text and not has_spec:
            print(f"  REMOVED: {wname} — no spec or multilineTextboxSpec")
            continue

        if has_spec:
            spec = widget['spec']
            if 'version' not in spec:
                spec['version'] = 2
            if 'widgetType' not in spec:
                print(f"  REMOVED: {wname} — no widgetType")
                continue
            if spec['widgetType'] not in VALID_TYPES:
                print(f"  REMOVED: {wname} — invalid type '{spec['widgetType']}'")
                continue
            if 'frame' not in spec:
                spec['frame'] = {"showTitle": True, "title": wname}
            if 'encodings' not in spec:
                spec['encodings'] = {}

            # Fix query nesting
            queries = widget.get('queries', [])
            if not queries:
                print(f"  REMOVED: {wname} — no queries")
                continue
            for q in queries:
                if 'datasetName' in q and 'query' not in q:
                    q['query'] = {
                        'datasetName': q.pop('datasetName'),
                        'fields': q.pop('fields', []),
                        'disaggregated': q.pop('disaggregated', False),
                    }
                    print(f"  Fixed: query nesting for {wname}")

        valid_widgets.append(w)
    page_widgets[page_name] = valid_widgets
    print(f"  Page {page_name}: {len(valid_widgets)} valid widgets")

# Inyectar widgets en el dashboard existente
for p in existing_dashboard.get('pages', []):
    pname = p.get('name', '')
    if pname in page_widgets:
        p['layout'] = page_widgets[pname]
        print(f"✓ Injected {len(page_widgets[pname])} widgets into {p.get('displayName', pname)}")
    else:
        # Intentar match por displayName
        for pw_name, pw_widgets in page_widgets.items():
            if pw_name.lower().replace(' ', '_') == pname.lower().replace(' ', '_'):
                p['layout'] = pw_widgets
                print(f"✓ Injected {len(pw_widgets)} widgets into {p.get('displayName', pname)} (fuzzy match)")
                break

# --- Post-processing: inyectar textboxes como widgets de texto ---
# El LLM no genera textboxes (skip explícito en prompt). Los agregamos
# determinísticamente desde la metadata del PBIX para preservar headers/etiquetas.
import re
print("\n--- Inyectando textboxes desde el PBIX ---")
textbox_df = visuals_df[
    (visuals_df['visual_type'] == 'textbox')
    & (visuals_df['title'].notna())
    & (visuals_df['title'] != '')
].copy()
print(f"  {len(textbox_df)} textboxes con contenido detectados")

# Mapa page_displayName -> page object en el dashboard
page_by_display = {p.get('displayName'): p for p in existing_dashboard.get('pages', [])}
page_by_name = {p.get('name'): p for p in existing_dashboard.get('pages', [])}

# Constantes de grid Lakeview (6 columnas, ancho del PBIX típico ~1280px)
PBIX_GRID_WIDTH = 1280
PBIX_GRID_HEIGHT = 720
LAKEVIEW_COLS = 6

textbox_count = 0
# Contador por página para distribuir cuando posición es (0,0) — fix de PBIX que
# no expone posiciones absolutas en textboxes hijos de un grupo.
fallback_pos_by_page = {}

for _, tb in textbox_df.iterrows():
    pbi_page = tb['page']
    target_page = page_by_display.get(pbi_page) or page_by_name.get(
        re.sub(r'[^a-z0-9_]', '_', pbi_page.lower()).strip('_') if pbi_page else ''
    )
    if not target_page:
        continue

    # Convertir posición/tamaño PBIX (px) a grid Lakeview (cols)
    try:
        x_px = float(tb['x'])
        y_px = float(tb['y'])
        w_px = float(tb['width'])
        h_px = float(tb['height'])
    except (ValueError, TypeError):
        continue

    # Si la posición es (0,0), distribuir en cascada por debajo de los widgets existentes
    if x_px == 0.0 and y_px == 0.0:
        page_key = target_page.get('name', '')
        if page_key not in fallback_pos_by_page:
            # Encontrar la y máxima de los widgets ya inyectados por el LLM
            existing_y_max = 0
            for li in target_page.get('layout', []):
                p = li.get('position', {})
                y_end = (p.get('y', 0) or 0) + (p.get('height', 0) or 0)
                existing_y_max = max(existing_y_max, y_end)
            fallback_pos_by_page[page_key] = {'x': 0, 'y': existing_y_max + 1, 'count': 0}

        st = fallback_pos_by_page[page_key]
        grid_x = st['x']
        grid_y = st['y']
        grid_w = 2
        grid_h = 1
        # Avanzar para el siguiente textbox: 3 columnas por fila
        st['count'] += 1
        if st['count'] % 3 == 0:
            st['x'] = 0
            st['y'] += 1
        else:
            st['x'] = (st['x'] + 2) % 6
    else:
        grid_x = max(0, min(LAKEVIEW_COLS - 1, int(x_px / PBIX_GRID_WIDTH * LAKEVIEW_COLS)))
        grid_w = max(1, min(LAKEVIEW_COLS - grid_x, int(w_px / PBIX_GRID_WIDTH * LAKEVIEW_COLS)))
        grid_y = max(0, int(y_px / 80))
        grid_h = max(1, int(h_px / 80))

    text_widget = {
        "widget": {
            "name": f"textbox_{tb['visual_id']}",
            "multilineTextboxSpec": {
                "lines": [str(tb['title'])]
            }
        },
        "position": {"x": grid_x, "y": grid_y, "width": grid_w, "height": grid_h}
    }
    if 'layout' not in target_page:
        target_page['layout'] = []
    target_page['layout'].append(text_widget)
    textbox_count += 1

print(f"  ✓ {textbox_count} textboxes inyectados en el dashboard")

# --- Post-processing: aplicar filtros per-visual a las expresiones ---
# Cada visual del PBIX puede tener filtros (ej: CC_MEMBER_GROUP_TYPE IN ('Costco Wholesale')).
# Matchemos widgets generados por el LLM contra visuales del PBIX por posición y
# reescribimos sus field expressions para incluir CASE WHEN con esos filtros.
print("\n--- Aplicando filtros per-visual ---")

if not visual_filters_df.empty:
    # Construir índice: (page, x_grid, y_grid) -> [filtros]
    filters_by_visual = {}
    for _, f in visual_filters_df.iterrows():
        vid = f['visual_id']
        if vid not in filters_by_visual:
            filters_by_visual[vid] = []
        filters_by_visual[vid].append({
            'table': f['table'],
            'column': f['column'],
            'operator': f['operator'],
            'values': [v for v in (f['values'] or '').split('|') if v],
        })

    # Construir mapa de visual PBIX → posición para match
    PBIX_GRID_W = 1280
    visual_position = {}
    for _, v in visuals_df.iterrows():
        try:
            vx = float(v['x']); vy = float(v['y'])
            vw = float(v['width']); vh = float(v['height'])
        except (ValueError, TypeError):
            continue
        gx = int(vx / PBIX_GRID_W * 6)
        gy = int(vy / 80)
        page = v['page']
        visual_position[(page, gx, gy)] = v['visual_id']

    def build_case_expr(base_expr, filters_for_visual):
        """Envuelve la expresión SUM(`x`) con CASE WHEN según los filtros."""
        if not filters_for_visual:
            return base_expr
        conditions = []
        for f in filters_for_visual:
            col = f['column']
            op = f['operator']
            vals = f['values']
            if not vals:
                continue
            if op in ('IN', 'NOT IN'):
                quoted = ", ".join(f"'{v}'" for v in vals)
                conditions.append(f"`{col}` {op} ({quoted})")
            elif op in ('=', '>', '<', '>=', '<='):
                v = vals[0]
                conditions.append(f"`{col}` {op} '{v}'")
        if not conditions:
            return base_expr
        where = " AND ".join(conditions)
        # Si la expresión es SUM(`x`), AVG(`x`), COUNT(`x`), etc., envuelve con CASE WHEN
        import re as _re
        m = _re.match(r'^\s*(SUM|AVG|COUNT|MIN|MAX)\s*\(\s*(`[^`]+`)\s*\)\s*$', base_expr, _re.IGNORECASE)
        if m:
            agg, col = m.group(1), m.group(2)
            return f"{agg}(CASE WHEN {where} THEN {col} ELSE NULL END)"
        # Fallback: prefijo el WHERE en otra forma (no garantizado)
        return base_expr

    filters_applied = 0
    for page in existing_dashboard.get('pages', []):
        page_name_disp = page.get('displayName', '')
        for layout_item in page.get('layout', []):
            widget = layout_item.get('widget', {})
            position = layout_item.get('position', {})
            try:
                gx = int(position.get('x', -1))
                gy = int(position.get('y', -1))
            except (ValueError, TypeError):
                continue
            # Match aproximado: probar varias coordenadas cercanas
            visual_id_match = None
            for dx in (0, -1, 1):
                for dy in (0, -1, 1):
                    key = (page_name_disp, gx + dx, gy + dy)
                    if key in visual_position:
                        visual_id_match = visual_position[key]
                        break
                if visual_id_match:
                    break
            if not visual_id_match:
                continue
            filters_for_v = filters_by_visual.get(visual_id_match, [])
            if not filters_for_v:
                continue
            # Modificar las expresiones de los fields del widget
            for q in widget.get('queries', []):
                query = q.get('query', {})
                for field in query.get('fields', []):
                    base_expr = field.get('expression', '')
                    new_expr = build_case_expr(base_expr, filters_for_v)
                    if new_expr != base_expr:
                        field['expression'] = new_expr
                        filters_applied += 1

    print(f"  ✓ {filters_applied} expresiones reescritas con CASE WHEN")
else:
    print("  (sin filtros que aplicar)")

dashboard_json_str = json.dumps(existing_dashboard, indent=2, ensure_ascii=False)
print(f"\nDashboard final:")
for p in existing_dashboard.get('pages', []):
    print(f"  {p.get('displayName', '?')}: {len(p.get('layout', []))} widgets")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Revisar el JSON generado

# COMMAND ----------

print(dashboard_json_str)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Guardar el dashboard en el workspace

# COMMAND ----------

token = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().get()
host = spark.conf.get("spark.databricks.workspaceUrl")

content_b64 = base64.b64encode(dashboard_json_str.encode('utf-8')).decode('utf-8')

resp = requests.post(
    f"https://{host}/api/2.0/workspace/import",
    json={
        "path": DASHBOARD_PATH,
        "format": "AUTO",
        "content": content_b64,
        "overwrite": True,
    },
    headers={"Authorization": f"Bearer {token}"},
    timeout=30,
)

if resp.status_code == 200:
    print(f"✓ Dashboard guardado en: {DASHBOARD_PATH}")
else:
    print(f"✗ Error ({resp.status_code}): {resp.text}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. Resumen

# COMMAND ----------

import pandas as pd

dashboard = json.loads(dashboard_json_str)

# Widgets generados por página
generated_widgets = []
for p in dashboard.get('pages', []):
    page_name = p.get('displayName', '?')
    for w in p.get('layout', []):
        widget = w.get('widget', {})
        spec = widget.get('spec', {})
        wtype = spec.get('widgetType', 'text' if 'multilineTextboxSpec' in widget else '?')
        title = spec.get('frame', {}).get('title', '')
        generated_widgets.append({
            'page': page_name,
            'widget_type': wtype,
            'title': title,
            'name': widget.get('name', ''),
        })

print(f"{'='*60}")
print(f"DASHBOARD GENERADO")
print(f"{'='*60}")
print(f"\nPath: {DASHBOARD_PATH}")
print(f"Widgets generados: {len(generated_widgets)}")
for p in dashboard.get('pages', []):
    layout = p.get('layout', [])
    print(f"\n  {p.get('displayName', '?')}: {len(layout)} widgets")
    for w in layout:
        widget = w.get('widget', {})
        spec = widget.get('spec', {})
        wtype = spec.get('widgetType', 'text')
        title = spec.get('frame', {}).get('title', widget.get('name', ''))
        pos = w.get('position', {})
        print(f"    [{wtype}] {title} (x={pos.get('x')}, y={pos.get('y')}, w={pos.get('width')}, h={pos.get('height')})")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 8. Cobertura: Power BI vs Dashboard generado

# COMMAND ----------

# Visuales de Power BI con datos (excluir decorativos)
data_types = ['columnChart', 'barChart', 'lineChart', 'pieChart', 'gauge', 'tableEx', 'card',
              'kpi', 'multiRowCard', 'clusteredBarChart', 'clusteredColumnChart',
              'stackedBarChart', 'stackedColumnChart', 'donutChart', 'funnel',
              'treemap', 'waterfallChart', 'scatterChart']

pbi_data_visuals = visuals_df[visuals_df['visual_type'].isin(data_types)].copy()

# Mapeo PBI page → dashboard page (fuzzy)
dashboard_pages = {p.get('displayName', '').lower(): p.get('displayName', '') for p in dashboard.get('pages', [])}

coverage_rows = []
for _, v in pbi_data_visuals.iterrows():
    pbi_page = v['page']
    pbi_type = v['visual_type']
    pbi_title = v['title']
    pbi_measures = v['measures_used']
    pbi_columns = v['columns_used']

    # Buscar si hay un widget equivalente generado
    matched = False
    match_widget = ""
    db_type = PBI_TO_DATABRICKS.get(pbi_type, pbi_type)

    for gw in generated_widgets:
        page_match = pbi_page.lower().replace(' ', '_').replace('_', '') in gw['page'].lower().replace(' ', '_').replace('_', '')
        if not page_match:
            continue
        # Match por título
        if pbi_title and pbi_title.lower() in gw['title'].lower():
            matched = True
            match_widget = f"[{gw['widget_type']}] {gw['title']}"
            break
        # Match por measures
        if pbi_measures and any(m.lower().replace(' ', '_') in gw['title'].lower().replace(' ', '_') for m in pbi_measures.split(', ') if m):
            matched = True
            match_widget = f"[{gw['widget_type']}] {gw['title']}"
            break
        # Match por tipo de widget (para tablas sin título)
        if db_type == gw['widget_type'] and db_type in ('table', 'pivot'):
            matched = True
            match_widget = f"[{gw['widget_type']}] {gw['title']}"
            break

    coverage_rows.append({
        'PBI Page': pbi_page,
        'PBI Type': pbi_type,
        'PBI Title': pbi_title or '(sin título)',
        'PBI Measures': pbi_measures or '(ninguna)',
        'PBI Columns': pbi_columns[:50] if pbi_columns else '',
        'Generated': '✓' if matched else '✗',
        'Match': match_widget if matched else 'NO GENERADO',
    })

coverage_df = pd.DataFrame(coverage_rows)

total_pbi = len(coverage_df)
total_generated = sum(1 for r in coverage_rows if r['Generated'] == '✓')
total_missing = total_pbi - total_generated

print(f"\n{'='*60}")
print(f"COBERTURA: Power BI → Databricks Dashboard")
print(f"{'='*60}")
print(f"\nVisuales Power BI con datos: {total_pbi}")
print(f"Generados en dashboard:      {total_generated} ✓")
print(f"No generados:                {total_missing} ✗")

if total_missing > 0:
    print(f"\nVisuales NO generados:")
    missing = [r for r in coverage_rows if r['Generated'] == '✗']
    for r in missing:
        print(f"  ✗ [{r['PBI Type']}] {r['PBI Title']} — page: {r['PBI Page']} — measures: {r['PBI Measures']}")

display(coverage_df)


# COMMAND ----------

# MAGIC %md
# MAGIC ## Post-procesamiento determinístico (sin LLM)
# MAGIC
# MAGIC El LLM consistentemente no maneja bien estos cuatro temas:
# MAGIC 1. Counters con `SUM(CASE WHEN... ELSE NULL END)` → Lakeview no los rendea, se ven en blanco
# MAGIC 2. Counters sin `frame.title` → no muestran etiqueta visible
# MAGIC 3. Time counters (MIN period / MAX year) → quedan en el grid en lugar del header
# MAGIC 4. Markdown widgets con líneas vacías → Lakeview las strippea
# MAGIC
# MAGIC Aplicamos fixes deterministas leyendo el dashboard ya generado.

# COMMAND ----------

import sys, os, json
sys.path.insert(0, MODULE_PATH if os.path.isdir(MODULE_PATH) else os.path.dirname(os.path.abspath('')))

from lakeview_post_process import (
    post_process_dashboard,
    patch_dashboard_via_lakeview_api,
    publish_dashboard,
)
from smoke_test import smoke_test_dashboard, print_smoke_test_report

# Leer el dashboard JSON generado
with open(f"/Workspace{DASHBOARD_PATH}" if not DASHBOARD_PATH.startswith('/Workspace') else DASHBOARD_PATH) as f:
    dash = json.load(f)

# Aplicar post-procesamiento
post_process_dashboard(dash, dataset_name=dash['datasets'][0]['name'] if dash.get('datasets') else 'ds_main')

# Guardar resultado
with open(f"/Workspace{DASHBOARD_PATH}" if not DASHBOARD_PATH.startswith('/Workspace') else DASHBOARD_PATH, 'w') as f:
    json.dump(dash, f, indent=2)

print("✓ Post-procesamiento aplicado")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Smoke test
# MAGIC
# MAGIC Verifica que el dataset query corra y los counters retornen valores válidos
# MAGIC ANTES de que el usuario abra el dashboard en el browser.

# COMMAND ----------

issues = smoke_test_dashboard(spark, dash)
print_smoke_test_report(issues)
