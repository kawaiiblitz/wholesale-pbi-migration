# Databricks notebook source
# MAGIC %md
# MAGIC # Agregar Filtros al Dashboard
# MAGIC
# MAGIC Lee el dashboard generado por el notebook 5, lee `pbi_page_filters` para saber qué filtros
# MAGIC tenía cada página en Power BI, y los agrega como widgets `filter-multi-select` dentro de cada página.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Parámetros

# COMMAND ----------



# COMMAND ----------

import json, requests, base64
import pandas as pd

dbutils.widgets.text("catalog", "pbi_migration", "Catálogo")
dbutils.widgets.text("schema", "couch", "Schema")
dbutils.widgets.text("dashboard_path", "/Users/<your-email>@databricks.com/cpg-kpi-coach.lvdash.json", "Path del dashboard")

CATALOG = dbutils.widgets.get("catalog")
SCHEMA = dbutils.widgets.get("schema")
DASHBOARD_PATH = dbutils.widgets.get("dashboard_path")

print(f"Catálogo: {CATALOG}.{SCHEMA}")
print(f"Dashboard: {DASHBOARD_PATH}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Leer dashboard existente

# COMMAND ----------



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
print(f"  Datasets: {len(dashboard.get('datasets', []))}")
print(f"  Pages: {len(dashboard.get('pages', []))}")
for p in dashboard.get('pages', []):
    print(f"    {p.get('displayName', '?')}: {len(p.get('layout', []))} widgets")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Leer filtros de página del Power BI

# COMMAND ----------

pbi_filters = spark.sql(f"SELECT * FROM {CATALOG}.{SCHEMA}.pbi_page_filters").toPandas()
print(f"Total filtros de página: {len(pbi_filters)}")
print(f"Páginas con filtros: {pbi_filters['Pagina'].nunique()}")
print()

# Agrupar por página
filters_by_page = {}
for _, row in pbi_filters.iterrows():
    page = row['Pagina']
    if page not in filters_by_page:
        filters_by_page[page] = []
    filters_by_page[page].append({
        'tabla_pbi': row['Tabla'],
        'columna_pbi': row['Columna'],
        'slicer': row['Slicer'],
    })

for page, filters in sorted(filters_by_page.items()):
    print(f"  {page}: {len(filters)} filtros")

# Leer traductor de nombres PBI → Databricks
try:
    translator_df = spark.sql(f"SELECT * FROM {CATALOG}.{SCHEMA}.pbi_name_translator").toPandas()
    name_map = {}
    for _, t in translator_df.iterrows():
        if t.get('match_method', '') != 'NO MATCH' and t.get('databricks_name', ''):
            name_map[(t['pbi_table'].lower(), t['pbi_name'].lower())] = t['databricks_name']
            name_map[('', t['pbi_name'].lower())] = t['databricks_name']
    print(f"\nTraductor: {len(name_map)} nombres mapeados")
except:
    name_map = {}
    print("\n⚠ Traductor no disponible — matching por nombre directo")

def translate_name(table, name):
    """Traduce un nombre PBI al nombre Databricks."""
    if not name_map:
        return None
    db = name_map.get((table.lower().replace(' ', '_'), name.lower()))
    if db:
        return db
    db = name_map.get(('', name.lower()))
    if db:
        return db
    return None

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Obtener columnas disponibles por dataset

# COMMAND ----------

dataset_columns = {}
for ds in dashboard.get('datasets', []):
    ds_name = ds['name']
    query = ' '.join(ds.get('queryLines', []))
    try:
        schema_df = spark.sql(f"{query} LIMIT 0")
        cols = schema_df.columns
        dataset_columns[ds_name] = list(cols)
        print(f"Dataset {ds_name}: {len(cols)} columnas")
    except Exception as e:
        print(f"Dataset {ds_name}: ERROR — {str(e)[:100]}")
        dataset_columns[ds_name] = []

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Mapear filtros PBI → columnas del dataset de cada página

# COMMAND ----------

def find_column_in_dataset(pbi_table, pbi_col, available_cols):
    """Busca la columna PBI en las columnas del dataset, usando el traductor primero."""
    # 1. Intentar con el traductor
    translated = translate_name(pbi_table, pbi_col)
    if translated:
        for col in available_cols:
            if col.lower() == translated.lower():
                return col

    # 2. Match directo por nombre
    pbi_lower = pbi_col.lower()
    for col in available_cols:
        if col.lower() == pbi_lower:
            return col

    # 3. Match sin underscores
    pbi_flat = pbi_lower.replace('_', '').replace(' ', '')
    for col in available_cols:
        if col.lower().replace('_', '') == pbi_flat:
            return col

    # 4. Match parcial
    for col in available_cols:
        col_flat = col.lower().replace('_', '')
        if len(pbi_flat) > 3 and (pbi_flat in col_flat or col_flat.endswith(pbi_flat)):
            return col

    # 5. Match con nombre de tabla como prefijo (ej: "crs_repunc_messagerefid")
    table_prefix = pbi_table.lower().replace(' ', '_').replace('__', '_')
    combined = f"{table_prefix}_{pbi_lower}".replace('__', '_')
    for col in available_cols:
        if col.lower() == combined or col.lower().replace('_', '') == combined.replace('_', ''):
            return col

    return None

page_filters_mapped = {}
for p in dashboard.get('pages', []):
    page_display = p.get('displayName', '')
    page_name = p.get('name', '')

    if p.get('pageType') == 'PAGE_TYPE_GLOBAL_FILTERS':
        continue

    # Buscar TODOS los datasets usados en esta página
    page_datasets = set()
    for w in p.get('layout', []):
        widget = w.get('widget', {})
        queries = widget.get('queries', [])
        if queries:
            q = queries[0].get('query', {})
            dsn = q.get('datasetName', '')
            if dsn:
                page_datasets.add(dsn)

    if not page_datasets:
        print(f"  {page_display}: no dataset found, skipping")
        continue

    # Usar el primer dataset como principal (para los filtros)
    ds_name = list(page_datasets)[0]
    # Combinar columnas de todos los datasets de la página
    available_cols = []
    for dsn in page_datasets:
        available_cols.extend(dataset_columns.get(dsn, []))

    # Buscar filtros PBI para esta página (matching flexible)
    matched_filters = []
    def normalize_page(name):
        n = name.lower().replace(' ', '_').replace('-', '_')
        for a, b in [('á','a'),('é','e'),('í','i'),('ó','o'),('ú','u'),('ñ','n')]:
            n = n.replace(a, b)
        return n

    def pages_match(pbi_page, db_page):
        pn = normalize_page(pbi_page)
        dn = normalize_page(db_page)
        # Substring match
        if pn in dn or dn in pn:
            return True
        # Word overlap match (at least half of words match)
        pbi_words = set(pn.replace('_', ' ').split())
        db_words = set(dn.replace('_', ' ').split())
        common = pbi_words & db_words
        if len(common) >= max(1, min(len(pbi_words), len(db_words)) // 2):
            return True
        # Key word match (fat, crs, sabana, repunc, reporte, unico)
        pbi_keys = {w for w in pbi_words if len(w) > 2}
        db_keys = {w for w in db_words if len(w) > 2}
        if pbi_keys & db_keys:
            return True
        return False

    for pbi_page, filters in filters_by_page.items():
        if pages_match(pbi_page, page_display):
            for f in filters:
                db_col = find_column_in_dataset(f['tabla_pbi'], f['columna_pbi'], available_cols)
                if db_col:
                    matched_filters.append({
                        'pbi_slicer': f['slicer'],
                        'db_column': db_col,
                        'tabla_pbi': f['tabla_pbi'],
                        'columna_pbi': f['columna_pbi'],
                    })
                else:
                    print(f"  ⚠ {page_display}: filtro '{f['slicer']}' no encontrado en dataset {ds_name}")

    # Deduplicar
    seen = set()
    unique_filters = []
    for mf in matched_filters:
        if mf['db_column'] not in seen:
            seen.add(mf['db_column'])
            unique_filters.append(mf)

    page_filters_mapped[page_name] = {
        'display_name': page_display,
        'dataset': ds_name,
        'filters': unique_filters,
    }

    print(f"  {page_display} (dataset: {ds_name}): {len(unique_filters)} filtros")
    for f in unique_filters:
        print(f"    {f['pbi_slicer']} → {f['db_column']}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Agregar filtros como widgets dentro de cada página

# COMMAND ----------

import uuid

applied_filters = []
updated_dashboard = json.loads(json.dumps(dashboard))  # deep copy

# Eliminar página Global Filters si existe (ya no la usamos)
updated_dashboard['pages'] = [p for p in updated_dashboard['pages'] if p.get('pageType') != 'PAGE_TYPE_GLOBAL_FILTERS']

for p in updated_dashboard.get('pages', []):
    page_name = p.get('name', '')
    page_display = p.get('displayName', '')

    page_info = page_filters_mapped.get(page_name, {})
    filters = page_info.get('filters', [])
    ds_name = page_info.get('dataset', '')

    if not filters:
        print(f"  {page_display}: sin filtros")
        continue

    # Eliminar filtros existentes de esta página (para no duplicar)
    p['layout'] = [w for w in p.get('layout', [])
                   if w.get('widget', {}).get('spec', {}).get('widgetType', '') not in ('filter-multi-select', 'filter-single-select')]

    # Encontrar la posición Y más alta actual (para poner filtros arriba o abajo)
    # Los filtros van justo después del título (y=1)
    # Desplazar los widgets existentes hacia abajo para hacer espacio
    filter_height = 2
    num_filter_rows = (len(filters) + 5) // 6  # 6 filtros por fila (width=2 cada uno)
    total_filter_height = num_filter_rows * filter_height

    # Desplazar widgets existentes hacia abajo
    for w in p.get('layout', []):
        pos = w.get('position', {})
        widget = w.get('widget', {})
        # No desplazar el título
        if 'textbox_spec' in widget or 'multilineTextboxSpec' in widget:
            continue
        if pos.get('y', 0) >= 1:
            pos['y'] = pos.get('y', 0) + total_filter_height

    # Crear widgets de filtro
    filter_x = 0
    filter_y = 1  # justo después del título
    for f in filters:
        widget_name = str(uuid.uuid4())[:8]
        query_name = f"{ds_name}_{f['db_column']}"
        filter_label = f['pbi_slicer']  # "Tabla.Columna"

        filter_widget = {
            "widget": {
                "name": widget_name,
                "queries": [{
                    "name": query_name,
                    "query": {
                        "datasetName": ds_name,
                        "fields": [
                            {"name": f['db_column'], "expression": f"`{f['db_column']}`"},
                            {"name": f"{f['db_column']}_associativity", "expression": "COUNT_IF(`associative_filter_predicate_group`)"}
                        ],
                        "disaggregated": False
                    }
                }],
                "spec": {
                    "version": 2,
                    "frame": {
                        "title": filter_label,
                        "showTitle": False,
                        "showDescription": True,
                        "description": f['columna_pbi']
                    },
                    "widgetType": "filter-multi-select",
                    "encodings": {
                        "fields": [{
                            "fieldName": f['db_column'],
                            "queryName": query_name
                        }]
                    }
                }
            },
            "position": {"x": filter_x, "y": filter_y, "width": 2, "height": filter_height}
        }
        p['layout'].append(filter_widget)

        applied_filters.append({
            'page': page_display,
            'pbi_slicer': filter_label,
            'db_column': f['db_column'],
            'dataset': ds_name,
            'status': 'APPLIED',
        })

        # Avanzar posición (6 filtros por fila)
        filter_x += 2
        if filter_x >= 12:
            filter_x = 0
            filter_y += filter_height

    filter_count = len(filters)
    total_widgets = len(p.get('layout', []))
    print(f"  {page_display}: {filter_count} filtros agregados ({total_widgets} widgets total)")

print(f"\nTotal filtros aplicados: {len(applied_filters)}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. Guardar dashboard actualizado

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
# MAGIC ## 8. Guardar tabla de filtros aplicados

# COMMAND ----------

# Incluir filtros no mapeados
all_filter_rows = list(applied_filters)
for pbi_page, filters in filters_by_page.items():
    for f in filters:
        already = any(
            af['pbi_slicer'] == f['slicer']
            for af in applied_filters
        )
        if not already:
            all_filter_rows.append({
                'page': pbi_page,
                'pbi_slicer': f['slicer'],
                'db_column': '',
                'dataset': '',
                'status': 'NOT MAPPED',
            })

filters_applied_df = pd.DataFrame(all_filter_rows)
spark.createDataFrame(filters_applied_df.astype(str)).write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{CATALOG}.{SCHEMA}.pbi_dashboard_filters")
print(f"✓ {CATALOG}.{SCHEMA}.pbi_dashboard_filters ({len(filters_applied_df)} filas)")
display(filters_applied_df)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 9. Resumen

# COMMAND ----------

total_applied = len([r for r in all_filter_rows if r['status'] == 'APPLIED'])
total_not_mapped = len([r for r in all_filter_rows if r['status'] == 'NOT MAPPED'])

print(f"{'='*60}")
print(f"FILTROS DEL DASHBOARD (por página)")
print(f"{'='*60}")
print(f"\nDashboard: {DASHBOARD_PATH}")
print(f"Filtros aplicados: {total_applied} ✓")
print(f"Filtros sin mapear: {total_not_mapped} ✗")
print()

for page_name, info in page_filters_mapped.items():
    print(f"  {info['display_name']} (dataset: {info['dataset']}):")
    if info['filters']:
        for f in info['filters']:
            print(f"    ✓ {f['pbi_slicer']} → {f['db_column']}")
    else:
        print(f"    (sin filtros)")

if total_not_mapped > 0:
    print(f"\nFiltros NO mapeados:")
    for r in all_filter_rows:
        if r['status'] == 'NOT MAPPED':
            print(f"  ✗ {r['page']}: {r['pbi_slicer']}")

# COMMAND ----------



# COMMAND ----------



# COMMAND ----------



# COMMAND ----------



# COMMAND ----------



# COMMAND ----------


