# Databricks notebook source
# MAGIC %md
# MAGIC # 5b. Refinar Dashboard
# MAGIC
# MAGIC Toma el dashboard generado por el notebook 5 y aplica validaciones determinísticas
# MAGIC para limpiar problemas comunes que causan el warning:
# MAGIC *"Unsupported widget definition was automatically fixed in file import"*
# MAGIC
# MAGIC

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Parámetros

# COMMAND ----------

import json, requests, base64

dbutils.widgets.text("catalog", "pbi_migration", "Catálogo")
dbutils.widgets.text("schema", "default", "Schema")
dbutils.widgets.text("dashboard_path",
                     "/Users/<your-email>@databricks.com/pbi-migration/cpg-kpi-coach.lvdash.json",
                     "Path del dashboard")

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
dashboard = json.loads(base64.b64decode(resp.json()["content"]).decode("utf-8"))

print(f"✓ Dashboard leído: {DASHBOARD_PATH}")
print(f"  Datasets: {len(dashboard.get('datasets', []))}")
print(f"  Pages: {len(dashboard.get('pages', []))}")
for p in dashboard.get('pages', []):
    print(f"    {p.get('displayName', '?')}: {len(p.get('layout', []))} widgets")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Limpiar widgets
# MAGIC
# MAGIC Aplica reglas determinísticas para corregir problemas comunes.

# COMMAND ----------

import re

# --- Pre-compute: extract MEASURE columns from each dataset's SQL ---
ds_measures = {}
for ds in dashboard.get('datasets', []):
    query = ' '.join(ds.get('queryLines', []))
    name = ds['name']
    measures = re.findall(r'MEASURE\((\w+)\)\s+as\s+(\w+)', query, re.IGNORECASE)
    if len(measures) >= 2:
        ds_measures[name] = {
            'value_col': measures[0][1],
            'global_col': measures[1][1],
        }
    elif len(measures) == 1:
        ds_measures[name] = {
            'value_col': measures[0][1],
            'global_col': None,
        }

print(f"Datasets con measures detectadas:")
for k, v in ds_measures.items():
    print(f"  {k}: value={v['value_col']}, global={v['global_col']}")
print()

fixes = []
total_widgets = 0

for page in dashboard.get('pages', []):
    pname = page.get('displayName', 'unnamed')
    for layout in page.get('layout', []):
        total_widgets += 1
        w = layout.get('widget', {})
        wname = w.get('name', '?')
        spec = w.get('spec', {})
        wtype = spec.get('widgetType', '')
        encodings = spec.get('encodings', {})

        # --- COUNTER fixes ---
        if wtype == 'counter':
            # Fix 1: si tiene "comparison", renombrar a "target"
            if 'comparison' in encodings and 'target' not in encodings:
                encodings['target'] = encodings.pop('comparison')
                fixes.append(f"{pname}/{wname}: renamed 'comparison' → 'target'")

            # Fix 2: limpiar propiedades inválidas del target (preservar change y format)
            for enc_key in ['target']:
                enc = encodings.get(enc_key, {})
                for bad_prop in ['displayName', 'scale']:
                    if bad_prop in enc:
                        del enc[bad_prop]
                        fixes.append(f"{pname}/{wname}: removed '{bad_prop}' from {enc_key}")

            # Fix 3: asegurar que target tenga change si no lo tiene
            target_enc = encodings.get('target', {})
            if target_enc and 'fieldName' in target_enc and 'change' not in target_enc:
                target_enc['change'] = {"type": "percent"}
                fixes.append(f"{pname}/{wname}: added 'change' to target")

            # Fix 4: detectar fields genéricos (COUNT(*) idénticos) y reemplazar con columnas MEASURE reales
            queries = w.get('queries', [])
            if queries:
                query = queries[0].get('query', {})
                ds_name = query.get('datasetName', '')
                fields = query.get('fields', [])

                # Detectar si todos los fields usan la misma expresión genérica
                expressions = [f.get('expression', '') for f in fields]
                all_same = len(set(expressions)) == 1 and len(expressions) > 1
                all_count_star = all('COUNT(*)' in expr.upper() or 'COUNT(1)' in expr.upper() for expr in expressions)

                if (all_same or all_count_star) and ds_name in ds_measures:
                    cols = ds_measures[ds_name]
                    val_col = cols['value_col']
                    glob_col = cols['global_col']

                    if val_col and glob_col:
                        # Reemplazar fields con las columnas reales
                        query['fields'] = [
                            {"name": f"sum({val_col})", "expression": f"SUM(`{val_col}`)"},
                            {"name": f"sum({glob_col})", "expression": f"SUM(`{glob_col}`)"},
                        ]
                        query['disaggregated'] = False
                        # Actualizar encodings para que apunten a los fields correctos
                        encodings['value'] = {"fieldName": f"sum({val_col})"}
                        encodings['target'] = {
                            "fieldName": f"sum({glob_col})",
                            "change": {"type": "percent"}
                        }
                        fixes.append(f"{pname}/{wname}: replaced generic COUNT(*) with real measures ({val_col}, {glob_col})")
                    elif val_col:
                        query['fields'] = [
                            {"name": f"sum({val_col})", "expression": f"SUM(`{val_col}`)"},
                        ]
                        encodings['value'] = {"fieldName": f"sum({val_col})"}
                        fixes.append(f"{pname}/{wname}: replaced generic COUNT(*) with real measure ({val_col})")

            # Fix 5: quitar frame de counters
            if 'frame' in spec:
                del spec['frame']
                fixes.append(f"{pname}/{wname}: removed 'frame' from counter")

        # --- TABLE fixes ---
        if wtype == 'table':
            # Fix 3: asegurar invisibleColumns existe
            if 'invisibleColumns' not in encodings:
                encodings['invisibleColumns'] = []
                fixes.append(f"{pname}/{wname}: added 'invisibleColumns: []'")

            # Fix 4: asegurar cada columna tenga propiedades requeridas
            columns = encodings.get('columns', [])
            for col in columns:
                if 'title' not in col and 'displayName' in col:
                    col['title'] = col['displayName']
                if 'type' not in col:
                    col['type'] = 'string'
                if 'displayAs' not in col:
                    col['displayAs'] = 'string'

        # --- TEXT widget fixes ---
        if 'textboxSpec' in w:
            inner = w['textboxSpec']
            if isinstance(inner, dict) and 'multilineTextboxSpec' in inner:
                w['multilineTextboxSpec'] = inner['multilineTextboxSpec']
                del w['textboxSpec']
                fixes.append(f"{pname}/{wname}: fixed textboxSpec → multilineTextboxSpec")
            elif isinstance(inner, str):
                w['multilineTextboxSpec'] = {"lines": [inner]}
                del w['textboxSpec']
                fixes.append(f"{pname}/{wname}: converted textboxSpec string → multilineTextboxSpec")

        # --- GENERIC fixes ---
        if spec:
            # Fix 5: query nesting
            for q in w.get('queries', []):
                if 'datasetName' in q and 'query' not in q:
                    q['query'] = {
                        'datasetName': q.pop('datasetName'),
                        'fields': q.pop('fields', []),
                        'disaggregated': q.pop('disaggregated', False),
                    }
                    fixes.append(f"{pname}/{wname}: fixed query nesting")

print(f"Widgets analizados: {total_widgets}")
print(f"Correcciones aplicadas: {len(fixes)}")
for fix in fixes:
    print(f"  → {fix}")

if not fixes:
    print("  (ninguna corrección necesaria)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Validar naming
# MAGIC
# MAGIC Revisa que displayNames y títulos sean legibles (no abreviaciones ni IDs técnicos).

# COMMAND ----------

import re

naming_warnings = []

for page in dashboard.get('pages', []):
    pname = page.get('displayName', 'unnamed')
    for layout in page.get('layout', []):
        w = layout.get('widget', {})
        spec = w.get('spec', {})
        wname = w.get('name', '?')
        wtype = spec.get('widgetType', '')
        frame = spec.get('frame', {})
        title = frame.get('title', '')

        # Detectar títulos técnicos (widget IDs como títulos)
        if title and re.match(r'^[a-f0-9]{8}$', title):
            naming_warnings.append(f"{pname}/{wname}: title is a hex ID '{title}' — should be human-readable")

        # Detectar títulos con snake_case
        if title and '_' in title and not any(c.isupper() for c in title):
            naming_warnings.append(f"{pname}/{wname}: title '{title}' looks like snake_case — should be human-readable")

        # Detectar displayNames técnicos en encodings
        encodings = spec.get('encodings', {})
        for enc_key, enc_val in encodings.items():
            if isinstance(enc_val, dict):
                dn = enc_val.get('displayName', '')
                if dn and dn == enc_val.get('fieldName', ''):
                    naming_warnings.append(f"{pname}/{wname}: encoding '{enc_key}' displayName = fieldName '{dn}' — should be human-readable")

# Validar dataset displayNames
for ds in dashboard.get('datasets', []):
    dn = ds.get('displayName', '')
    name = ds.get('name', '')
    if dn == name:
        naming_warnings.append(f"Dataset '{name}': displayName = name — should be human-readable")

print(f"Warnings de naming: {len(naming_warnings)}")
for warn in naming_warnings:
    print(f"  ⚠ {warn}")

if not naming_warnings:
    print("  ✓ Todos los nombres son legibles")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Resumen y guardar

# COMMAND ----------

# Stubs por si la celda de validación SQL fue removida del notebook
sql_errors = locals().get('sql_errors', [])
sql_ok = locals().get('sql_ok', 0)

has_sql_errors = len(sql_errors) > 0
has_fixes = len(fixes) > 0
has_naming = len(naming_warnings) > 0

print(f"{'='*60}")
print(f"REFINAMIENTO DEL DASHBOARD")
print(f"{'='*60}")
print(f"\nDashboard: {DASHBOARD_PATH}")
print(f"SQL queries:  {sql_ok} OK, {len(sql_errors)} errores")
print(f"Widget fixes: {len(fixes)} correcciones aplicadas")
print(f"Naming:       {len(naming_warnings)} warnings")

if has_sql_errors:
    print(f"\n⚠ Hay {len(sql_errors)} queries con error. El dashboard se guardará pero esos widgets no funcionarán.")

if has_fixes:
    print(f"\n✓ Se aplicaron {len(fixes)} correcciones automáticas.")

if not has_fixes and not has_sql_errors and not has_naming:
    print(f"\n✓ Dashboard limpio — no requiere cambios.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Guardar dashboard corregido

# COMMAND ----------

if has_fixes:
    dashboard_json_str = json.dumps(dashboard, indent=2, ensure_ascii=False)
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
        print(f"✓ Dashboard corregido guardado en: {DASHBOARD_PATH}")
    else:
        print(f"✗ Error ({resp.status_code}): {resp.text}")
else:
    print("Sin correcciones — dashboard no modificado.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. Detalle por widget

# COMMAND ----------

import pandas as pd

widget_summary = []
for page in dashboard.get('pages', []):
    pname = page.get('displayName', 'unnamed')
    for layout in page.get('layout', []):
        w = layout.get('widget', {})
        spec = w.get('spec', {})
        wtype = spec.get('widgetType', 'text' if 'multilineTextboxSpec' in w else '?')
        title = spec.get('frame', {}).get('title', '')
        pos = layout.get('position', {})

        widget_summary.append({
            'page': pname,
            'type': wtype,
            'title': title or w.get('name', ''),
            'x': pos.get('x', ''),
            'y': pos.get('y', ''),
            'w': pos.get('width', ''),
            'h': pos.get('height', ''),
        })

display(pd.DataFrame(widget_summary))
