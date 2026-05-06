# Databricks notebook source
# MAGIC %md
# MAGIC # Crear Vistas de Dashboard
# MAGIC
# MAGIC Lee las Metrics Views existentes (`mv_*`) y la tabla `pbi_measures` para generar
# MAGIC vistas SQL que alimentarán los dashboards de Databricks.
# MAGIC
# MAGIC Cada vista incluye todas las dimensiones + `MEASURE()` de cada measure + `GROUP BY ALL`.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Parámetros

# COMMAND ----------

dbutils.widgets.text("catalog", "pbi_migration", "Catálogo")
dbutils.widgets.text("schema", "couch", "Schema")
dbutils.widgets.text("llm_endpoint", "databricks-claude-sonnet-4", "Endpoint LLM")
CATALOG = dbutils.widgets.get("catalog")
SCHEMA = dbutils.widgets.get("schema")
LLM_ENDPOINT = dbutils.widgets.get("llm_endpoint")
print(f"Catálogo: {CATALOG}.{SCHEMA}")
print(f"LLM: {LLM_ENDPOINT}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Descubrir Metrics Views existentes

# COMMAND ----------

spark.sql(f"USE CATALOG {CATALOG}")

# COMMAND ----------

views_df = spark.sql(f"SHOW VIEWS IN {CATALOG}.{SCHEMA} LIKE 'mv_*'").collect()
mv_names = [r.viewName for r in views_df]
print(f"{len(mv_names)} Metrics Views encontradas: {mv_names}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Leer metadatos de Power BI

# COMMAND ----------

pbi_measures = spark.sql(f"SELECT * FROM {CATALOG}.{SCHEMA}.pbi_measures").toPandas()
pbi_filters = spark.sql(f"SELECT * FROM {CATALOG}.{SCHEMA}.pbi_context_filters").toPandas()
pbi_slicers = spark.sql(f"SELECT * FROM {CATALOG}.{SCHEMA}.pbi_page_filters").toPandas()

print(f"Measures: {len(pbi_measures)}")
print(f"Filtros de contexto: {len(pbi_filters)}")
print(f"Slicers de página: {len(pbi_slicers)}")

display(pbi_measures)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Analizar cada Metrics View

# COMMAND ----------

import re

mv_info = {}
for mv_name in mv_names:
    full_name = f"{CATALOG}.{SCHEMA}.{mv_name}"
    cols = spark.sql(f"DESCRIBE {full_name}").collect()

    dimensions = []
    measures = []
    for c in cols:
        col_name = c.col_name
        data_type = c.data_type or ""
        comment = c.comment or ""
        if col_name.startswith('#') or not col_name.strip():
            continue
        if 'measure' in data_type:
            measures.append({'name': col_name, 'type': data_type, 'comment': comment})
        else:
            dimensions.append({'name': col_name, 'type': data_type, 'comment': comment})

    mv_info[mv_name] = {
        'full_name': full_name,
        'dimensions': dimensions,
        'measures': measures,
    }
    print(f"\n{mv_name}: {len(dimensions)} dimensiones, {len(measures)} measures")
    for d in dimensions:
        print(f"  dim: {d['name']} ({d['type']})")
    for m in measures:
        print(f"  measure: {m['name']} ({m['comment'][:60]})")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4b. call_claude

# COMMAND ----------

import requests

def call_claude(prompt, system_prompt="You are an expert in Databricks SQL.", max_tokens=4000):
    token = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().get()
    host = spark.conf.get("spark.databricks.workspaceUrl")
    url = f"https://{host}/serving-endpoints/{LLM_ENDPOINT}/invocations"
    resp = requests.post(url,
        json={
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": 0.1,
        },
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        timeout=120
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"].strip()
    if content.startswith("```"):
        lines = content.split("\n")[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        content = "\n".join(lines)
    return content.strip()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Generar, probar y auto-corregir vistas de dashboard

# COMMAND ----------

import pandas as pd
import time

dashboard_sqls = {}
view_results = []

# --- Ejecutar SQL via SQL Warehouse (evita bug INTERNAL_ERROR_ATTRIBUTE_NOT_FOUND de spark.sql) ---
def run_sql_via_warehouse(sql_statement, timeout_seconds=300):
    """Ejecuta SQL via Statement Execution API usando el SQL Warehouse del workspace."""
    token = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().get()
    host = spark.conf.get("spark.databricks.workspaceUrl")

    # Buscar un warehouse activo o serverless
    wh_resp = requests.get(f"https://{host}/api/2.0/sql/warehouses",
                           headers={"Authorization": f"Bearer {token}"}, timeout=30)
    warehouses = wh_resp.json().get('warehouses', [])
    # Preferir serverless, luego el primero disponible
    wh_id = None
    for w in warehouses:
        if 'serverless' in w.get('name', '').lower() or w.get('warehouse_type') == 'PRO':
            wh_id = w['id']
            break
    if not wh_id and warehouses:
        wh_id = warehouses[0]['id']
    if not wh_id:
        raise Exception("No SQL Warehouse found in workspace")

    # Ejecutar statement
    resp = requests.post(
        f"https://{host}/api/2.0/sql/statements",
        json={"warehouse_id": wh_id, "statement": sql_statement, "wait_timeout": "0s"},
        headers={"Authorization": f"Bearer {token}"}, timeout=30
    )
    stmt = resp.json()
    stmt_id = stmt.get('statement_id')
    state = stmt.get('status', {}).get('state', '')

    # Poll hasta que termine
    start = time.time()
    while state in ('PENDING', 'RUNNING', '') and (time.time() - start) < timeout_seconds:
        time.sleep(2)
        poll = requests.get(
            f"https://{host}/api/2.0/sql/statements/{stmt_id}",
            headers={"Authorization": f"Bearer {token}"}, timeout=30
        ).json()
        state = poll.get('status', {}).get('state', '')
        stmt = poll

    if state == 'SUCCEEDED':
        return True, None
    else:
        err = stmt.get('status', {}).get('error', {}).get('message', f'Unknown error, state={state}')
        return False, err

def needs_cast(d):
    """Determina si una dimension necesita TRY_CAST para evitar CAST_OVERFLOW."""
    dtype = d.get('type', '').upper()
    return any(t in dtype for t in ['BIGINT', 'LONG', 'INT'])

def build_simple_view_sql(full_view, mv_full_name, dims, meass):
    """Genera SQL. Si hay columnas LONG/INT, usa subquery para evitar CAST_OVERFLOW."""
    has_problematic = any(needs_cast(d) for d in dims)

    dim_select = ",\n      ".join(f"`{d['name']}`" for d in dims)
    measure_select = ",\n      ".join(
        f"TRY_CAST(MEASURE(`{m['name']}`) AS DOUBLE) as `{m['name']}`" for m in meass
    )
    group_by = ",\n      ".join(f"`{d['name']}`" for d in dims)

    if not has_problematic:
        return f"""CREATE OR REPLACE VIEW {full_view} AS
  SELECT
      {dim_select},
      {measure_select}
  FROM {mv_full_name}
  GROUP BY
      {group_by}"""
    else:
        # Subquery: agregar primero (columnas originales), castear despues
        outer_dims = ",\n    ".join(
            f"TRY_CAST(`{d['name']}` AS STRING) as `{d['name']}`" if needs_cast(d)
            else f"`{d['name']}`"
            for d in dims
        )
        outer_measures = ",\n    ".join(f"`{m['name']}`" for m in meass)
        return f"""CREATE OR REPLACE VIEW {full_view} AS
  SELECT
    {outer_dims},
    {outer_measures}
  FROM (
    SELECT
      {dim_select},
      {measure_select}
    FROM {mv_full_name}
    GROUP BY
      {group_by}
  )"""

def build_batched_view_sql(full_view, mv_full_name, dims, meass, batch_size):
    """Genera SQL dividiendo measures en sub-vistas y uniendo con JOIN."""
    dim_names = [d['name'] for d in dims]
    dim_select = ", ".join(dim_expression(d) for d in dims)
    group_by = ",\n    ".join(f"`{d}`" for d in dim_names)

    # Dividir measures en batches
    batches = []
    for i in range(0, len(meass), batch_size):
        batches.append(meass[i:i + batch_size])

    print(f"  Dividiendo {len(meass)} measures en {len(batches)} batches de ~{batch_size}")

    # Crear sub-vista por cada batch
    sub_view_names = []
    for idx, batch in enumerate(batches):
        sub_view = f"{full_view}__part{idx}"
        sub_view_names.append(sub_view)
        measure_select = ",\n    ".join(
            f"TRY_CAST(MEASURE(`{m['name']}`) AS DOUBLE) as `{m['name']}`" for m in batch
        )
        sub_sql = f"""CREATE OR REPLACE VIEW {sub_view} AS
  SELECT
    {dim_select},
    {measure_select}
  FROM {mv_full_name}
  GROUP BY
    {group_by}"""
        print(f"  Sub-vista {idx}: {sub_view} ({len(batch)} measures)")
        spark.sql(sub_sql)
        # Verificar que funciona
        spark.sql(f"SELECT * FROM {sub_view} LIMIT 1").collect()
        print(f"    OK")

    # Construir la vista final con JOIN de todas las sub-vistas
    join_conditions = " AND ".join(
        f"COALESCE(CAST(p0.`{d}` AS STRING), '___NULL___') = COALESCE(CAST(p{idx}.`{d}` AS STRING), '___NULL___')"
        for d in dim_names
        for idx in range(1, len(sub_view_names))
        if idx > 0  # solo para p1, p2, etc.
    )
    # Reconstruir join_conditions correctamente: para cada sub-vista > 0, join con p0
    joins = ""
    for idx in range(1, len(sub_view_names)):
        conds = " AND ".join(
            f"COALESCE(CAST(p0.`{d}` AS STRING), '___NULL___') = COALESCE(CAST(p{idx}.`{d}` AS STRING), '___NULL___')"
            for d in dim_names
        )
        joins += f"\n  FULL OUTER JOIN {sub_view_names[idx]} p{idx} ON {conds}"

    # SELECT: dimensiones de p0, measures de cada sub-vista
    final_dims = ", ".join(f"p0.`{d}`" for d in dim_names)
    final_measures = []
    for idx, batch in enumerate(batches):
        for m in batch:
            final_measures.append(f"p{idx}.`{m['name']}`")
    final_measures_str = ",\n    ".join(final_measures)

    final_sql = f"""CREATE OR REPLACE VIEW {full_view} AS
  SELECT
    {final_dims},
    {final_measures_str}
  FROM {sub_view_names[0]} p0{joins}"""

    return final_sql

for mv_name, info in mv_info.items():
    view_name = mv_name.replace('mv_', 'v_dashboard_')
    full_view = f"{CATALOG}.{SCHEMA}.{view_name}"

    dims = info['dimensions']
    meass = info['measures']

    print(f"\n{'='*60}")
    print(f"{full_view} ({len(dims)} dims, {len(meass)} measures)")
    print(f"{'='*60}")

    # Generar SQL deterministicamente
    sql = build_simple_view_sql(full_view, info['full_name'], dims, meass)

    # Ejecutar via SQL Warehouse (evita bug INTERNAL_ERROR_ATTRIBUTE_NOT_FOUND de spark.sql)
    print(f"  Creando vista via SQL Warehouse...")
    ok, err = run_sql_via_warehouse(sql)
    if ok:
        # Verificar con SELECT
        ok2, err2 = run_sql_via_warehouse(f"SELECT * FROM {full_view} LIMIT 1")
        if ok2:
            print(f"  OK")
            dashboard_sqls[full_view] = sql
            view_results.append({'vista_dashboard': full_view, 'metric_view': info['full_name'], 'status': 'OK', 'error': ''})
        else:
            print(f"  ⚠ WARN: Vista creada pero SELECT fallo: {err2[:200]}")
            dashboard_sqls[full_view] = sql
            view_results.append({'vista_dashboard': full_view, 'metric_view': info['full_name'], 'status': 'WARN', 'error': err2[:300]})
    else:
        print(f"  FAIL: {err[:300]}")
        view_results.append({'vista_dashboard': full_view, 'metric_view': info['full_name'], 'status': 'FAIL', 'error': err[:300]})

# --- Resumen ---
ok_views = [v for v in view_results if v['status'] == 'OK']
warn_views = [v for v in view_results if v['status'] == 'WARN']
fail_views = [v for v in view_results if v['status'] == 'FAIL']

print(f"\n{'='*60}")
print(f"RESUMEN DE VISTAS")
print(f"{'='*60}")
print(f"  OK:   {len(ok_views)}")
print(f"  WARN: {len(warn_views)} (vista creada, SELECT fallo)")
print(f"  FAIL: {len(fail_views)} (no se pudo crear)")

if warn_views:
    print(f"\n⚠ WARN — Vistas con problemas en SELECT (revisar Metric View):")
    for v in warn_views:
        print(f"  - {v['vista_dashboard']}")
        print(f"    MV: {v['metric_view']}")

if fail_views:
    print(f"\n✗ FAIL — Vistas que no se pudieron crear:")
    for v in fail_views:
        print(f"  - {v['vista_dashboard']}")
        print(f"    Error: {v.get('error', '?')[:200]}")

if ok_views:
    print(f"\n✓ OK — Vistas creadas correctamente:")
    for v in ok_views:
        print(f"  - {v['vista_dashboard']}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Guardar los SQLs generados

# COMMAND ----------

sql_rows = []
for view_name, sql in dashboard_sqls.items():
    mv_name = view_name.replace('v_dashboard_', 'mv_').replace(f'{CATALOG}.{SCHEMA}.', '')
    info = mv_info.get(mv_name, {})
    dims = [d['name'] for d in info.get('dimensions', [])]
    meass = [m['name'] for m in info.get('measures', [])]

    sql_rows.append({
        'vista_dashboard': view_name,
        'metric_view': info.get('full_name', ''),
        'num_dimensiones': len(dims),
        'dimensiones': ', '.join(dims),
        'num_measures': len(meass),
        'measures': ', '.join(meass),
        'sql': sql,
    })

sql_df = pd.DataFrame(sql_rows)
spark.createDataFrame(sql_df).write.mode("overwrite").saveAsTable(f"{CATALOG}.{SCHEMA}.dashboard_view_sqls")

ok_count = sum(1 for r in view_results if r['status'] == 'OK')
fail_count = sum(1 for r in view_results if r['status'] == 'FAIL')
print(f"Guardado en {CATALOG}.{SCHEMA}.dashboard_view_sqls ({len(sql_rows)} filas)")
print(f"  OK: {ok_count} | FAIL: {fail_count}")
display(sql_df)
