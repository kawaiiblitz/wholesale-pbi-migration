# Databricks notebook source
# MAGIC %md
# MAGIC # 9. Generar Reporte PDF de Migración
# MAGIC
# MAGIC Lee las tablas generadas por la pipeline y produce un PDF con el resumen
# MAGIC de la migración: tablas, measures, visuales, cobertura y validación.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Parámetros

# COMMAND ----------

import json, requests, base64
import pandas as pd
from datetime import datetime

dbutils.widgets.text("catalog", "pbi_migration", "Catálogo")
dbutils.widgets.text("schema", "default", "Schema")
dbutils.widgets.text("dashboard_path", "", "Path del dashboard")

CATALOG = dbutils.widgets.get("catalog")
SCHEMA = dbutils.widgets.get("schema")
DASHBOARD_PATH = dbutils.widgets.get("dashboard_path")

print(f"Catálogo: {CATALOG}.{SCHEMA}")
print(f"Dashboard: {DASHBOARD_PATH}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Leer tablas de la pipeline

# COMMAND ----------

def safe_read(table):
    try:
        return spark.sql(f"SELECT * FROM {CATALOG}.{SCHEMA}.{table}").toPandas()
    except:
        return pd.DataFrame()

measures_df = safe_read("pbi_measures")
visuals_df = safe_read("pbi_visuals")
fields_df = safe_read("pbi_visual_fields")
sqls_df = safe_read("dashboard_view_sqls")
translator_df = safe_read("pbi_name_translator")
styles_df = safe_read("pbi_styles")
props_df = safe_read("pbi_visual_props")
filters_df = safe_read("pbi_dashboard_filters")

print(f"Measures: {len(measures_df)}")
print(f"Visuals: {len(visuals_df)}")
print(f"Fields: {len(fields_df)}")
print(f"Dashboard views: {len(sqls_df)}")
print(f"Name translator: {len(translator_df)}")
print(f"Styles: {len(styles_df)}")
print(f"Visual props: {len(props_df)}")
print(f"Dashboard filters: {len(filters_df)}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Leer dashboard generado

# COMMAND ----------

token = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().get()
host = spark.conf.get("spark.databricks.workspaceUrl")

dashboard = {}
if DASHBOARD_PATH:
    try:
        resp = requests.get(
            f"https://{host}/api/2.0/workspace/export",
            params={"path": DASHBOARD_PATH, "format": "AUTO"},
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        resp.raise_for_status()
        dashboard = json.loads(base64.b64decode(resp.json()["content"]).decode("utf-8"))
        print(f"Dashboard: {len(dashboard.get('datasets', []))} datasets, {len(dashboard.get('pages', []))} pages")
    except Exception as e:
        print(f"⚠ No se pudo leer dashboard: {e}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Generar reporte HTML

# COMMAND ----------

now = datetime.now().strftime("%Y-%m-%d %H:%M")

# Conteos
n_measures = len(measures_df)
n_visuals = len(visuals_df)
n_views = len(sqls_df)
n_datasets = len(dashboard.get('datasets', []))
n_pages = len(dashboard.get('pages', []))
n_widgets = sum(len(p.get('layout', [])) for p in dashboard.get('pages', []))
n_filters_applied = len(filters_df[filters_df.get('status', pd.Series()) == 'APPLIED']) if not filters_df.empty else 0
n_filters_missing = len(filters_df[filters_df.get('status', pd.Series()) == 'NOT MAPPED']) if not filters_df.empty else 0
n_translated = len(translator_df[translator_df.get('match_method', pd.Series()) != 'NO MATCH']) if not translator_df.empty else 0
n_untranslated = len(translator_df[translator_df.get('match_method', pd.Series()) == 'NO MATCH']) if not translator_df.empty else 0

# Widget types in dashboard
widget_types = {}
for p in dashboard.get('pages', []):
    for w in p.get('layout', []):
        wt = w.get('widget', {}).get('spec', {}).get('widgetType', 'text')
        widget_types[wt] = widget_types.get(wt, 0) + 1

# Measures by status
measure_statuses = {}
if not measures_df.empty and 'Status' in measures_df.columns:
    measure_statuses = measures_df['Status'].value_counts().to_dict()

html = f"""
<html>
<head>
<style>
    body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 40px; color: #333; }}
    h1 {{ color: #1B3A5C; border-bottom: 3px solid #2E6DB4; padding-bottom: 10px; }}
    h2 {{ color: #2E6DB4; margin-top: 30px; }}
    h3 {{ color: #555; }}
    table {{ border-collapse: collapse; width: 100%; margin: 10px 0; }}
    th {{ background: #1B3A5C; color: white; padding: 8px 12px; text-align: left; }}
    td {{ border: 1px solid #ddd; padding: 6px 12px; }}
    tr:nth-child(even) {{ background: #f8f9fb; }}
    .metric {{ display: inline-block; background: #f1f5f9; border-radius: 8px; padding: 15px 25px; margin: 5px; text-align: center; }}
    .metric .value {{ font-size: 2rem; font-weight: 700; color: #1B3A5C; }}
    .metric .label {{ font-size: 0.85rem; color: #666; }}
    .ok {{ color: #166534; font-weight: 600; }}
    .err {{ color: #991b1b; font-weight: 600; }}
    .footer {{ margin-top: 40px; padding-top: 10px; border-top: 1px solid #ddd; color: #999; font-size: 0.8rem; }}
</style>
</head>
<body>

<h1>Reporte de Migración Power BI → Databricks AI/BI</h1>
<p><strong>Catálogo:</strong> {CATALOG}.{SCHEMA} | <strong>Dashboard:</strong> {DASHBOARD_PATH} | <strong>Fecha:</strong> {now}</p>

<h2>Resumen</h2>
<div>
    <div class="metric"><div class="value">{n_measures}</div><div class="label">Measures PBI</div></div>
    <div class="metric"><div class="value">{n_visuals}</div><div class="label">Visuales PBI</div></div>
    <div class="metric"><div class="value">{n_views}</div><div class="label">Dashboard Views</div></div>
    <div class="metric"><div class="value">{n_datasets}</div><div class="label">Datasets</div></div>
    <div class="metric"><div class="value">{n_pages}</div><div class="label">Páginas</div></div>
    <div class="metric"><div class="value">{n_widgets}</div><div class="label">Widgets</div></div>
</div>

<h2>Widgets por Tipo</h2>
<table>
<tr><th>Tipo</th><th>Cantidad</th></tr>
{"".join(f"<tr><td>{wt}</td><td>{count}</td></tr>" for wt, count in sorted(widget_types.items()))}
</table>

<h2>Traducción de Nombres</h2>
<p><span class="ok">✓ {n_translated} nombres traducidos</span> | <span class="err">✗ {n_untranslated} sin traducción</span></p>
"""

if not translator_df.empty and n_untranslated > 0:
    unmatched = translator_df[translator_df['match_method'] == 'NO MATCH']
    html += "<table><tr><th>Nombre PBI</th><th>Tabla PBI</th><th>Tipo</th></tr>"
    for _, r in unmatched.head(20).iterrows():
        html += f"<tr><td>{r.get('pbi_name','')}</td><td>{r.get('pbi_table','')}</td><td>{r.get('pbi_type','')}</td></tr>"
    html += "</table>"

html += f"""
<h2>Filtros del Dashboard</h2>
<p><span class="ok">✓ {n_filters_applied} filtros aplicados</span> | <span class="err">✗ {n_filters_missing} sin mapear</span></p>
"""

if not filters_df.empty and n_filters_missing > 0:
    missing = filters_df[filters_df['status'] == 'NOT MAPPED']
    html += "<table><tr><th>Página</th><th>Filtro PBI</th></tr>"
    for _, r in missing.head(20).iterrows():
        html += f"<tr><td>{r.get('page','')}</td><td>{r.get('pbi_slicer','')}</td></tr>"
    html += "</table>"

html += """
<h2>Dashboard Views (SQL)</h2>
"""
if not sqls_df.empty:
    html += "<table><tr><th>Vista</th><th>Metric View</th><th>Dims</th><th>Measures</th></tr>"
    for _, r in sqls_df.iterrows():
        html += f"<tr><td>{r.get('vista_dashboard','')}</td><td>{r.get('metric_view','')}</td><td>{r.get('num_dimensiones','')}</td><td>{r.get('num_measures','')}</td></tr>"
    html += "</table>"

html += """
<h2>Páginas del Dashboard</h2>
"""
for p in dashboard.get('pages', []):
    pname = p.get('displayName', '?')
    layout = p.get('layout', [])
    html += f"<h3>{pname} ({len(layout)} widgets)</h3>"
    html += "<table><tr><th>Tipo</th><th>Título</th><th>Posición</th></tr>"
    for w in layout:
        widget = w.get('widget', {})
        spec = widget.get('spec', {})
        wtype = spec.get('widgetType', 'text')
        title = spec.get('frame', {}).get('title', widget.get('name', ''))
        pos = w.get('position', {})
        html += f"<tr><td>{wtype}</td><td>{title}</td><td>x={pos.get('x')}, y={pos.get('y')}, w={pos.get('width')}, h={pos.get('height')}</td></tr>"
    html += "</table>"

html += f"""
<div class="footer">
    Generado automáticamente por la pipeline de migración PBI → Databricks | {now}
</div>
</body>
</html>
"""

print(f"HTML generado: {len(html)} caracteres")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Guardar como HTML en Volume

# COMMAND ----------

report_name = f"migration_report_{CATALOG}_{SCHEMA}_{datetime.now().strftime('%Y%m%d_%H%M')}"

# Guardar en Volume
volume_path = f"/Volumes/{CATALOG}/{SCHEMA}/reports"
try:
    spark.sql(f"CREATE VOLUME IF NOT EXISTS {CATALOG}.{SCHEMA}.reports")
except:
    pass

html_path = f"{volume_path}/{report_name}.html"
dbutils.fs.put(html_path, html, overwrite=True)
print(f"✓ Reporte guardado: {html_path}")

# También guardar como tabla para referencia
report_row = [{
    'report_date': now,
    'catalog': CATALOG,
    'schema': SCHEMA,
    'dashboard_path': DASHBOARD_PATH,
    'n_measures': n_measures,
    'n_visuals': n_visuals,
    'n_views': n_views,
    'n_datasets': n_datasets,
    'n_pages': n_pages,
    'n_widgets': n_widgets,
    'n_filters_applied': n_filters_applied,
    'n_filters_missing': n_filters_missing,
    'n_names_translated': n_translated,
    'n_names_untranslated': n_untranslated,
}]
report_df = pd.DataFrame(report_row)
spark.createDataFrame(report_df).write.mode("append").saveAsTable(f"{CATALOG}.{SCHEMA}.pbi_migration_reports")
print(f"✓ Registro guardado en {CATALOG}.{SCHEMA}.pbi_migration_reports")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Mostrar reporte

# COMMAND ----------

displayHTML(html)
