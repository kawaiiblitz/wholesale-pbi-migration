# Databricks notebook source
# MAGIC %md
# MAGIC # Traductor de Nombres PBI → Databricks
# MAGIC
# MAGIC Genera un diccionario que mapea nombres de columnas y measures de Power BI
# MAGIC a los nombres snake_case de las Metrics Views en Databricks.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Parámetros

# COMMAND ----------

dbutils.widgets.text("catalog", "pbi_migration", "Catálogo")
dbutils.widgets.text("schema", "default", "Schema")
CATALOG = dbutils.widgets.get("catalog")
SCHEMA = dbutils.widgets.get("schema")
print(f"Catálogo: {CATALOG}.{SCHEMA}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Leer tablas fuente

# COMMAND ----------

import pandas as pd

# Columnas/measures de Power BI (del notebook 4)
pbi_fields = spark.sql(f"SELECT * FROM {CATALOG}.{SCHEMA}.pbi_visual_fields").toPandas()
pbi_measures = spark.sql(f"SELECT * FROM {CATALOG}.{SCHEMA}.pbi_measures").toPandas()

# Columnas/measures de las Metrics Views (del notebook 2)
sqls_df = spark.sql(f"SELECT * FROM {CATALOG}.{SCHEMA}.dashboard_view_sqls").toPandas()

# Describir cada Metrics View para obtener nombres exactos
mv_columns = {}  # {mv_name: [col_names]}
spark.sql(f"USE CATALOG {CATALOG}")
views_df = spark.sql(f"SHOW VIEWS IN {CATALOG}.{SCHEMA} LIKE 'mv_*'").collect()

for v in views_df:
    vname = v.viewName
    cols = spark.sql(f"DESCRIBE {CATALOG}.{SCHEMA}.{vname}").collect()
    mv_columns[vname] = []
    for c in cols:
        if c.col_name.startswith('#') or not c.col_name.strip():
            continue
        mv_columns[vname].append({
            'name': c.col_name,
            'type': 'measure' if 'measure' in (c.data_type or '') else 'dimension',
        })

print(f"Campos PBI: {len(pbi_fields)}")
print(f"Measures PBI: {len(pbi_measures)}")
print(f"Metrics Views: {len(mv_columns)}")
for mv, cols in mv_columns.items():
    dims = [c['name'] for c in cols if c['type'] == 'dimension']
    meass = [c['name'] for c in cols if c['type'] == 'measure']
    print(f"  {mv}: {len(dims)} dims, {len(meass)} measures")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Generar traductor

# COMMAND ----------

import re

def strip_accents(name):
    """Quita acentos: á→a, é→e, í→i, ó→o, ú→u, ñ→n."""
    replacements = {'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u', 'ñ': 'n',
                    'Á': 'A', 'É': 'E', 'Í': 'I', 'Ó': 'O', 'Ú': 'U', 'Ñ': 'N'}
    for k, v in replacements.items():
        name = name.replace(k, v)
    return name

def normalize(name):
    """Normaliza un nombre para comparación."""
    return strip_accents(name).lower().replace(' ', '_').replace("'", "").replace('-', '_')

def normalize_flat(name):
    """Normaliza quitando todos los separadores y acentos."""
    return re.sub(r'[^a-z0-9]', '', strip_accents(name).lower())

# Recoger todos los nombres snake_case de las Metrics Views
all_snake_names = {}  # {snake_name: {mv: mv_name, type: dim/measure}}
for mv, cols in mv_columns.items():
    for c in cols:
        all_snake_names[c['name']] = {'mv': mv, 'type': c['type']}

# Recoger todos los nombres PBI únicos (columnas y measures)
pbi_names = set()

# De pbi_visual_fields
for _, f in pbi_fields.iterrows():
    if f['column']:
        pbi_names.add((f['table'], f['column'], 'column'))
    if f['measure_name']:
        pbi_names.add((f['table'], f['measure_name'], 'measure'))

# De pbi_measures
for _, m in pbi_measures.iterrows():
    pbi_names.add((m['Tabla'], m['Measure'], 'measure'))

print(f"Nombres PBI únicos: {len(pbi_names)}")

# Matching
translation_rows = []

for pbi_table, pbi_name, pbi_type in sorted(pbi_names):
    pbi_norm = normalize(pbi_name)
    pbi_flat = normalize_flat(pbi_name)

    matched_snake = None
    matched_mv = None
    match_method = None

    # 1. Match exacto normalizado
    if pbi_norm in all_snake_names:
        matched_snake = pbi_norm
        matched_mv = all_snake_names[pbi_norm]['mv']
        match_method = 'exact'

    # 2. Match sin separadores
    if not matched_snake:
        for snake in all_snake_names:
            if normalize_flat(snake) == pbi_flat:
                matched_snake = snake
                matched_mv = all_snake_names[snake]['mv']
                match_method = 'flat'
                break

    # 3. Match parcial (PBI contenido en snake o viceversa)
    if not matched_snake:
        for snake in all_snake_names:
            snake_flat = normalize_flat(snake)
            if len(pbi_flat) > 3 and len(snake_flat) > 3:
                if pbi_flat in snake_flat or snake_flat in pbi_flat:
                    matched_snake = snake
                    matched_mv = all_snake_names[snake]['mv']
                    match_method = 'partial'
                    break

    # 4. Match por tabla PBI → MV (misma tabla, buscar columna similar)
    if not matched_snake:
        pbi_table_norm = normalize(pbi_table).replace('_', '')
        for mv, cols in mv_columns.items():
            mv_flat = mv.replace('mv_', '').replace('_', '')
            if pbi_table_norm in mv_flat or mv_flat in pbi_table_norm:
                for c in cols:
                    if normalize_flat(c['name']) == pbi_flat:
                        matched_snake = c['name']
                        matched_mv = mv
                        match_method = 'table_match'
                        break
                if matched_snake:
                    break

    # 5. Match fuzzy — Levenshtein-like: buscar el snake más similar (tolerancia a typos)
    if not matched_snake:
        best_score = 0
        best_snake = None
        best_mv = None
        for snake in all_snake_names:
            snake_flat = normalize_flat(snake)
            # Calcular caracteres en común (Jaccard sobre bigramas)
            if len(pbi_flat) < 4 or len(snake_flat) < 4:
                continue
            pbi_bigrams = set(pbi_flat[i:i+2] for i in range(len(pbi_flat)-1))
            snake_bigrams = set(snake_flat[i:i+2] for i in range(len(snake_flat)-1))
            if not pbi_bigrams or not snake_bigrams:
                continue
            intersection = pbi_bigrams & snake_bigrams
            union = pbi_bigrams | snake_bigrams
            score = len(intersection) / len(union)
            if score > best_score and score > 0.6:  # umbral 60% similitud
                best_score = score
                best_snake = snake
                best_mv = all_snake_names[snake]['mv']
        if best_snake:
            matched_snake = best_snake
            matched_mv = best_mv
            match_method = f'fuzzy({best_score:.0%})'

    translation_rows.append({
        'pbi_table': pbi_table,
        'pbi_name': pbi_name,
        'pbi_type': pbi_type,
        'databricks_name': matched_snake or '',
        'metric_view': matched_mv or '',
        'match_method': match_method or 'NO MATCH',
        'pbi_full': f"{pbi_table}.{pbi_name}",
    })

translation_df = pd.DataFrame(translation_rows)

# Resumen
total = len(translation_df)
matched = len(translation_df[translation_df['match_method'] != 'NO MATCH'])
unmatched = total - matched

print(f"\nResultado: {matched}/{total} nombres traducidos")
print(f"Sin match: {unmatched}")

if unmatched > 0:
    print(f"\nNombres SIN traducción:")
    for _, r in translation_df[translation_df['match_method'] == 'NO MATCH'].iterrows():
        print(f"  ✗ {r['pbi_full']} ({r['pbi_type']})")

print(f"\nPor método de match:")
print(translation_df['match_method'].value_counts().to_string())

display(translation_df)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Guardar en Unity Catalog

# COMMAND ----------

spark.createDataFrame(translation_df.astype(str)).write.mode("overwrite").saveAsTable(f"{CATALOG}.{SCHEMA}.pbi_name_translator")
print(f"✓ {CATALOG}.{SCHEMA}.pbi_name_translator ({len(translation_df)} filas)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Resumen

# COMMAND ----------

print(f"{'='*60}")
print(f"TRADUCTOR DE NOMBRES")
print(f"{'='*60}")
print(f"\nTabla: {CATALOG}.{SCHEMA}.pbi_name_translator")
print(f"Total mappings: {total}")
print(f"Traducidos: {matched} ✓")
print(f"Sin match: {unmatched} ✗")
print(f"\nEjemplos:")
for _, r in translation_df[translation_df['match_method'] != 'NO MATCH'].head(10).iterrows():
    print(f"  {r['pbi_name']:35s} → {r['databricks_name']:35s} ({r['match_method']})")

