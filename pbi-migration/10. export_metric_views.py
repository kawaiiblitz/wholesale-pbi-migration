# Databricks notebook source
# MAGIC %md
# MAGIC # Exportar Metric Views
# MAGIC
# MAGIC Descarga el YAML de todas las Metric Views del catálogo y las muestra/guarda.

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
# MAGIC ## 2. Listar Metric Views

# COMMAND ----------

views_df = spark.sql(f"SHOW VIEWS IN {CATALOG}.{SCHEMA}").toPandas()
metric_views = views_df[views_df['isMetric'] == True]['viewName'].tolist()

print(f"Metric Views encontradas: {len(metric_views)}")
for mv in metric_views:
    print(f"  {mv}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Extraer YAML de cada Metric View

# COMMAND ----------

import json

mv_yamls = {}

for mv_name in metric_views:
    full_name = f"{CATALOG}.{SCHEMA}.{mv_name}"
    print(f"\n{'='*60}")
    print(f"{full_name}")
    print(f"{'='*60}")

    try:
        desc_df = spark.sql(f"DESCRIBE EXTENDED {full_name}").toPandas()

        # Extraer columnas (dims y measures)
        dims = []
        measures = []
        yaml_text = ""

        for _, row in desc_df.iterrows():
            col_name = row['col_name'] or ''
            data_type = row['data_type'] or ''
            comment = row['comment'] or ''

            # Las columnas normales aparecen antes de la sección de metadata
            if col_name and not col_name.startswith('#') and col_name.strip():
                if 'measure' in data_type.lower():
                    measures.append(col_name)
                elif data_type and col_name not in ('', 'Catalog', 'Database', 'Table', 'Owner',
                                                      'Created Time', 'Last Access', 'Created By',
                                                      'Type', 'Provider', 'Comment', 'Table Properties',
                                                      'View Text', 'View Catalog and Namespace',
                                                      'View Query Output Columns', 'Language'):
                    dims.append(col_name)

            # El YAML está en la fila donde col_name vacío y data_type contiene "version:"
            if col_name == '' and data_type and 'version:' in data_type:
                yaml_text = data_type
            # O en View Text
            if 'View Text' in col_name and data_type:
                yaml_text = data_type

        mv_yamls[mv_name] = {
            'yaml': yaml_text,
            'dims': dims,
            'measures': measures,
        }

        print(f"  Dimensions: {len(dims)}")
        print(f"  Measures: {len(measures)} → {measures}")
        print(f"\n--- YAML ---")
        print(yaml_text)

    except Exception as e:
        print(f"  ERROR: {str(e)[:200]}")
        mv_yamls[mv_name] = {'yaml': '', 'dims': [], 'measures': [], 'error': str(e)}

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Guardar YAMLs como tabla

# COMMAND ----------

import pandas as pd

rows = []
for mv_name, info in mv_yamls.items():
    rows.append({
        'metric_view': f"{CATALOG}.{SCHEMA}.{mv_name}",
        'num_dimensions': len(info['dims']),
        'num_measures': len(info['measures']),
        'dimensions': ', '.join(info['dims']),
        'measures': ', '.join(info['measures']),
        'yaml': info['yaml'],
    })

export_df = pd.DataFrame(rows)
spark.createDataFrame(export_df).write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{CATALOG}.{SCHEMA}.pbi_metric_view_yamls")

print(f"\n✓ Guardado en {CATALOG}.{SCHEMA}.pbi_metric_view_yamls ({len(rows)} filas)")
display(export_df[['metric_view', 'num_dimensions', 'num_measures']])

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Generar script de recreación
# MAGIC
# MAGIC Para que el cliente pueda recrear las Metric Views en su workspace.

# COMMAND ----------

print("-- Script para recrear las Metric Views en otro workspace")
print("-- Cambiar el catálogo/schema según corresponda")
print()

for mv_name, info in mv_yamls.items():
    if not info['yaml']:
        continue
    full_name = f"{CATALOG}.{SCHEMA}.{mv_name}"
    print(f"CREATE OR REPLACE VIEW {full_name}")
    print(f"WITH METRICS")
    print(f"LANGUAGE YAML")
    print(f"AS $$")
    print(info['yaml'])
    print(f"$$;")
    print()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Resumen

# COMMAND ----------

print(f"{'='*60}")
print(f"METRIC VIEWS EXPORTADAS")
print(f"{'='*60}")
print(f"Catálogo: {CATALOG}.{SCHEMA}")
print(f"Total: {len(mv_yamls)}")
print()
for mv_name, info in mv_yamls.items():
    print(f"  {mv_name}: {len(info['dims'])} dims, {len(info['measures'])} measures")
print()
print(f"Tabla de export: {CATALOG}.{SCHEMA}.pbi_metric_view_yamls")
print(f"Script SQL: ver celda 5 arriba")
