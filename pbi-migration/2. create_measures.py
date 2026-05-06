# Databricks notebook source
# MAGIC %md
# MAGIC # 2. Crear measures en las Metric Views
# MAGIC
# MAGIC Lee las Metric Views base del notebook 1 (que ya incluyen vistas LOD pre-calculadas) y para cada una:
# MAGIC 1. Pide a Claude que traduzca cada DAX a SQL (JSON)
# MAGIC 2. Inserta measures una a una al YAML y valida
# MAGIC 3. Segunda pasada: measures compuestas que referencian otras measures

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Parametros

# COMMAND ----------

import pandas as pd
import json, re, requests, sys
from collections import defaultdict

dbutils.widgets.text("catalog", "pbi_migration", "Catalogo destino")
dbutils.widgets.text("schema", "couch", "Schema destino")
dbutils.widgets.text("module_path", "/Workspace/Users/<your-email>@databricks.com/powerbi-model-analyzer", "Path modulos")
dbutils.widgets.text("llm_endpoint", "databricks-claude-sonnet-4", "Endpoint LLM")

CATALOG = dbutils.widgets.get("catalog")
SCHEMA = dbutils.widgets.get("schema")
MODULE_PATH = dbutils.widgets.get("module_path")
LLM_ENDPOINT = dbutils.widgets.get("llm_endpoint")

print(f"Destino: {CATALOG}.{SCHEMA}")
print(f"LLM: {LLM_ENDPOINT}")

# --- Helper: test de ejecucion real de una measure via SQL Warehouse ---
import time as _time

def _test_measure_execution(view_name, measure_name):
    """Ejecuta SELECT MEASURE(name) FROM mv GROUP BY first_dim LIMIT 1 via SQL Warehouse.
    Retorna (ok, error_msg). Detecta errores de runtime como CAST_OVERFLOW."""
    token = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().get()
    host = spark.conf.get("spark.databricks.workspaceUrl")

    # Buscar warehouse
    wh_resp = requests.get(f"https://{host}/api/2.0/sql/warehouses",
                           headers={"Authorization": f"Bearer {token}"}, timeout=30)
    warehouses = wh_resp.json().get('warehouses', [])
    wh_id = None
    for w in warehouses:
        if 'serverless' in w.get('name', '').lower() or w.get('warehouse_type') == 'PRO':
            wh_id = w['id']
            break
    if not wh_id and warehouses:
        wh_id = warehouses[0]['id']
    if not wh_id:
        return True, None  # Sin warehouse, skip el test

    # Obtener primera dimension de la vista
    desc_resp = requests.post(
        f"https://{host}/api/2.0/sql/statements",
        json={"warehouse_id": wh_id, "statement": f"DESCRIBE {view_name}", "wait_timeout": "30s"},
        headers={"Authorization": f"Bearer {token}"}, timeout=60
    )
    desc = desc_resp.json()
    first_dim = None
    if desc.get('status', {}).get('state') == 'SUCCEEDED':
        for row in desc.get('result', {}).get('data_array', []):
            col_name, col_type = row[0], row[1] if len(row) > 1 else ''
            if col_name and not col_name.startswith('#') and 'measure' not in col_type.lower():
                first_dim = col_name
                break

    if not first_dim:
        return True, None  # No pudo obtener dimension, skip

    # Ejecutar SELECT MEASURE
    test_sql = f"SELECT `{first_dim}`, TRY_CAST(MEASURE(`{measure_name}`) AS DOUBLE) FROM {view_name} GROUP BY `{first_dim}` LIMIT 1"
    resp = requests.post(
        f"https://{host}/api/2.0/sql/statements",
        json={"warehouse_id": wh_id, "statement": test_sql, "wait_timeout": "0s"},
        headers={"Authorization": f"Bearer {token}"}, timeout=30
    )
    stmt = resp.json()
    stmt_id = stmt.get('statement_id', '')
    state = stmt.get('status', {}).get('state', '')

    start = _time.time()
    while state in ('PENDING', 'RUNNING', '') and (_time.time() - start) < 60:
        _time.sleep(2)
        poll = requests.get(
            f"https://{host}/api/2.0/sql/statements/{stmt_id}",
            headers={"Authorization": f"Bearer {token}"}, timeout=30
        ).json()
        state = poll.get('status', {}).get('state', '')
        stmt = poll

    if state == 'SUCCEEDED':
        return True, None
    else:
        err = stmt.get('status', {}).get('error', {}).get('message', f'state={state}')
        return False, err

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Leer Metric Views base y measures pendientes

# COMMAND ----------

# Measures con DAX completo
measures_df = spark.sql(f"SELECT * FROM {CATALOG}.{SCHEMA}.pbi_measures").toPandas()
print(f"{len(measures_df)} measures totales")

# Descubrir Metric Views base (creadas por notebook 1)
# Usamos la API de Unity Catalog porque SHOW CREATE TABLE no funciona con Metric Views
mv_views = {}
tables_in_catalog = spark.sql(f"SHOW TABLES IN {CATALOG}.{SCHEMA}").collect()

token = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().get()
host = spark.conf.get("spark.databricks.workspaceUrl")

for r in tables_in_catalog:
    tname = r.tableName
    if tname.startswith("mv_"):
        view_name = f"{CATALOG}.{SCHEMA}.{tname}"
        try:
            resp = requests.get(
                f"https://{host}/api/2.1/unity-catalog/tables/{view_name}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=30
            )
            resp.raise_for_status()
            table_info = resp.json()
            yaml_text = table_info.get("view_definition", "")
            if yaml_text:
                base_table = tname[3:]  # quitar "mv_"
                mv_views[base_table] = {
                    'yaml': yaml_text,
                    'view_name': view_name,
                }
                print(f"  {view_name} ({len(yaml_text)} chars)")
            else:
                print(f"  {view_name}: sin view_definition")
        except Exception as e:
            print(f"  Error leyendo {view_name}: {str(e)[:100]}")

print(f"\n{len(mv_views)} Metric Views base encontradas")

# Tablas de datos en UC
existing_tables = {}
existing_table_types = {}
for r in tables_in_catalog:
    tname = r.tableName
    if tname.startswith("pbi_") or tname.startswith("mv_"):
        continue
    try:
        cols = spark.sql(f"DESCRIBE {CATALOG}.{SCHEMA}.{tname}").collect()
        existing_tables[tname] = [c.col_name for c in cols if not c.col_name.startswith('#')]
        existing_table_types[tname] = {c.col_name: c.data_type for c in cols if not c.col_name.startswith('#')}
    except:
        print(f"Error leyendo {CATALOG}.{SCHEMA}.{tname}")

# Relaciones
try:
    rels_df = spark.sql(f"SELECT * FROM {CATALOG}.{SCHEMA}.pbi_relationships").toPandas()
except:
    rels_df = pd.DataFrame()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Agrupar measures por view

# COMMAND ----------

def detect_base_table(dax_expression, measure_table):
    if not dax_expression:
        return None
    agg_patterns = [
        r"COUNTROWS\(\s*'?([^')]+)'?\s*\)",
        r"(?:COUNT|SUM|AVERAGE|MIN|MAX|DISTINCTCOUNT)\(\s*'?([^')\[]+)'?\[",
    ]
    general_patterns = [
        r"SELECTEDVALUE\(\s*'?([^')\[]+)'?\[",
        r"FILTER\(\s*'?([^'),]+)'?",
        r"VALUES\(\s*'?([^')\[]+)'?\[",
        r"'([^']+)'\[",
    ]
    excluded = {measure_table.lower(), 'true', 'false', 'blank'}
    agg_tables = set()
    all_tables = set()
    for pattern in agg_patterns:
        for m in re.finditer(pattern, dax_expression, re.IGNORECASE):
            t = (m.group(1) or m.group(2) if m.lastindex > 1 else m.group(1)).strip()
            if t.lower() not in excluded:
                agg_tables.add(t)
                all_tables.add(t)
    for pattern in general_patterns:
        for m in re.finditer(pattern, dax_expression, re.IGNORECASE):
            t = m.group(1).strip()
            if t.lower() not in excluded:
                all_tables.add(t)
    return list(agg_tables)[0] if agg_tables else (list(all_tables)[0] if all_tables else None)


def _find_all_table_refs(dax, measure_table):
    if not dax:
        return []
    patterns = [
        r"COUNTROWS\(\s*'?([^')]+)'?\s*\)",
        r"(?:COUNT|SUM|AVERAGE|MIN|MAX|DISTINCTCOUNT)\(\s*'?([^')\[]+)'?\[",
        r"SELECTEDVALUE\(\s*'?([^')\[]+)'?\[",
        r"FILTER\(\s*'?([^'),]+)'?",
        r"VALUES\(\s*'?([^')\[]+)'?\[",
        r"ALL\(\s*'?([^')]+)'?\s*\)",
        r"ALLEXCEPT\(\s*'?([^'),]+)'?",
        r"'([^']+)'\[",
    ]
    excluded = {measure_table.lower(), 'true', 'false', 'blank'}
    tables = []
    for pattern in patterns:
        for m in re.finditer(pattern, dax, re.IGNORECASE):
            for g in range(1, m.lastindex + 1 if m.lastindex else 2):
                try:
                    t = m.group(g)
                    if t and t.strip().lower() not in excluded and not any(c in t for c in '()=<>'):
                        tables.append(t.strip())
                except:
                    pass
    return tables


def _match_to_uc_table(table_name, existing_tables):
    normalized = table_name.lower().replace(' ', '_').replace("'", "")
    if normalized in existing_tables:
        return normalized
    for tname in existing_tables:
        if normalized.replace('_', '') == tname.replace('_', ''):
            return tname
        if normalized.replace('_', '') in tname.replace('_', '') or tname.replace('_', '') in normalized.replace('_', ''):
            return tname
    return None


# Agrupar measures por su view destino
measures_by_view = defaultdict(list)
unassigned = []

for _, row in measures_df.iterrows():
    name = row.get("Measure", "")
    table = row.get("Tabla", "")
    dax = str(row.get("DAX", ""))

    # Detectar tabla base
    base = detect_base_table(dax, table)
    if base:
        base_normalized = base.lower().replace(' ', '_').replace("'", "")
        matched = _match_to_uc_table(base, existing_tables) or base_normalized
    else:
        # Fallback + reasignacion
        base_normalized = table.lower().replace(' ', '_').replace("'", "") if table else None
        matched = None
        if base_normalized:
            matched = _match_to_uc_table(table, existing_tables)
            if not matched:
                for dt in _find_all_table_refs(dax, table):
                    matched = _match_to_uc_table(dt, existing_tables)
                    if matched:
                        break
        if not matched:
            matched = base_normalized

    # Buscar en que view cae
    if matched and matched in mv_views:
        measures_by_view[matched].append({'measure_name': name, 'table': table, 'dax': dax})
    else:
        unassigned.append({'measure_name': name, 'table': table, 'target': matched})

print(f"Measures asignadas a views:")
for vname, mlist in measures_by_view.items():
    print(f"  {vname}: {len(mlist)} measures")
if unassigned:
    print(f"\nSin view: {len(unassigned)}")
    for u in unassigned:
        print(f"  {u['measure_name']} (tabla: {u['table']}, target: {u['target']})")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Importar docs y construir system prompt

# COMMAND ----------

sys.path.insert(0, MODULE_PATH)
from metrics_view_docs import METRICS_VIEW_DOCS
from dax_function_reference import get_relevant_dax_docs

DAX_DOCS = get_relevant_dax_docs(measures_df)
print(f"DAX docs: {len(DAX_DOCS)} chars")

SYSTEM_PROMPT = f"""You are an expert in converting Power BI DAX measures to Databricks SQL expressions for Metrics Views.

{METRICS_VIEW_DOCS}

{DAX_DOCS}

GENERAL RULES:
- Use MEASURE() for composed measures that reference other measures
- Use scalar subqueries for ALL(table) patterns
- Use window specs for ALL(column) patterns
- Output ONLY valid JSON — no markdown fences, no explanations
"""

def call_claude(prompt, system_prompt=None, max_tokens=4000):
    if system_prompt is None:
        system_prompt = SYSTEM_PROMPT
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
# MAGIC ## 5. Helpers

# COMMAND ----------

def _yaml_quote(value):
    """Quote a YAML string value safely."""
    if value is None:
        return '""'
    value = str(value)
    value = value.replace('\\', '\\\\').replace('"', '\\"')
    value = value.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
    while '  ' in value:
        value = value.replace('  ', ' ')
    return f'"{value.strip()}"'


def _validate_sql_against_dax(sql_expr, dax_expr):
    """Return list of literal values in sql_expr that DO NOT appear in dax_expr.

    These are likely LLM hallucinations (invented filters/values). Caller decides
    whether to flag, re-prompt, or fail.
    """
    if not sql_expr or not dax_expr:
        return []
    suspicious = []
    dax_lower = str(dax_expr).lower()

    # String literals in SQL: 'value'
    for lit in re.findall(r"'([^']{1,120})'", str(sql_expr)):
        if not lit.strip():
            continue
        if lit.lower() not in dax_lower:
            suspicious.append({"value": lit, "type": "string"})

    # Numeric comparisons in SQL: = 0, > 100, etc. (excluding Y/M/D in dates)
    for m in re.finditer(r"(?:=|<>|!=|>|<|>=|<=)\s*(-?\d+(?:\.\d+)?)\b", str(sql_expr)):
        lit = m.group(1)
        # Buscar el número en DAX (con variaciones tipo 0, 0L, 0.0)
        patterns = [rf"\b{re.escape(lit)}L?\b", rf"\b{re.escape(lit)}\.0+\b"]
        if not any(re.search(p, dax_lower) for p in patterns):
            suspicious.append({"value": lit, "type": "numeric"})

    return suspicious


def _build_measure_yaml(m):
    """Build YAML lines for a single measure from Claude's JSON."""
    lines = []
    lines.append(f"  - name: {m['name']}")
    lines.append(f"    expr: {_yaml_quote(m['sql_expr'])}")
    if m.get("display_name"):
        lines.append(f"    display_name: {_yaml_quote(m['display_name'])}")
    if m.get("comment"):
        lines.append(f"    comment: {_yaml_quote(m['comment'])}")
    # format: pass through Claude's object as-is
    fmt = m.get("format")
    if fmt and isinstance(fmt, dict) and fmt.get("type"):
        lines.append("    format:")
        for fk, fv in fmt.items():
            if fv is None:
                continue
            if isinstance(fv, dict):
                lines.append(f"      {fk}:")
                for sk, sv in fv.items():
                    lines.append(f"        {sk}: {sv}")
            else:
                lines.append(f"      {fk}: {fv}")
    # window: pass through Claude's list as-is
    window = m.get("window")
    if window and isinstance(window, list) and len(window) > 0:
        lines.append("    window:")
        for w in window:
            if isinstance(w, dict) and w.get("order"):
                parts = [f"{k}: {v}" for k, v in w.items() if v is not None]
                lines.append(f"      - {{{', '.join(parts)}}}")
    return "\n".join(lines)


def _build_bare_measure_yaml(name, expr, display_name=None):
    """Build minimal YAML for a measure (no format/window)."""
    lines = [f"  - name: {name}", f"    expr: {_yaml_quote(expr)}"]
    if display_name:
        lines.append(f"    display_name: {_yaml_quote(display_name)}")
    return "\n".join(lines)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Traducir DAX a SQL y crear measures una a una

# COMMAND ----------

MAX_FIX_RETRIES = 3
all_results = []

for base_table, mlist in measures_by_view.items():
    info = mv_views[base_table]
    view_name = info['view_name']
    current_yaml = info['yaml']
    catalog_table = base_table

    # Columnas de la tabla source
    cols = existing_tables.get(catalog_table, [])
    col_types = existing_table_types.get(catalog_table, {})
    cols_detail = "\n".join(f"  - {c}: {col_types.get(c, 'unknown')}" for c in cols)

    # Tablas relacionadas
    related_tables_cols = ""
    base_orig = mlist[0].get('table', '') if mlist else ''
    related_table_names = set()
    if hasattr(rels_df, 'iterrows'):
        for _, rel in rels_df.iterrows():
            from_t = str(rel.get('FromTableName', ''))
            to_t = str(rel.get('ToTableName', ''))
            if from_t == base_orig:
                related_table_names.add(to_t)
            elif to_t == base_orig:
                related_table_names.add(from_t)
    for rt in related_table_names:
        rt_match = _match_to_uc_table(rt, existing_tables)
        if rt_match:
            rt_cols = existing_tables.get(rt_match, [])
            rt_types = existing_table_types.get(rt_match, {})
            related_tables_cols += f"\n\nRelated: {CATALOG}.{SCHEMA}.{rt_match} (PBI: '{rt}')"
            for c in rt_cols:
                related_tables_cols += f"\n  - {c}: {rt_types.get(c, 'unknown')}"

    # Quitar TODA la seccion measures del YAML base (incluyendo __row_count y cualquier otra)
    # Asi empezamos limpio — solo source + joins + dimensions
    clean_lines = []
    in_measures = False
    for line in current_yaml.split('\n'):
        stripped = line.strip()
        if stripped == 'measures:' or stripped.startswith('measures:'):
            in_measures = True
            continue
        if in_measures:
            # Seguir saltando mientras estemos en contenido indentado de measures
            # Una linea no-vacia sin indentacion marca el inicio de otra seccion top-level
            if stripped == '' or line.startswith('  ') or line.startswith('\t'):
                continue
            else:
                in_measures = False
        clean_lines.append(line)
    current_yaml = '\n'.join(clean_lines).rstrip() + '\n'

    # Extraer TODOS los nombres existentes (dimensions + measures residuales) para colisiones
    existing_names = set()
    for line in current_yaml.split('\n'):
        stripped = line.strip()
        if stripped.startswith('- name:'):
            existing_names.add(stripped.replace('- name:', '').strip().strip("'\""))

    # Extraer dimensions del YAML para pasarlas al prompt
    yaml_dimensions = []
    in_dims = False
    current_dim = {}
    for line in current_yaml.split('\n'):
        stripped = line.strip()
        if stripped == 'dimensions:' or stripped.startswith('dimensions:'):
            in_dims = True
            continue
        if in_dims:
            if stripped.startswith('- name:'):
                if current_dim:
                    yaml_dimensions.append(current_dim)
                current_dim = {'name': stripped.replace('- name:', '').strip().strip("'\""), 'expr': ''}
            elif stripped.startswith('expr:') and current_dim:
                current_dim['expr'] = stripped.replace('expr:', '').strip().strip("'\"")
            elif stripped and not line.startswith(' ') and not line.startswith('\t') and ':' in stripped:
                if current_dim:
                    yaml_dimensions.append(current_dim)
                    current_dim = {}
                in_dims = False
    if current_dim:
        yaml_dimensions.append(current_dim)

    dimensions_list = "\n".join(f"  - {d['name']}: {d['expr']}" for d in yaml_dimensions if d.get('name'))

    # Detect current source
    current_source_lines = []
    in_src = False
    for sl in current_yaml.split('\n'):
        if sl.strip().startswith('source:'):
            src_value = sl.split('source:', 1)[1].strip()
            if src_value in ('|', '>'):
                in_src = True
            else:
                current_source_lines.append(src_value)
            continue
        if in_src:
            if sl.startswith('  '):
                current_source_lines.append(sl.strip())
            else:
                in_src = False
    current_source = ' '.join(current_source_lines).strip() or f"{CATALOG}.{SCHEMA}.{catalog_table}"

    print(f"\n{'='*60}")
    print(f"{view_name}: {len(mlist)} measures, una a una")
    print(f"  Dimensions en YAML: {len(yaml_dimensions)}")
    print(f"  Nombres existentes: {len(existing_names)}")
    print(f"{'='*60}")

    accepted = []
    skipped = []
    skipped_runtime = []

    for m_idx, m in enumerate(mlist):
        measure_name = m['measure_name']
        dax = m['dax']

        print(f"\n  [{m_idx+1}/{len(mlist)}] {measure_name}")

        translate_prompt = f"""Convert this single DAX measure to a SQL expression for a Databricks Metrics View.

RESPONSE FORMAT — return ONE of these JSON structures:

Option A — Regular measure:
{{"name": "snake_case_name", "sql_expr": "SQL expression", "display_name": "Human Name", "comment": "Original DAX: ...", "format": {{"type": "number"}} or null, "window": [{{"order": "dim", "range": "all", "semiadditive": "last"}}] or null}}

Skip (ONLY if genuinely impossible):
{{"skip": true, "reason": "explanation"}}

Format rules:
- number: {{"type": "number"}} or {{"type": "number", "decimal_places": {{"type": "exact", "places": 2}}}}
- percentage: {{"type": "percentage"}}
- currency: {{"type": "currency", "currency_code": "MXN"}}
- null if no formatting

Current source: {current_source}
Source table: {CATALOG}.{SCHEMA}.{catalog_table}
Source columns:
{cols_detail}
{related_tables_cols}

Dimensions ALREADY AVAILABLE in this Metric View (use directly in expressions):
{dimensions_list}

Measures already in this view (use MEASURE(name) to reference):
{json.dumps(accepted)}

Measure to convert:
  Name: {measure_name}
  DAX: {dax}

AVAILABLE BUILDING BLOCKS — use these to construct the SQL expression:
1. Source columns — must be inside an aggregate: SUM, COUNT, MAX, MIN, AVG, ANY_VALUE
2. Dimensions listed above — pre-computed and available directly. Some are Fixed LOD columns (window functions computed in the source). Use ANY_VALUE(dim_name) to reference them in measures.
3. Existing measures — reference with MEASURE(name)
4. Window measures — for Coarser LOD patterns (grand totals, percent-of-total, running totals, period-over-period, YTD, semiadditive). Use the window field as documented in sections 8, 9, and 13b of the Metric View docs in the system prompt.

CRITICAL: SQL window functions (ANY function with OVER clause) are NOT allowed in measure expr.
For ANY pattern that would need a window function, you have TWO alternatives:
- Fixed LOD: the dimensions listed above already include pre-computed window results. Find the matching dimension and use ANY_VALUE(dimension_name).
- Coarser LOD / Window measures: use the "window" field on the measure (order + range + semiadditive, all three required).
Apply the full LOD documentation from the system prompt (sections 8, 9, 13b) — it covers all window patterns including trailing, cumulative, period-over-period, semiadditive, YTD, and multi-dimension exclusion.

NEVER skip a measure because "it needs a window function." There is ALWAYS a Fixed LOD dimension or a Coarser LOD window measure pattern that handles it.

DAX conversion rules:
- DIVIDE(a, b): MEASURE(a) / NULLIF(MEASURE(b), 0)
- CALCULATE(agg, filter): agg FILTER (WHERE condition)
- ALL('Table'): scalar subquery (SELECT agg FROM {CATALOG}.{SCHEMA}.table) or Coarser LOD with window range: all
- Every column MUST be in an aggregation or MEASURE()
- CAST dates: use CAST(x AS DATE) for ADD_MONTHS, DATE_ADD, etc.
- INTERVAL only accepts LITERAL values: INTERVAL '7' DAY is valid, INTERVAL (expression) DAY is NOT. For computed intervals use DATE_SUB(date, n) or DATE_ADD(date, n) where n is an integer expression. Example: instead of "date - INTERVAL (DAYOFWEEK(date) - 2) DAY" write "DATE_SUB(date, DAYOFWEEK(date) - 2)".
- WEEKDAY(date, mode) is not supported in Databricks. Use DAYOFWEEK(date) which returns 1=Sunday..7=Saturday, or EXTRACT(DAYOFWEEK FROM date).
- EOMONTH is not supported. Use LAST_DAY(date) instead.
- HASONEVALUE + SELECTEDVALUE: CASE WHEN COUNT(DISTINCT col) = 1 THEN ANY_VALUE(col) ELSE 'default' END
- ALWAYS attempt to convert. Only skip if there is literally no SQL equivalent AND no matching dimension AND no window measure pattern.

Return ONLY the JSON object. No markdown."""

        try:
            result = call_claude(translate_prompt, max_tokens=2000)
            m_json = json.loads(result) if result.startswith('{') else json.loads(re.search(r'\{.*\}', result, re.DOTALL).group())
        except Exception as e:
            print(f"    x Error parseando JSON: {str(e)[:80]}")
            skipped.append(measure_name)
            all_results.append({"View": view_name, "Original": measure_name, "Measure": measure_name, "Status": "SKIP"})
            continue

        if m_json.get("skip"):
            reason = m_json.get('reason', 'no convertible')
            print(f"    SKIP: {reason}")
            skipped.append(measure_name)
            all_results.append({"View": view_name, "Original": measure_name, "Measure": measure_name, "Status": "SKIP"})
            continue

        # --- Regular measure ---
        mname = m_json.get('name', measure_name.lower().replace(' ', '_'))
        current_expr = m_json.get('sql_expr', '')

        # Colision con dimension o measure existente
        if mname in existing_names or mname in accepted:
            mname = f"m_{mname}"
            # Si sigue colisionando, agregar sufijo numerico
            if mname in existing_names or mname in accepted:
                mname = f"{mname}_{m_idx}"

        # --- Insertar en YAML y validar ---
        success = False
        for attempt in range(MAX_FIX_RETRIES + 1):
            if attempt == 0:
                block = _build_measure_yaml({**m_json, 'name': mname})
            else:
                block = _build_bare_measure_yaml(mname, current_expr, m_json.get('display_name'))

            if "measures:" not in current_yaml:
                test_yaml = current_yaml.rstrip() + "\nmeasures:\n" + block + "\n"
            else:
                test_yaml = current_yaml.rstrip() + "\n" + block + "\n"

            try:
                spark.sql(f"""CREATE OR REPLACE VIEW {view_name} WITH METRICS LANGUAGE YAML AS $$\n{test_yaml}\n$$""")
                # Test de ejecucion real via SQL Warehouse
                exec_ok, exec_err = _test_measure_execution(view_name, mname)
                if not exec_ok:
                    print(f"    x RUNTIME {mname}: {exec_err[:150]}")
                    # Revertir: volver al YAML sin esta measure
                    spark.sql(f"""CREATE OR REPLACE VIEW {view_name} WITH METRICS LANGUAGE YAML AS $$\n{current_yaml}\n$$""")
                    skipped_runtime.append({'measure': mname, 'view': view_name, 'error': exec_err[:200]})
                    success = False
                    break
                success = True
                current_yaml = test_yaml
                accepted.append(mname)
                print(f"    OK {mname}" + (f" (fix {attempt})" if attempt > 0 else ""))
                break
            except Exception as e:
                last_error = str(e)[:500]
                print(f"    x intento {attempt+1}: {last_error[:200]}")

                if attempt >= MAX_FIX_RETRIES:
                    break

                # Error de nombre duplicado → renombrar sin gastar llamada a Claude
                if 'names must be unique' in last_error:
                    mname = f"measure_{mname}" if not mname.startswith("measure_") else f"{mname}_{attempt}"
                    print(f"    -> renombrando a: {mname}")
                    continue

                # Pedir fix regular a Claude
                is_last_attempt = (attempt >= MAX_FIX_RETRIES - 1)
                fix_prompt = f"""Fix this SQL expression for a Databricks Metrics View measure. This is attempt {attempt+1} of {MAX_FIX_RETRIES+1}.

Measure: {mname}
Expr: {current_expr}
Error: {last_error}

Dimensions AVAILABLE in this Metric View (use these names, NOT raw table.column):
{dimensions_list}

Existing measures (reference with MEASURE(name)):
{json.dumps(accepted)}

Source table columns:
{cols}

RULES:
- For UNRESOLVED_COLUMN: the column might exist as a DIMENSION above (possibly with a join prefix like joinname_column). Search the dimensions list. Or it might be a MEASURE — check the measures list.
- For METRIC_VIEW_WINDOW_FUNCTION_NOT_SUPPORTED: window functions are NOT allowed in measures. Use ANY_VALUE(dimension_name) if there is a pre-computed LOD dimension above, or use the window field (order + range + semiadditive).
- For INVALID_AGGREGATE_FILTER: the FILTER WHERE clause cannot contain aggregates or references to other tables. Use only source columns or dimension names.
- For DATATYPE_MISMATCH: use CAST(x AS DATE) for date functions. If a column is BIGINT and needs to be a date, use DATE_FROM_UNIX_DATE(col) or TO_DATE(CAST(col AS STRING), 'yyyyMMdd').
- For PARSE_SYNTAX_ERROR with INTERVAL: INTERVAL only accepts LITERALS like INTERVAL '7' DAY. For computed intervals use DATE_SUB(date, n) or DATE_ADD(date, n). Example: instead of "date - INTERVAL (expr) DAY" write "DATE_SUB(date, expr)".
- WEEKDAY(date, mode) is not supported. Use DAYOFWEEK(date) (1=Sunday..7=Saturday).
- EOMONTH is not supported. Use LAST_DAY(date).
- NESTED_AGGREGATE_FUNCTION: cannot nest aggregates. Move the inner aggregate to a scalar subquery or use an existing MEASURE().
- TABLE_OR_VIEW_NOT_FOUND: ALWAYS use fully qualified names in subqueries: {CATALOG}.{SCHEMA}.tablename
- Columns from joined tables: FIRST try the dimension name from the list above. If not found, try referencing via the join alias (e.g., joinname.ColumnName). If still not found, try a creative alternative using columns and measures that DO exist.
- {"You may return SKIP only as absolute last resort." if is_last_attempt else "Do NOT return SKIP. Try a different approach — use dimensions, measures, join aliases, or simplify the expression."}

Return ONLY: {{"sql_expr": "fixed expression"}}{' or {{"sql_expr": "SKIP", "reason": "explanation"}}' if is_last_attempt else ''}"""
                try:
                    fix_result = call_claude(fix_prompt, max_tokens=1000)
                    try:
                        fix_json = json.loads(fix_result)
                    except json.JSONDecodeError:
                        match = re.search(r'\{[^{}]*"sql_expr"[^{}]*\}', fix_result, re.DOTALL)
                        if not match:
                            match = re.search(r'\{.*?\}', fix_result, re.DOTALL)
                        fix_json = json.loads(match.group()) if match else {}
                    current_expr = fix_json.get('sql_expr', current_expr)
                    if current_expr == 'SKIP':
                        reason = fix_json.get('reason', 'no expresable')
                        print(f"    -> SKIP: {reason}")
                        break
                    print(f"    -> fix: {current_expr[:80]}")
                except Exception as ce:
                    print(f"    -> error fix: {str(ce)[:80]}")
                    break

        if not success:
            skipped.append({'measure_name': measure_name, 'dax': dax, 'last_error': last_error if 'last_error' in dir() else ''})

        all_results.append({
            "View": view_name,
            "Original": measure_name,
            "Measure": mname if success else measure_name,
            "Status": "OK" if success else "SKIP",
        })

    print(f"\n  === {view_name}: {len(accepted)}/{len(mlist)} OK ===")
    if skipped:
        print(f"  Saltadas (YAML invalido): {len(skipped)}")
        for s in skipped:
            sname = s['measure_name'] if isinstance(s, dict) else s
            print(f"    - {sname}")
    if skipped_runtime:
        print(f"  Saltadas (RUNTIME error): {len(skipped_runtime)}")
        for s in skipped_runtime:
            print(f"    - {s['measure']}: {s['error'][:100]}")

    mv_views[base_table]['yaml'] = current_yaml

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. Segunda pasada: measures compuestas

# COMMAND ----------

# Recolectar measures ya creadas
created_measures = {}  # {measure_name_lower: view_name}
for r in all_results:
    if r['Status'] == 'OK':
        created_measures[r['Measure'].lower()] = r['View']

print(f"Measures creadas: {len(created_measures)}")

# Buscar measures no creadas que referencian measures existentes
composed = []
created_names = set(r['Measure'] for r in all_results)
created_originals = set(r['Original'] for r in all_results if r['Status'] == 'OK')
for _, row in measures_df.iterrows():
    name = row.get("Measure", "")
    dax = str(row.get("DAX", ""))
    m_lower = name.lower().replace(' ', '_').replace("'", "")

    # Skip si ya se creo (por nombre snake_case O por nombre original)
    if name in created_originals:
        continue
    if any(m_lower == cn.lower().replace(' ', '_') for cn in created_names):
        continue

    # Buscar referencias a measures existentes en el DAX
    refs = re.findall(r'\[([^\]]+)\]', dax)
    matched_refs = []
    for ref in refs:
        ref_lower = ref.lower().replace(' ', '_')
        if ref_lower in created_measures:
            matched_refs.append((ref, created_measures[ref_lower]))

    if matched_refs:
        composed.append({
            'measure_name': name,
            'dax': dax,
            'target_view': matched_refs[0][1],
            'references': matched_refs,
        })

print(f"Measures compuestas detectadas: {len(composed)}")

if composed:
    by_view = defaultdict(list)
    for c in composed:
        by_view[c['target_view']].append(c)

    for view_name, comp_measures in by_view.items():
        print(f"\n{'='*60}")
        print(f"{view_name}: {len(comp_measures)} measures compuestas")

        # Measures existentes en la view
        existing_in_view = [r['Measure'] for r in all_results if r['View'] == view_name and r['Status'] == 'OK']

        measures_to_add = ""
        for m in comp_measures:
            measures_to_add += f"\n- {m['measure_name']}: {m['dax'][:200]}"

        compose_prompt = f"""Convert these composed DAX measures to SQL. They reference existing measures.

Return ONLY a JSON array: {{"name": "snake_case", "sql_expr": "MEASURE(existing) / NULLIF(MEASURE(other), 0)", "display_name": "Name", "original_name": "Original PBI Measure Name", "format": null}}

EXISTING MEASURES (use MEASURE(name)):
{json.dumps(existing_in_view)}

NEW MEASURES:
{measures_to_add}

Rules:
- Use MEASURE(name) to reference existing measures
- Skip purely cosmetic measures (FORMAT, colors, icons)
- Return ONLY the JSON array."""

        json_result = call_claude(compose_prompt, max_tokens=4000)
        try:
            new_json = json.loads(json_result)
        except:
            match = re.search(r'\[.*\]', json_result, re.DOTALL)
            new_json = json.loads(match.group()) if match else []

        # Encontrar base_table para esta view
        base_table = None
        for bt, info in mv_views.items():
            if info['view_name'] == view_name:
                base_table = bt
                break

        if not base_table:
            continue

        current_yaml = mv_views[base_table]['yaml']

        # Collect existing names to avoid collisions
        existing_names = set()
        for line in current_yaml.split('\n'):
            stripped = line.strip()
            if stripped.startswith('- name:'):
                existing_names.add(stripped.replace('- name:', '').strip().strip("'\""))

        for m in new_json:
            if m.get("is_dimension", False):
                continue
            mname = m['name']

            # Check for name collision — rename if needed
            if mname in existing_names:
                mname = f"m_{mname}"
            if mname in existing_names:
                mname = f"measure_{m['name']}"

            print(f"  Insertando compuesta: {mname}")

            block = _build_bare_measure_yaml(mname, m['sql_expr'], m.get('display_name'))
            if "measures:" not in current_yaml:
                test_yaml = current_yaml.rstrip() + "\nmeasures:\n" + block + "\n"
            else:
                test_yaml = current_yaml.rstrip() + "\n" + block + "\n"

            try:
                spark.sql(f"""CREATE OR REPLACE VIEW {view_name} WITH METRICS LANGUAGE YAML AS $$\n{test_yaml}\n$$""")
                current_yaml = test_yaml
                existing_names.add(mname)
                orig_name = m.get('original_name', m.get('display_name', mname))
                print(f"    OK")
                all_results.append({"View": view_name, "Original": orig_name, "Measure": mname, "Status": "OK"})
            except Exception as e:
                error_msg = str(e)[:500]
                orig_name = m.get('original_name', m.get('display_name', mname))
                # One more try with more aggressive rename
                if 'names must be unique' in error_msg:
                    mname = f"composed_{m['name']}"
                    block = _build_bare_measure_yaml(mname, m['sql_expr'], m.get('display_name'))
                    test_yaml = current_yaml.rstrip() + "\n" + block + "\n"
                    try:
                        spark.sql(f"""CREATE OR REPLACE VIEW {view_name} WITH METRICS LANGUAGE YAML AS $$\n{test_yaml}\n$$""")
                        current_yaml = test_yaml
                        existing_names.add(mname)
                        print(f"    OK (renamed to {mname})")
                        all_results.append({"View": view_name, "Original": orig_name, "Measure": mname, "Status": "OK"})
                        continue
                    except:
                        pass
                print(f"    x {error_msg[:200]}")
                all_results.append({"View": view_name, "Original": orig_name, "Measure": mname, "Status": "SKIP"})

        mv_views[base_table]['yaml'] = current_yaml

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7b. Tercera pasada: measures fallidas con contexto de dimensions

# COMMAND ----------

# Recolectar measures que aun estan SKIP (no resueltas por la segunda pasada)
already_ok = set(r['Original'] for r in all_results if r['Status'] == 'OK')
failed_measures_by_view = defaultdict(list)
for base_table, info in mv_views.items():
    view_name = info['view_name']
    for r in all_results:
        if r['View'] == view_name and r['Status'] == 'SKIP' and r.get('Original', '') not in already_ok:
            # Buscar el DAX original
            for m in info.get('measures', measures_by_view.get(base_table, [])):
                if isinstance(m, dict) and m.get('measure_name') == r['Measure']:
                    failed_measures_by_view[view_name].append({
                        'measure_name': m['measure_name'],
                        'dax': m['dax'],
                        'base_table': base_table,
                    })
                    break

total_failed = sum(len(v) for v in failed_measures_by_view.values())
print(f"Measures fallidas para tercera pasada: {total_failed}")

if total_failed > 0:
    for view_name, failed_list in failed_measures_by_view.items():
        # Encontrar base_table y current_yaml
        base_table = None
        for bt, info in mv_views.items():
            if info['view_name'] == view_name:
                base_table = bt
                break
        if not base_table:
            continue

        current_yaml = mv_views[base_table]['yaml']

        # Extraer dimensions del YAML actual
        dims = []
        in_dims = False
        cur = {}
        for line in current_yaml.split('\n'):
            stripped = line.strip()
            if stripped == 'dimensions:' or stripped.startswith('dimensions:'):
                in_dims = True
                continue
            if in_dims:
                if stripped.startswith('- name:'):
                    if cur:
                        dims.append(cur)
                    cur = {'name': stripped.replace('- name:', '').strip().strip("'\""), 'expr': ''}
                elif stripped.startswith('expr:') and cur:
                    cur['expr'] = stripped.replace('expr:', '').strip().strip("'\"")
                elif stripped and not line.startswith(' ') and not line.startswith('\t') and ':' in stripped:
                    if cur:
                        dims.append(cur)
                        cur = {}
                    in_dims = False
        if cur:
            dims.append(cur)

        dims_text = "\n".join(f"  - {d['name']}: {d['expr']}" for d in dims)

        # Measures ya creadas en esta view
        existing_in_view = [r['Measure'] for r in all_results if r['View'] == view_name and r['Status'] == 'OK']

        # Existing names for collision detection
        existing_names = set()
        for line in current_yaml.split('\n'):
            stripped = line.strip()
            if stripped.startswith('- name:'):
                existing_names.add(stripped.replace('- name:', '').strip().strip("'\""))

        print(f"\n{'='*60}")
        print(f"{view_name}: {len(failed_list)} measures fallidas, reintentando con contexto de dimensions")
        print(f"  Dimensions disponibles: {len(dims)}")
        print(f"  Measures existentes: {len(existing_in_view)}")
        print(f"{'='*60}")

        for fm in failed_list:
            measure_name = fm['measure_name']
            dax = fm['dax']

            print(f"\n  RETRY: {measure_name}")

            retry_prompt = f"""Convert this DAX measure to SQL for a Databricks Metrics View.
This measure FAILED in a previous attempt. Use the dimensions and measures below to make it work.

Measure: {measure_name}
DAX: {dax}

ALL DIMENSIONS available in this Metric View — use ANY_VALUE(name) to reference pre-computed values:
{dims_text}

ALL MEASURES already created — use MEASURE(name) to reference:
{json.dumps(existing_in_view)}

INSTRUCTIONS:
- Match the DAX logic to existing dimensions and measures listed above.
- For RANKX/TOPN/window patterns: find the matching pre-computed dimension and use ANY_VALUE(dimension_name).
- For columns from joined tables: use the dimension name (e.g., if dimension "join_segmento" has expr "join.SEGMENTO", use join_segmento in aggregations).
- For ratios/percentages: use MEASURE(numerator) / NULLIF(MEASURE(denominator), 0).
- Every column reference MUST be inside an aggregate (SUM, COUNT, ANY_VALUE, etc.) or MEASURE().
- Apply the LOD patterns from the Metric View documentation (Fixed LOD, Coarser LOD, Window Measures) as needed.

Return ONLY: {{"name": "snake_case_name", "sql_expr": "expression", "display_name": "Human Name"}}
Or if truly impossible: {{"skip": true, "reason": "explanation"}}"""

            try:
                result = call_claude(retry_prompt, max_tokens=2000)
                m_json = json.loads(result) if result.startswith('{') else json.loads(re.search(r'\{.*\}', result, re.DOTALL).group())
            except Exception as e:
                print(f"    x Error parsing: {str(e)[:80]}")
                continue

            if m_json.get('skip'):
                print(f"    SKIP: {m_json.get('reason', '')[:100]}")
                continue

            mname = m_json.get('name', measure_name.lower().replace(' ', '_'))
            sql_expr = m_json.get('sql_expr', '')

            if mname in existing_names:
                mname = f"r_{mname}"
            if mname in existing_names:
                mname = f"retry_{measure_name.lower().replace(' ', '_')}"

            block = _build_bare_measure_yaml(mname, sql_expr, m_json.get('display_name', measure_name))
            if "measures:" not in current_yaml:
                test_yaml = current_yaml.rstrip() + "\nmeasures:\n" + block + "\n"
            else:
                test_yaml = current_yaml.rstrip() + "\n" + block + "\n"

            try:
                spark.sql(f"""CREATE OR REPLACE VIEW {view_name} WITH METRICS LANGUAGE YAML AS $$\n{test_yaml}\n$$""")
                current_yaml = test_yaml
                existing_names.add(mname)
                existing_in_view.append(mname)
                # Update result from SKIP to OK
                for r in all_results:
                    if r['View'] == view_name and r['Measure'] == measure_name and r['Status'] == 'SKIP':
                        r['Status'] = 'OK'
                        r['Measure'] = mname
                        break
                print(f"    OK {mname}")
            except Exception as e:
                err = str(e)[:300]
                print(f"    x {err[:200]}")

        mv_views[base_table]['yaml'] = current_yaml

# COMMAND ----------

# MAGIC %md
# MAGIC ## 8. Resultados

# COMMAND ----------

results_df = pd.DataFrame(all_results)

if not results_df.empty:
    total = len(results_df)
    ok = len(results_df[results_df['Status'] == 'OK'])
    skip = len(results_df[results_df['Status'] == 'SKIP'])

    print(f"=== COBERTURA DE MEASURES ===")
    print(f"Total procesadas:  {total}")
    print(f"Creadas OK:        {ok} ({100*ok/total:.0f}%)")
    print(f"Saltadas:          {skip} ({100*skip/total:.0f}%)")
    print(f"Total en .pbix:    {len(measures_df)}")
    print(f"No procesadas:     {len(measures_df) - total}")

    print(f"\nPor view:")
    for view, group in results_df.groupby('View'):
        ok_v = len(group[group['Status'] == 'OK'])
        print(f"  {view}: {ok_v}/{len(group)} OK")

    # Reordenar columnas: Original primero para facilitar mapeo
    col_order = ['View', 'Original', 'Measure', 'Status']
    results_df = results_df[[c for c in col_order if c in results_df.columns]]
    display(results_df)

    # ─────────────────────────────────────────────────────────────────
    # VALIDACIÓN ANTI-ALUCINACIÓN
    # Para cada measure creada, verifica que los literales del SQL
    # traducido aparezcan en el DAX original. Si no, lo flagea.
    # ─────────────────────────────────────────────────────────────────
    print("\n=== VALIDACIÓN ANTI-ALUCINACIÓN ===")
    validation_rows = []
    for view_name, info in mv_views.items():
        view_yaml = info.get('yaml', '')
        # Parsear measures del YAML por bloques
        import re as _re
        # Cada measure: '- name: X' seguido de 'expr: ...'
        for m_block in _re.finditer(
            r'-\s*name:\s*(\S+)[\s\S]*?expr:\s*"((?:[^"\\]|\\.)*)"',
            view_yaml
        ):
            mname = m_block.group(1)
            sql_expr = m_block.group(2).replace('\\"', '"').replace('\\\\', '\\')
            # Buscar el DAX original en pbi_measures (por display_name o nombre)
            dax_match = measures_df[
                measures_df['Measure'].str.lower().str.replace(' ', '_').str.replace('-', '_') == mname.lower()
            ]
            if dax_match.empty:
                continue
            dax_expr = dax_match.iloc[0].get('DAX', '')
            suspicious = _validate_sql_against_dax(sql_expr, dax_expr)
            validation_rows.append({
                'view': view_name,
                'measure': mname,
                'original_dax_measure': dax_match.iloc[0].get('Measure', ''),
                'suspicious_count': len(suspicious),
                'suspicious_literals': "; ".join(f"{s['type']}:{s['value']}" for s in suspicious) if suspicious else "",
                'status': 'NEEDS_REVIEW' if suspicious else 'OK',
                'sql_expr_preview': sql_expr[:200],
            })

    validation_df = pd.DataFrame(validation_rows)
    if not validation_df.empty:
        n_review = len(validation_df[validation_df['status'] == 'NEEDS_REVIEW'])
        n_ok = len(validation_df[validation_df['status'] == 'OK'])
        print(f"  Measures verificadas: {len(validation_df)}")
        print(f"  ✓ Sin literales sospechosos: {n_ok}")
        print(f"  ⚠ NEEDS_REVIEW (literales no en DAX original): {n_review}")
        if n_review > 0:
            print(f"\n  Sospechosas (primeras 10):")
            for _, r in validation_df[validation_df['status'] == 'NEEDS_REVIEW'].head(10).iterrows():
                print(f"    · {r['measure']}: {r['suspicious_literals']}")
        # Guardar tabla
        spark.createDataFrame(validation_df.astype(str)).write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{CATALOG}.{SCHEMA}.pbi_measure_validation")
        print(f"\n  Detalle completo en: {CATALOG}.{SCHEMA}.pbi_measure_validation")
    else:
        print("  (sin measures que validar)")

    # Guardar cobertura
    spark.createDataFrame(results_df.astype(str)).write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{CATALOG}.{SCHEMA}.pbi_measure_coverage")
    print(f"\nOK {CATALOG}.{SCHEMA}.pbi_measure_coverage")
else:
    print("No hay resultados")


# COMMAND ----------

# MAGIC %md
# MAGIC ## Auto-fix de measures (sin LLM en el loop)
# MAGIC
# MAGIC La validación anti-alucinación arriba **flagea** measures sospechosas pero no las
# MAGIC arregla. Aquí aplicamos auto-fix determinista para los 3 bugs más comunes:
# MAGIC
# MAGIC 1. `SUM(col)` o `AVG(col)` donde col es STRING → COUNT(*)
# MAGIC 2. División sin NULLIF → auto-envolver denominador
# MAGIC 3. `THEN <string_flag>` en CASE WHEN → THEN 1
# MAGIC
# MAGIC Los fixes leen el schema vivo de la tabla source (no hardcoded).
# MAGIC Las measures se reescriben en la metric view después.

# COMMAND ----------

import sys, os
sys.path.insert(0, MODULE_PATH if os.path.isdir(MODULE_PATH) else os.path.dirname(os.path.abspath('')))

from measure_validators import (
    fix_measure_expression,
    get_source_columns_types,
)

# Leer tipos de columnas del schema vivo de cada base table
print("\n=== AUTO-FIX MEASURES ===")
auto_fix_report = []

for view_name, info in mv_views.items():
    base_table = info.get('catalog_table', '').split('.')[-1] if info.get('catalog_table') else None
    if not base_table:
        continue

    try:
        col_types = get_source_columns_types(spark, CATALOG, SCHEMA, base_table)
    except Exception as e:
        print(f"  ⚠ {view_name}: no se pudo leer schema de {base_table}: {e}")
        continue

    # Re-leer YAML actual y aplicar fixes a cada measure
    yaml_text = info.get('yaml', '')
    import re as _re
    measures_blocks = list(_re.finditer(
        r'(-\s*name:\s*\S+[\s\S]*?expr:\s*")((?:[^"\\]|\\.)*)(")',
        yaml_text
    ))

    fixes_applied = 0
    for mb in measures_blocks:
        prefix, expr_escaped, suffix = mb.groups()
        expr = expr_escaped.replace('\\"', '"').replace('\\\\', '\\')
        new_expr, fixes = fix_measure_expression(expr, col_types)
        if fixes:
            new_expr_escaped = new_expr.replace('\\', '\\\\').replace('"', '\\"')
            yaml_text = yaml_text.replace(
                prefix + expr_escaped + suffix,
                prefix + new_expr_escaped + suffix
            )
            fixes_applied += len(fixes)
            for fix in fixes:
                auto_fix_report.append({'view': view_name, 'fix': fix})

    if fixes_applied > 0:
        # Re-crear la metric view con el YAML corregido
        try:
            spark.sql(f"""CREATE OR REPLACE VIEW {info.get('view_name', view_name)}
WITH METRICS
LANGUAGE YAML
AS $${yaml_text}$$""")
            info['yaml'] = yaml_text
            print(f"  ✓ {view_name}: {fixes_applied} fixes aplicados")
        except Exception as e:
            print(f"  ⚠ {view_name}: error re-creando view después de fixes: {str(e)[:200]}")

if auto_fix_report:
    import pandas as _pd
    fix_df = _pd.DataFrame(auto_fix_report)
    print(f"\nTotal fixes determinísticos: {len(fix_df)}")
    display(fix_df)
    # Guardar para auditoría
    spark.createDataFrame(fix_df.astype(str)).write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{CATALOG}.{SCHEMA}.pbi_measure_auto_fixes")
else:
    print("  (no se necesitaron fixes — o no se pudieron leer schemas)")
