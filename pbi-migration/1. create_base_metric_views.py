# Databricks notebook source
# MAGIC %md
# MAGIC # 1. Crear Metric Views base (source + joins + dimensions + LOD)
# MAGIC
# MAGIC Lee las tablas `pbi_*` del notebook 0 y para cada tabla base:
# MAGIC 1. Agrupa measures por tabla
# MAGIC 2. Detecta measures que necesitan Fixed LOD (window functions) y crea vistas pre-calculadas
# MAGIC 3. Claude genera el YAML base (source + joins + dimensions, sin measures)
# MAGIC 4. Intenta crear la Metric View sin measures para validar

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Parametros

# COMMAND ----------

import pandas as pd
import json, re, requests, sys
from collections import defaultdict

dbutils.widgets.text("pbix_path", "/Volumes/<your_catalog>/<your_schema>/pbix/<your_dashboard>.pbix", "Path del .pbix")
dbutils.widgets.text("catalog", "pbi_migration", "Catalogo destino")
dbutils.widgets.text("schema", "couch", "Schema destino")
dbutils.widgets.text("module_path", "/Workspace/Users/<your-email>@databricks.com/powerbi-model-analyzer", "Path modulos")
dbutils.widgets.text("llm_endpoint", "databricks-claude-sonnet-4", "Endpoint LLM")

pbix_path = dbutils.widgets.get("pbix_path")
CATALOG = dbutils.widgets.get("catalog")
SCHEMA = dbutils.widgets.get("schema")
MODULE_PATH = dbutils.widgets.get("module_path")
LLM_ENDPOINT = dbutils.widgets.get("llm_endpoint")

print(f"PBIX: {pbix_path}")
print(f"Destino: {CATALOG}.{SCHEMA}")
print(f"LLM: {LLM_ENDPOINT}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Leer datos del notebook 0 (todo de UC, sin tocar el .pbix)

# COMMAND ----------

# Measures con DAX completo
measures_df = spark.sql(f"SELECT * FROM {CATALOG}.{SCHEMA}.pbi_measures").toPandas()
print(f"{len(measures_df)} measures")

# Relaciones
try:
    rels_df = spark.sql(f"SELECT * FROM {CATALOG}.{SCHEMA}.pbi_relationships").toPandas()
    print(f"{len(rels_df)} relaciones")
except:
    rels_df = pd.DataFrame()
    print("0 relaciones")

# Slicers
try:
    page_filters_df = spark.sql(f"SELECT * FROM {CATALOG}.{SCHEMA}.pbi_page_filters").toPandas()
    print(f"{len(page_filters_df)} slicers")
except:
    page_filters_df = pd.DataFrame()
    print("0 slicers")

# Construir measure_pages y slicers_by_page desde pbi_measures
measure_pages = {}
for _, row in measures_df.iterrows():
    name = row.get('Measure', '')
    pages_str = row.get('Paginas_donde_se_usa', '')
    if pages_str and pages_str != '(no usada en visuales)':
        measure_pages[name] = set(p.strip() for p in pages_str.split(','))

slicers_by_page = {}
if not page_filters_df.empty:
    for _, row in page_filters_df.iterrows():
        page = row.get('Pagina', '')
        slicer = row.get('Slicer', '')
        if page not in slicers_by_page:
            slicers_by_page[page] = []
        slicers_by_page[page].append(slicer)

# Tablas de datos en UC (no pbi_* ni mv_*)
existing_tables = {}
existing_table_types = {}
tables_in_catalog = spark.sql(f"SHOW TABLES IN {CATALOG}.{SCHEMA}").collect()
for r in tables_in_catalog:
    tname = r.tableName
    if tname.startswith("pbi_") or tname.startswith("mv_") or tname.startswith("v_dashboard_"):
        continue
    try:
        cols = spark.sql(f"DESCRIBE {CATALOG}.{SCHEMA}.{tname}").collect()
        col_names = [c.col_name for c in cols if not c.col_name.startswith('#')]
        col_types = {c.col_name: c.data_type for c in cols if not c.col_name.startswith('#')}
        existing_tables[tname] = col_names
        existing_table_types[tname] = col_types
    except Exception as e:
        print(f"  SKIP {tname}: {str(e)[:100]}")

print(f"\nTablas de datos en UC:")
for tname, cols in existing_tables.items():
    print(f"  {tname}: {len(cols)} columnas")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Importar docs y construir system prompt

# COMMAND ----------

sys.path.insert(0, MODULE_PATH)
from metrics_view_docs import METRICS_VIEW_DOCS
from dax_function_reference import get_relevant_dax_docs

DAX_DOCS = get_relevant_dax_docs(measures_df)
print(f"DAX docs: {len(DAX_DOCS)} chars ({DAX_DOCS.count('###')} funciones)")

SYSTEM_PROMPT = f"""You are an expert in Databricks Metrics Views YAML.

Here is the COMPLETE official Databricks Metrics View documentation:

{METRICS_VIEW_DOCS}

Here is the DAX function reference for the functions used in this .pbix file:

{DAX_DOCS}

You generate valid Metrics View YAML following the documentation exactly.
"""

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. call_claude

# COMMAND ----------

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
# MAGIC ## 5. Agrupar measures por tabla base

# COMMAND ----------

def detect_base_table(dax_expression, measure_table):
    """Detecta la tabla base de una measure a partir de su DAX."""
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
    """Find ALL table names referenced in a DAX expression."""
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
        r"CALCULATE\([^,]+,\s*'?([^')\[]+)'?\[",
        r"'([^']+)'\[",
    ]
    excluded = {measure_table.lower(), 'true', 'false', 'blank'}
    tables = []
    for pattern in patterns:
        for m in re.finditer(pattern, dax, re.IGNORECASE):
            for g in range(1, m.lastindex + 1 if m.lastindex else 2):
                try:
                    t = m.group(g)
                    if t:
                        t = t.strip()
                        if t.lower() not in excluded and not any(c in t for c in '()=<>'):
                            tables.append(t)
                except:
                    pass
    return tables


def _match_to_uc_table(table_name, existing_tables):
    """Try to match a PBI table name to a UC table name."""
    normalized = table_name.lower().replace(' ', '_').replace("'", "")
    if normalized in existing_tables:
        return normalized
    for tname in existing_tables:
        if normalized.replace('_', '') == tname.replace('_', ''):
            return tname
        if normalized.replace('_', '') in tname.replace('_', '') or tname.replace('_', '') in normalized.replace('_', ''):
            return tname
    return None


def group_measures_by_table(measures_df, measure_pages, slicers_by_page, existing_tables):
    """Agrupa measures por tabla base detectada desde la DAX."""
    measures_by_base = defaultdict(list)
    fallback_count = 0
    reassigned_count = 0
    skipped = []

    for _, row in measures_df.iterrows():
        # Columnas UC (del notebook 0): Measure, Tabla, DAX
        # O columnas PBIXRay: Name, TableName, Expression
        name = row.get("Measure", row.get("Name", ""))
        table = row.get("Tabla", row.get("TableName", ""))
        dax = str(row.get("DAX", row.get("Expression", "")))
        base = detect_base_table(dax, table)

        if base:
            base_normalized = base.lower().replace(' ', '_').replace("'", "")
            if existing_tables and base_normalized not in existing_tables:
                matched = _match_to_uc_table(base, existing_tables)
                if matched:
                    base_normalized = matched
        else:
            base = table
            base_normalized = table.lower().replace(' ', '_').replace("'", "") if table else None

            if base_normalized:
                fallback_count += 1
                fallback_exists = base_normalized in existing_tables or _match_to_uc_table(base, existing_tables)

                if not fallback_exists and existing_tables:
                    dax_tables = _find_all_table_refs(dax, table)
                    matched_table = None
                    for dt in dax_tables:
                        matched = _match_to_uc_table(dt, existing_tables)
                        if matched:
                            matched_table = matched
                            break
                    if matched_table:
                        reassigned_count += 1
                        print(f"  [REASSIGN] '{name}': '{table}' -> '{matched_table}'")
                        base = matched_table
                        base_normalized = matched_table
                    else:
                        print(f"  [FALLBACK] '{name}' -> '{table}' (no match en UC)")
                else:
                    if fallback_exists and isinstance(fallback_exists, str):
                        base_normalized = fallback_exists
                    print(f"  [FALLBACK] '{name}' -> '{table}'")
            else:
                skipped.append(name)
                continue

        pages = sorted(measure_pages.get(name, set()))
        page_slicer_list = set()
        for p in pages:
            page_slicer_list.update(slicers_by_page.get(p, []))

        measures_by_base[base_normalized].append({
            'measure_name': name,
            'measure_table': table,
            'dax': dax,
            'base_table': base,
            'pages': ", ".join(pages) if pages else "(no usada)",
            'page_slicers': ", ".join(sorted(page_slicer_list)) if page_slicer_list else "(sin slicers)",
        })

    total_grouped = sum(len(v) for v in measures_by_base.values())
    print(f"\n=== RESUMEN ===")
    print(f"Total: {len(measures_df)} | Agrupadas: {total_grouped} | Fallback: {fallback_count} | Reasignadas: {reassigned_count} | Descartadas: {len(skipped)}")
    for base, mlist in measures_by_base.items():
        print(f"  {base}: {len(mlist)} measures")
    return measures_by_base

# COMMAND ----------

measures_by_base = group_measures_by_table(measures_df, measure_pages, slicers_by_page, existing_tables)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5b. Detectar measures que necesitan Fixed LOD

# COMMAND ----------

# Patrones DAX que requieren window functions en SQL -> Fixed LOD
_LOD_PATTERNS = [
    (r'RANKX\s*\(', 'RANKX -> RANK()/DENSE_RANK()'),
    (r'TOPN\s*\(', 'TOPN -> ROW_NUMBER()'),
    (r'EARLIER\s*\(', 'EARLIER -> LAG()/self-ref'),
    (r'PERCENTILEX\s*\(', 'PERCENTILEX -> PERCENTILE_CONT()'),
    (r'MEDIANX\s*\(', 'MEDIANX -> PERCENTILE_CONT(0.5)'),
]

def needs_fixed_lod(dax):
    """Check if a DAX expression will require a window function in SQL."""
    if not dax:
        return False, []
    reasons = []
    for pattern, desc in _LOD_PATTERNS:
        if re.search(pattern, dax, re.IGNORECASE):
            reasons.append(desc)
    return bool(reasons), reasons

lod_candidates = {}  # {base_table: [measures that need LOD]}

for base_table, mlist in measures_by_base.items():
    candidates = []
    for m in mlist:
        is_lod, reasons = needs_fixed_lod(m['dax'])
        if is_lod:
            candidates.append({**m, 'lod_reasons': reasons})
    if candidates:
        lod_candidates[base_table] = candidates

print(f"Tablas con measures LOD: {len(lod_candidates)}")
for bt, cands in lod_candidates.items():
    print(f"  {bt}: {len(cands)} measures")
    for c in cands:
        print(f"    - {c['measure_name']}: {', '.join(c['lod_reasons'])}")
        print(f"      DAX: {c['dax'][:100]}")

if not lod_candidates:
    print("Ninguna measure requiere Fixed LOD — todas se pueden resolver con measures regulares o window measures.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5c. Crear vistas LOD con columnas pre-calculadas

# COMMAND ----------

lod_info = {}  # {base_table: {'view_name': str, 'lod_columns': [{'column_name', 'column_sql', 'for_measure', 'comment'}]}}

for base_table, candidates in lod_candidates.items():
    catalog_table = base_table
    if base_table not in existing_tables:
        matched = _match_to_uc_table(base_table, existing_tables)
        if matched:
            catalog_table = matched
        else:
            print(f"  SKIP {base_table}: no existe en UC")
            continue

    source_fqn = f"{CATALOG}.{SCHEMA}.{catalog_table}"
    cols = existing_tables.get(catalog_table, [])
    col_types = existing_table_types.get(catalog_table, {})
    cols_detail = "\n".join(f"  - {c}: {col_types.get(c, 'unknown')}" for c in cols)

    # Relaciones para contexto
    related_info = ""
    base_orig = candidates[0].get('base_table', '') if candidates else ''
    if hasattr(rels_df, 'iterrows'):
        for _, rel in rels_df.iterrows():
            from_t = str(rel.get('FromTableName', ''))
            to_t = str(rel.get('ToTableName', ''))
            from_c = str(rel.get('FromColumnName', ''))
            to_c = str(rel.get('ToColumnName', ''))
            if from_t == base_orig or to_t == base_orig:
                related_pbi = to_t if from_t == base_orig else from_t
                rt_match = _match_to_uc_table(related_pbi, existing_tables)
                if rt_match:
                    rt_cols = existing_tables.get(rt_match, [])
                    rt_types = existing_table_types.get(rt_match, {})
                    rt_detail = ", ".join(f"{c}({rt_types.get(c,'')})" for c in rt_cols[:15])
                    related_info += f"\n  Relationship: {from_t}[{from_c}] -> {to_t}[{to_c}]"
                    related_info += f"\n  UC table: {CATALOG}.{SCHEMA}.{rt_match} -- Columns: {rt_detail}"

    measures_info = "\n".join(f"- {c['measure_name']}: {c['dax']}" for c in candidates)

    prompt = f"""These DAX measures need SQL window functions (RANK, ROW_NUMBER, LAG, LEAD, PERCENTILE_CONT, etc.).
Generate the pre-computed LOD columns to add to the source view.

Source table: {source_fqn}
Columns:
{cols_detail}
{f"Relationships:{related_info}" if related_info else ""}

DAX measures that need window functions:
{measures_info}

Return a JSON array of LOD columns to add:
[
  {{
    "column_name": "unique_snake_case_name",
    "column_sql": "RANK() OVER (ORDER BY col DESC)",
    "for_measure": "original measure name",
    "comment": "brief explanation"
  }}
]

Rules:
- column_sql must be valid Databricks SQL (window function with OVER clause)
- Use ONLY columns from the source table: {cols}
- If multiple measures can share the same window column, generate it once
- column_name must NOT conflict with existing columns
- Return ONLY the JSON array, no markdown fences
- Return empty array [] if none actually need window functions after analysis"""

    print(f"\n--- {base_table}: analizando {len(candidates)} measures LOD ---")

    try:
        result = call_claude(prompt, max_tokens=2000)
        lod_columns = json.loads(result) if result.startswith('[') else json.loads(re.search(r'\[.*\]', result, re.DOTALL).group())
    except Exception as e:
        print(f"  Error parsing LOD columns: {str(e)[:100]}")
        continue

    if not lod_columns:
        print(f"  Sin columnas LOD necesarias tras analisis")
        continue

    # Construir y crear la vista LOD
    select_extras = ", ".join(f"{lc['column_sql']} AS {lc['column_name']}" for lc in lod_columns)
    lod_sql = f"SELECT src.*, {select_extras} FROM {source_fqn} src"
    lod_view_name = f"{CATALOG}.{SCHEMA}.lod_{catalog_table}"

    created = False
    for attempt in range(3):
        try:
            spark.sql(f"CREATE OR REPLACE VIEW {lod_view_name} AS {lod_sql}")
            print(f"  OK {lod_view_name}")
            for lc in lod_columns:
                print(f"    + {lc['column_name']}: {lc['column_sql'][:80]}")
            lod_info[base_table] = {
                'view_name': lod_view_name,
                'lod_columns': lod_columns,
            }
            created = True
            break
        except Exception as e:
            error_msg = str(e)[:500]
            print(f"  x intento {attempt+1}: {error_msg[:200]}")
            if attempt < 2:
                fix_prompt = f"""Fix this SQL view definition.

Error: {error_msg}
SQL: {lod_sql}
Source: {source_fqn}
Columns: {cols}

Return ONLY: {{"sql": "corrected SELECT statement"}}"""
                try:
                    fix_r = call_claude(fix_prompt, max_tokens=1000)
                    fix_j = json.loads(fix_r) if fix_r.startswith('{') else json.loads(re.search(r'\{.*\}', fix_r, re.DOTALL).group())
                    lod_sql = fix_j.get('sql', lod_sql)
                    print(f"  -> fix: {lod_sql[:100]}")
                except:
                    break

    if not created:
        print(f"  FAIL: no se pudo crear vista LOD para {base_table}")

print(f"\nVistas LOD creadas: {len(lod_info)}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5d. Analizar columnas requeridas por las measures de cada tabla

# COMMAND ----------

def _extract_dax_columns(dax):
    """Extract column references from DAX: 'Table'[Column] and [Column] patterns."""
    if not dax:
        return set()
    cols = set()
    # 'Table'[Column] or Table[Column]
    for m in re.finditer(r"'?([^'\[\]]+)'?\[([^\]]+)\]", dax):
        cols.add((m.group(1).strip(), m.group(2).strip()))
    # Standalone [Column] (no table prefix)
    for m in re.finditer(r"(?<!\w)\[([^\]]+)\]", dax):
        cols.add(('', m.group(1).strip()))
    return cols

def _normalize_col_name(name):
    """Normalize a column name for fuzzy matching."""
    n = name.lower().replace(' ', '_').replace("'", "")
    # Common PBI -> UC substitutions
    n = n.replace('%', 'pct').replace('#', 'num').replace('$', 'usd').replace('&', 'and')
    n = re.sub(r'[^a-z0-9_]', '', n)
    return n

def _map_column_to_uc(col_name, table_hint, base_table_cols, related_tables_map):
    """Map a PBI column name to a UC column. Returns (uc_table, uc_column) or None."""
    col_norm = _normalize_col_name(col_name)
    col_stripped = col_norm.replace('_', '')
    # Check in base table
    for uc_col in base_table_cols:
        uc_norm = _normalize_col_name(uc_col)
        if uc_norm == col_norm or uc_norm.replace('_', '') == col_stripped:
            return (None, uc_col)  # None = base table
    # Check in related tables
    for rt_name, rt_info in related_tables_map.items():
        for uc_col in rt_info['cols']:
            uc_norm = _normalize_col_name(uc_col)
            if uc_norm == col_norm or uc_norm.replace('_', '') == col_stripped:
                return (rt_name, uc_col)
    # Partial match: PBI name contained in UC name or vice versa
    for uc_col in base_table_cols:
        uc_stripped = _normalize_col_name(uc_col).replace('_', '')
        if col_stripped in uc_stripped or uc_stripped in col_stripped:
            return (None, uc_col)
    for rt_name, rt_info in related_tables_map.items():
        for uc_col in rt_info['cols']:
            uc_stripped = _normalize_col_name(uc_col).replace('_', '')
            if col_stripped in uc_stripped or uc_stripped in col_stripped:
                return (rt_name, uc_col)
    return None

# Build required columns map per base table
required_columns = {}  # {base_table: {'base': set(), 'related': {rt_name: set()}}}

for base_table, mlist in measures_by_base.items():
    catalog_table = base_table
    if base_table not in existing_tables:
        matched = _match_to_uc_table(base_table, existing_tables)
        if matched:
            catalog_table = matched
        else:
            continue

    base_cols = existing_tables.get(catalog_table, [])

    # Build related tables map from relationships
    base_orig = mlist[0].get('base_table', '') if mlist else ''
    related_map = {}  # {uc_table_name: {'pbi_name': ..., 'cols': [...], 'from_col': ..., 'to_col': ...}}
    if hasattr(rels_df, 'iterrows'):
        for _, rel in rels_df.iterrows():
            from_t = str(rel.get('FromTableName', ''))
            to_t = str(rel.get('ToTableName', ''))
            from_c = str(rel.get('FromColumnName', ''))
            to_c = str(rel.get('ToColumnName', ''))
            if from_t == base_orig or to_t == base_orig:
                related_pbi = to_t if from_t == base_orig else from_t
                rt_match = _match_to_uc_table(related_pbi, existing_tables)
                if rt_match and rt_match != catalog_table:
                    related_map[rt_match] = {
                        'pbi_name': related_pbi,
                        'cols': existing_tables.get(rt_match, []),
                        'from_col': from_c,
                        'to_col': to_c,
                        'from_table': from_t,
                        'to_table': to_t,
                    }

    # Extract all column references from all measures
    needed_base = set()
    needed_related = defaultdict(set)  # {uc_table: set(uc_columns)}
    unmapped = []

    for m in mlist:
        dax_cols = _extract_dax_columns(m['dax'])
        for table_hint, col_name in dax_cols:
            mapping = _map_column_to_uc(col_name, table_hint, base_cols, related_map)
            if mapping:
                rt_name, uc_col = mapping
                if rt_name is None:
                    needed_base.add(uc_col)
                else:
                    needed_related[rt_name].add(uc_col)
            else:
                unmapped.append(f"{table_hint}[{col_name}]" if table_hint else f"[{col_name}]")

    req = {'base': needed_base, 'related': dict(needed_related), 'related_map': related_map, 'unmapped': list(set(unmapped))}
    required_columns[base_table] = req

    # Report
    print(f"\n{base_table}:")
    print(f"  Base columns needed: {len(needed_base)}")
    for rt, rt_cols in needed_related.items():
        print(f"  From {rt}: {sorted(rt_cols)}")
    if unmapped:
        print(f"  UNMAPPED: {list(set(unmapped))[:10]}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Claude genera YAML base por tabla (source + joins + dimensions)

# COMMAND ----------

base_yamls = {}

for base_table, mlist in measures_by_base.items():
    catalog_table = base_table
    if base_table not in existing_tables:
        matched = _match_to_uc_table(base_table, existing_tables)
        if matched:
            catalog_table = matched
        else:
            print(f"  SKIP {base_table}: no existe en UC")
            continue

    # Determinar source: vista LOD o tabla original
    has_lod = base_table in lod_info
    if has_lod:
        source_fqn = lod_info[base_table]['view_name']
        lod_cols = lod_info[base_table]['lod_columns']
        lod_cols_info = "\n\nPre-computed LOD columns (already in source, add each one as a dimension):"
        for lc in lod_cols:
            lod_cols_info += f"\n  - {lc['column_name']}: {lc.get('comment', lc['column_sql'][:80])}"
    else:
        source_fqn = f"{CATALOG}.{SCHEMA}.{catalog_table}"
        lod_cols_info = ""

    cols = existing_tables.get(catalog_table, [])
    col_types = existing_table_types.get(catalog_table, {})
    cols_detail = "\n".join(f"  - {c}: {col_types.get(c, 'unknown')}" for c in cols)

    # Relaciones relevantes (con detalle completo de columnas)
    related_info = ""
    req = required_columns.get(base_table, {})
    related_map = req.get('related_map', {})
    needed_related = req.get('related', {})

    for rt_name, rt_info in related_map.items():
        rt_cols = existing_tables.get(rt_name, [])
        rt_types = existing_table_types.get(rt_name, {})
        rt_detail = "\n".join(f"    - {c}: {rt_types.get(c, 'unknown')}" for c in rt_cols)
        from_t = rt_info['from_table']
        to_t = rt_info['to_table']
        from_c = rt_info['from_col']
        to_c = rt_info['to_col']
        related_info += f"\n  Relationship: {from_t}[{from_c}] -> {to_t}[{to_c}]"
        related_info += f"\n  UC table: {CATALOG}.{SCHEMA}.{rt_name}"
        related_info += f"\n  Columns:\n{rt_detail}"
        # Highlight which columns the measures actually need
        needed_from_this = needed_related.get(rt_name, set())
        if needed_from_this:
            related_info += f"\n  ** REQUIRED by measures: {sorted(needed_from_this)} — MUST be included as dimensions via JOIN **"

    # Measures que iran en esta view
    measures_summary = ""
    for m in mlist[:20]:
        measures_summary += f"\n  - {m['measure_name']}: {m['dax'][:120]}"

    # Build required columns instruction
    required_cols_instruction = ""
    if needed_related:
        required_cols_instruction = "\n\nCRITICAL — REQUIRED COLUMNS FROM RELATED TABLES:\nThe measures assigned to this view reference columns that live in related tables. You MUST:\n1. Add a JOIN for each related table listed below\n2. Expose each required column as a dimension (prefixed with join alias)\n"
        for rt_name, rt_cols in needed_related.items():
            rt_info = related_map.get(rt_name, {})
            required_cols_instruction += f"\n  Table: {CATALOG}.{SCHEMA}.{rt_name}"
            required_cols_instruction += f"\n  Required columns: {sorted(rt_cols)}"
            if rt_info:
                required_cols_instruction += f"\n  Join on: {rt_info['from_table']}[{rt_info['from_col']}] -> {rt_info['to_table']}[{rt_info['to_col']}]"
            required_cols_instruction += "\n"

    prompt = f"""Generate a Databricks Metrics View YAML with ONLY source, joins, and dimensions (NO measures).
This YAML will be the base structure where measures will be added later one by one.

Source table: {source_fqn}
Columns:
{cols_detail}
{lod_cols_info}
{f"Related tables:{related_info}" if related_info else "No related tables."}
{required_cols_instruction}
These measures will be added later (use this to decide which dimensions are relevant):
{measures_summary}

RULES:
- version: 1.1
- source: {source_fqn}
- dimensions: one per column that is useful for segmenting/filtering. Use name=column_name.lower(), expr=column_name as-is.
- display_name: human-readable, from the original column name
- DO NOT include a measures section — it will be added later
- For date/timestamp columns, also add a month-level dimension (DATE_TRUNC)
- For joins: use the relationships above, 'on' key must be quoted
- For joined table dimensions: prefix name with join alias (e.g., joinname_column)
- EVERY column marked as REQUIRED above MUST appear as a dimension (via join). If you skip a required column, the measures that reference it will fail.
- Valid dimension fields ONLY: name, expr, display_name, comment, format, synonyms
- Valid join fields ONLY: name, source, 'on', using, joins
{"- IMPORTANT: The source is a LOD view with pre-computed window columns. Add each LOD column as a dimension (name=column_name, expr=column_name). These will be used by measures with ANY_VALUE() later." if has_lod else ""}
- Return ONLY the YAML. No markdown fences, no explanations.
- Add a dummy measure so the view can be validated:
  measures:
    - name: __row_count
      expr: "COUNT(1)"
"""

    print(f"\n{'='*60}")
    print(f"Generando YAML base para: {base_table} ({len(mlist)} measures pendientes)")
    if has_lod:
        print(f"  Source: {source_fqn} (LOD view con {len(lod_cols)} columnas pre-calculadas)")
    if needed_related:
        for rt, rt_cols in needed_related.items():
            print(f"  Required from {rt}: {sorted(rt_cols)}")
    print(f"{'='*60}")

    yaml_text = call_claude(prompt, max_tokens=4000)
    print(yaml_text[:500])

    base_yamls[base_table] = {
        'yaml': yaml_text,
        'catalog_table': catalog_table,
        'measures': mlist,
        'lod_columns': lod_info.get(base_table, {}).get('lod_columns', []),
        'required_columns': req,
    }

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. Validar cada YAML base creando la Metric View

# COMMAND ----------

validated_yamls = {}

for base_table, info in base_yamls.items():
    yaml_text = info['yaml']
    catalog_table = info['catalog_table']
    safe_name = f"mv_{base_table}".replace(' ', '_').replace("'", "")
    view_name = f"{CATALOG}.{SCHEMA}.{safe_name}"

    print(f"\n--- {view_name} ---")

    for attempt in range(3):
        try:
            create_sql = f"""CREATE OR REPLACE VIEW {view_name}
WITH METRICS
LANGUAGE YAML
AS $$
{yaml_text}
$$"""
            spark.sql(create_sql)
            print(f"  OK" + (f" (fix {attempt})" if attempt > 0 else ""))
            validated_yamls[base_table] = {
                'yaml': yaml_text,
                'catalog_table': catalog_table,
                'view_name': view_name,
                'measures': info['measures'],
                'lod_columns': info.get('lod_columns', []),
            }
            break
        except Exception as e:
            error_msg = str(e)[:500]
            print(f"  x intento {attempt+1}: {error_msg[:300]}")

            if attempt < 2:
                fix_prompt = f"""Fix this Databricks Metrics View YAML. It has NO measures yet, only source + joins + dimensions + a dummy __row_count measure.

ERROR:
{error_msg}

CURRENT YAML:
{yaml_text}

RULES:
- Valid dimension fields ONLY: name, expr, display_name, comment, format, synonyms
- Valid join fields ONLY: name, source, 'on', using, joins
- 'on' must be quoted in YAML
- No "type" field in dimensions
- Keep the dummy measure __row_count
- Return ONLY the fixed YAML. No markdown fences."""

                try:
                    yaml_text = call_claude(fix_prompt, max_tokens=4000)
                    print(f"  -> Claude corrigio, reintentando...")
                except Exception as ce:
                    print(f"  -> Error en fix: {str(ce)[:100]}")
                    break

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7b. Verificar que TODAS las columnas requeridas estan en el YAML

# COMMAND ----------

def _extract_yaml_dimension_names(yaml_text):
    """Extract all dimension names from a YAML string."""
    names = set()
    in_dims = False
    for line in yaml_text.split('\n'):
        stripped = line.strip()
        if stripped == 'dimensions:' or stripped.startswith('dimensions:'):
            in_dims = True
            continue
        if in_dims:
            if stripped.startswith('- name:'):
                name = stripped.replace('- name:', '').strip().strip("'\"")
                names.add(name.lower())
            elif stripped and not line.startswith(' ') and not line.startswith('\t') and ':' in stripped:
                in_dims = False
    return names

def _extract_yaml_dimension_exprs(yaml_text):
    """Extract all dimension exprs from a YAML string."""
    exprs = set()
    in_dims = False
    for line in yaml_text.split('\n'):
        stripped = line.strip()
        if stripped == 'dimensions:' or stripped.startswith('dimensions:'):
            in_dims = True
            continue
        if in_dims:
            if stripped.startswith('expr:'):
                expr = stripped.replace('expr:', '').strip().strip("'\"")
                exprs.add(expr.lower())
            elif stripped and not line.startswith(' ') and not line.startswith('\t') and ':' in stripped:
                in_dims = False
    return exprs

for base_table, info in list(validated_yamls.items()):
    req = required_columns.get(base_table, {})
    needed_related = req.get('related', {})
    if not needed_related:
        continue

    yaml_text = info['yaml']
    dim_names = _extract_yaml_dimension_names(yaml_text)
    dim_exprs = _extract_yaml_dimension_exprs(yaml_text)
    all_dims = dim_names | dim_exprs

    missing = []
    for rt_name, rt_cols in needed_related.items():
        for col in rt_cols:
            col_lower = col.lower()
            # Check if the column appears in any dimension (name or expr)
            found = any(col_lower in d or col_lower.replace('_', '') in d.replace('_', '') for d in all_dims)
            if not found:
                missing.append((rt_name, col))

    if missing:
        print(f"\n{info['view_name']}: {len(missing)} columnas requeridas FALTANTES")
        for rt, col in missing:
            print(f"  MISSING: {col} (from {rt})")

        # Ask Claude to add the missing columns
        related_map = req.get('related_map', {})
        missing_instructions = "Add these MISSING columns as dimensions. They are in related tables that MUST be joined:\n"
        missing_by_table = defaultdict(list)
        for rt, col in missing:
            missing_by_table[rt].append(col)
        for rt, cols in missing_by_table.items():
            rt_info = related_map.get(rt, {})
            missing_instructions += f"\nTable: {CATALOG}.{SCHEMA}.{rt} (columns: {cols})"
            if rt_info:
                missing_instructions += f"\nJoin: {rt_info['from_table']}[{rt_info['from_col']}] -> {rt_info['to_table']}[{rt_info['to_col']}]"
            # Include ALL columns from this table for reference
            all_rt_cols = existing_tables.get(rt, [])
            all_rt_types = existing_table_types.get(rt, {})
            missing_instructions += f"\nAll columns: " + ", ".join(f"{c}({all_rt_types.get(c, '')})" for c in all_rt_cols)

        fix_prompt = f"""This Metrics View YAML is missing dimensions that the measures need. Add them.

{missing_instructions}

CURRENT YAML:
{yaml_text}

RULES:
- If the related table is NOT already joined, add a join for it
- For each missing column, add a dimension with name=joinname_column_name (lowercase), expr=joinname.ColumnName
- 'on' must be quoted in YAML
- Valid dimension fields ONLY: name, expr, display_name, comment, format, synonyms
- Valid join fields ONLY: name, source, 'on', using, joins
- Keep ALL existing dimensions and joins intact
- Keep the dummy measure __row_count
- Return ONLY the complete fixed YAML. No markdown fences."""

        try:
            fixed_yaml = call_claude(fix_prompt, max_tokens=4000)
            # Re-validate
            view_name = info['view_name']
            spark.sql(f"""CREATE OR REPLACE VIEW {view_name} WITH METRICS LANGUAGE YAML AS $$\n{fixed_yaml}\n$$""")
            validated_yamls[base_table]['yaml'] = fixed_yaml
            # Verify again
            new_dims = _extract_yaml_dimension_names(fixed_yaml) | _extract_yaml_dimension_exprs(fixed_yaml)
            still_missing = [(rt, col) for rt, col in missing if not any(col.lower() in d or col.lower().replace('_', '') in d.replace('_', '') for d in new_dims)]
            if still_missing:
                print(f"  WARNING: aun faltan {len(still_missing)}: {still_missing}")
            else:
                print(f"  OK: {len(missing)} columnas agregadas y validadas")
        except Exception as e:
            print(f"  ERROR al agregar columnas faltantes: {str(e)[:200]}")
    else:
        print(f"{info['view_name']}: todas las columnas requeridas presentes")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 8. Resumen

# COMMAND ----------

print(f"=== METRIC VIEWS BASE ===")
print(f"Total tablas: {len(base_yamls)}")
print(f"Validadas OK: {len(validated_yamls)}")
print(f"Fallidas: {len(base_yamls) - len(validated_yamls)}")
print(f"Con Fixed LOD: {sum(1 for v in validated_yamls.values() if v.get('lod_columns'))}")
print()
for base_table, info in validated_yamls.items():
    lod_tag = f" [LOD: {len(info['lod_columns'])} cols]" if info.get('lod_columns') else ""
    print(f"  OK  {info['view_name']} ({len(info['measures'])} measures pendientes){lod_tag}")
for base_table in base_yamls:
    if base_table not in validated_yamls:
        print(f"  FAIL {base_table}")
