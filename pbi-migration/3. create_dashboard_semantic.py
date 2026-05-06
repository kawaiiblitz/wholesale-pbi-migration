# Databricks notebook source
# MAGIC %md
# MAGIC # Crear Capa Semántica del Dashboard
# MAGIC
# MAGIC Lee los SQLs de `dashboard_view_sqls` y genera el `.lvdash.json` con los datasets correctos.

# COMMAND ----------

#/Workspace/Users/<your-email>@databricks.com/pbi-migration/cpg-kpi-coach.lvdash.json

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Parámetros

# COMMAND ----------

dbutils.widgets.text("catalog", "pbi_migration", "Catálogo")
dbutils.widgets.text("schema", "couch", "Schema")
dbutils.widgets.text("dashboard_path",
                     "/Workspace/Users/<your-email>@databricks.com/pbi-migration/cpg-kpi-coach.lvdash.json",
                     "Path del dashboard")
dbutils.widgets.text("pbix_path", "", "Path del .pbix (para extraer páginas reales)")
CATALOG = dbutils.widgets.get("catalog")
SCHEMA = dbutils.widgets.get("schema")
DASHBOARD_PATH = dbutils.widgets.get("dashboard_path")
PBIX_PATH = dbutils.widgets.get("pbix_path")

print(f"Catálogo: {CATALOG}.{SCHEMA}")
print(f"Dashboard: {DASHBOARD_PATH}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Leer SQLs de la tabla

# COMMAND ----------

import json

sql_df = spark.sql(f"SELECT * FROM {CATALOG}.{SCHEMA}.dashboard_view_sqls").toPandas()
print(f"{len(sql_df)} vistas encontradas:")
for _, row in sql_df.iterrows():
    print(f"  {row['vista_dashboard']}: {row['num_dimensiones']} dims, {row['num_measures']} measures")
display(sql_df[['vista_dashboard', 'metric_view', 'num_dimensiones', 'num_measures', 'measures']])

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Generar datasets del dashboard
# MAGIC
# MAGIC Cada SQL de la tabla se convierte en un dataset del `.lvdash.json`.
# MAGIC El query del dataset es el SELECT interno (sin el CREATE VIEW).

# COMMAND ----------

# Importar el builder de dataset query dinámico
import sys, os
MODULE_PATH_LOCAL = os.path.join(os.path.dirname(os.path.abspath('')), 'modules')
sys.path.insert(0, MODULE_PATH_LOCAL if os.path.isdir(MODULE_PATH_LOCAL) else '/Workspace' + os.path.dirname(DASHBOARD_PATH).rstrip('/') + '/modules')
try:
    from dynamic_dataset_query import build_dataset_query
    USE_DYNAMIC_DATASET = True
except ImportError:
    USE_DYNAMIC_DATASET = False
    print("⚠ dynamic_dataset_query no disponible, usando SQL de dashboard_view_sqls")

datasets = []
pages = []

# 1. DATASETS: uno por cada metric view / vista del dashboard
# Si dynamic_dataset_query está disponible, construye el query leyendo
# dimensions+measures DEL VIVO de la metric view (no hardcoded list).
# Esto resuelve el bug donde agregar measures a la metric view después
# no las hace visibles al dashboard.
for _, row in sql_df.iterrows():
    vista = row['vista_dashboard']
    mv = row['metric_view']
    sql = row['sql']

    # Nombre del dataset: derivar del nombre de la vista
    view_short = vista.replace(f'{CATALOG}.{SCHEMA}.', '')
    ds_name = view_short.replace('v_dashboard_', 'ds_')
    display_name = view_short.replace('v_dashboard_', '').replace('_', ' ').title()

    # Construir queryLines
    if USE_DYNAMIC_DATASET:
        try:
            mv_short = mv.split('.')[-1] if '.' in mv else mv
            query_lines = build_dataset_query(spark, CATALOG, SCHEMA, mv_short)
            print(f"Dataset: {ds_name} (DINÁMICO desde metric view {mv_short})")
        except Exception as e:
            print(f"  ⚠ {ds_name}: dynamic build falló ({str(e)[:100]}), usando SQL stored")
            select_idx = sql.upper().find('SELECT')
            select_sql = sql[select_idx:] if select_idx >= 0 else sql
            query_lines = [select_sql]
    else:
        select_idx = sql.upper().find('SELECT')
        select_sql = sql[select_idx:] if select_idx >= 0 else sql
        query_lines = [select_sql]
        print(f"Dataset: {ds_name} (HARDCODED desde dashboard_view_sqls)")

    datasets.append({
        "name": ds_name,
        "displayName": display_name,
        "queryLines": query_lines
    })

    print(f"  Display: {display_name}")
    preview = ''.join(query_lines)[:100]
    print(f"  Query: {preview}...")

# 2. PÁGINAS: una por cada página real del PBIX (no por dataset).
# Leemos directo del .pbix Layout para no depender de pbi_visuals (paso 4).
# Excluimos tooltips (page name empieza con 'tooltip_').
print()
print("=" * 60)
print("Generando páginas a partir del Layout del PBIX...")

import re, io, zipfile

pbi_pages_info = []  # [(displayName, ordinal, num_visuals)]

if PBIX_PATH:
    try:
        with open(PBIX_PATH, 'rb') as f:
            pbix_bytes = f.read()
        with zipfile.ZipFile(io.BytesIO(pbix_bytes)) as zf:
            layout_raw = zf.read('Report/Layout')
            layout_text = layout_raw.decode('utf-16-le').lstrip('﻿')
            layout_json = json.loads(layout_text)
        for s in layout_json.get('sections', []):
            display = s.get('displayName', '?')
            if display.lower().startswith('tooltip'):
                continue
            pbi_pages_info.append((display, s.get('ordinal', 0), len(s.get('visualContainers', []))))
        pbi_pages_info.sort(key=lambda x: x[1])
    except Exception as e:
        print(f"  WARN no pude leer .pbix Layout: {e}")
        pbi_pages_info = []

# Fallback: leer pbi_visuals si existe
if not pbi_pages_info:
    try:
        pbi_pages_df = spark.sql(f"""
            SELECT page, MIN(CAST(page_order AS INT)) AS page_order, COUNT(*) AS num_visuales
            FROM {CATALOG}.{SCHEMA}.pbi_visuals
            WHERE page IS NOT NULL AND LOWER(page) NOT LIKE 'tooltip%%'
            GROUP BY page ORDER BY page_order
        """).toPandas()
        pbi_pages_info = [(r['page'], r['page_order'], r['num_visuales']) for _, r in pbi_pages_df.iterrows()]
    except Exception as e:
        print(f"  WARN no hay pbi_visuals tampoco: {e}")

print(f"{len(pbi_pages_info)} páginas (sin tooltips):")
for display, order, num_visuals in pbi_pages_info:
    page_name = re.sub(r'[^a-z0-9_]', '_', display.lower()).strip('_')
    page_name = re.sub(r'_+', '_', page_name)
    if not page_name:
        page_name = f"page_{order}"

    pages.append({
        "name": page_name,
        "displayName": display,
        "pageType": "PAGE_TYPE_CANVAS",
        "layoutVersion": "GRID_V1"
    })
    print(f"  → {page_name}: '{display}' ({num_visuals} visuales)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Generar el .lvdash.json

# COMMAND ----------

dashboard = {
    "datasets": datasets,
    "pages": pages,
    "uiSettings": {
        "theme": {
            "widgetHeaderAlignment": "ALIGNMENT_UNSPECIFIED"
        },
        "applyModeEnabled": False
    }
}

dashboard_json = json.dumps(dashboard, indent=2, ensure_ascii=False)
print(dashboard_json)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Guardar el dashboard en el workspace

# COMMAND ----------

import requests, base64

token = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().get()
host = spark.conf.get("spark.databricks.workspaceUrl")

# Codificar el JSON en base64
content_b64 = base64.b64encode(dashboard_json.encode('utf-8')).decode('utf-8')

# Subir al workspace via API REST
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
# MAGIC ## 6. Resumen

# COMMAND ----------

print(f"{'='*60}")
print(f"CAPA SEMÁNTICA DEL DASHBOARD")
print(f"{'='*60}")
print(f"\nDashboard: {DASHBOARD_PATH}")
print(f"Datasets: {len(datasets)}")
print(f"Páginas: {len(pages)}")
print()
for ds in datasets:
    print(f"  {ds['name']}: {ds['displayName']}")
