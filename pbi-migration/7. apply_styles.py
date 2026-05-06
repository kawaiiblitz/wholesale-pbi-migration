# Databricks notebook source
# MAGIC %md
# MAGIC # Aplicar Estilos al Dashboard
# MAGIC
# MAGIC Lee el dashboard existente y aplica los colores y fuentes extraídos del Power BI.

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
# MAGIC ## 2. Leer dashboard existente

# COMMAND ----------

token = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().get()
host = spark.conf.get("spark.databricks.workspaceUrl")

resp = requests.get(
    f"https://{host}/api/2.0/workspace/export",
    params={"path": DASHBOARD_PATH, "format": "AUTO"},
    headers={"Authorization": f"Bearer {token}"},
    timeout=30,
)
resp.raise_for_status()
existing_json = base64.b64decode(resp.json()["content"]).decode("utf-8")
dashboard = json.loads(existing_json)

print(f"✓ Dashboard leído: {DASHBOARD_PATH}")
for p in dashboard.get('pages', []):
    print(f"  {p.get('displayName', '?')}: {len(p.get('layout', []))} widgets")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Leer estilos del Power BI

# COMMAND ----------

styles_df = spark.sql(f"SELECT * FROM {CATALOG}.{SCHEMA}.pbi_styles").toPandas()
print(f"Total estilos: {len(styles_df)}")

# Extraer paleta de colores
palette = styles_df[styles_df['category'] == 'theme_palette'].sort_values('property')
color_list = palette['value'].tolist()
print(f"\nPaleta de colores ({len(color_list)}):")
for c in color_list:
    print(f"  {c}")

# Extraer colores del tema
theme_colors = {}
for _, row in styles_df[styles_df['category'] == 'theme_color'].iterrows():
    theme_colors[row['property']] = row['value']
print(f"\nColores del tema:")
for k, v in theme_colors.items():
    print(f"  {k}: {v}")

# Extraer fuentes
fonts = styles_df[styles_df['category'].isin(['theme_font', 'visual_font'])].drop_duplicates(subset=['property', 'value'])
if not fonts.empty:
    print(f"\nFuentes:")
    for _, row in fonts.iterrows():
        print(f"  {row['property']}: {row['value']}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Aplicar colores a los widgets

# COMMAND ----------

updated_dashboard = json.loads(json.dumps(dashboard))  # deep copy

widgets_updated = 0
for p in updated_dashboard.get('pages', []):
    page_display = p.get('displayName', '')

    for w in p.get('layout', []):
        widget = w.get('widget', {})
        spec = widget.get('spec', {})
        wtype = spec.get('widgetType', '')

        if not wtype or wtype.startswith('filter'):
            continue

        # Aplicar paleta de colores a charts (bar, line, pie, area, scatter, combo)
        if wtype in ('bar', 'line', 'pie', 'area', 'scatter', 'combo', 'funnel', 'waterfall') and color_list:
            if 'mark' not in spec:
                spec['mark'] = {}
            spec['mark']['colors'] = color_list
            widgets_updated += 1

        # Aplicar color principal a counters
        elif wtype == 'counter' and color_list:
            if 'mark' not in spec:
                spec['mark'] = {}
            spec['mark']['colors'] = [color_list[0]]
            widgets_updated += 1

print(f"✓ Colores aplicados a {widgets_updated} widgets")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Guardar dashboard actualizado

# COMMAND ----------

dashboard_json_str = json.dumps(updated_dashboard, indent=2, ensure_ascii=False)
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
    print(f"✓ Dashboard actualizado: {DASHBOARD_PATH}")
else:
    print(f"✗ Error ({resp.status_code}): {resp.text}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Resumen

# COMMAND ----------

print(f"{'='*60}")
print(f"ESTILOS APLICADOS AL DASHBOARD")
print(f"{'='*60}")
print(f"\nDashboard: {DASHBOARD_PATH}")
print(f"Widgets actualizados: {widgets_updated}")
print(f"\nPaleta de colores aplicada:")
for i, c in enumerate(color_list[:10]):
    print(f"  Color {i}: {c}")
if len(color_list) > 10:
    print(f"  ... +{len(color_list)-10} más")
