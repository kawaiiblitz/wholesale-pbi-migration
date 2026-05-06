# Databricks notebook source
# MAGIC %md
# MAGIC # Orquestador — Migración Power BI a Databricks
# MAGIC
# MAGIC Cada celda llama a un notebook con sus parámetros visibles.
# MAGIC Corre celda por celda o todo de corrido.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Parámetros

# COMMAND ----------

dbutils.widgets.text("pbix_path", "/Volumes/<your_catalog>/<your_schema>/pbix/<your_dashboard>.pbix", "Path del archivo .pbix")
dbutils.widgets.text("catalog", "<your_catalog>", "Catálogo destino en Unity Catalog")
dbutils.widgets.text("schema", "<your_schema>", "Schema destino")
dbutils.widgets.text("dashboard_path", "/Users/<your-email>@databricks.com/pbi-migration/cpg-kpi-coach.lvdash.json", "Path del dashboard .lvdash.json")
dbutils.widgets.text("llm_endpoint", "databricks-claude-sonnet-4", "Endpoint del LLM")
dbutils.widgets.text("module_path", "/Workspace/Users/<your-email>@databricks.com/pbi-migration/modules", "Path de módulos Python")
dbutils.widgets.text("base_path", "/Users/<your-email>@databricks.com/pbi-migration", "Carpeta base donde viven los notebooks")

PBIX_PATH = dbutils.widgets.get("pbix_path")
CATALOG = dbutils.widgets.get("catalog")
SCHEMA = dbutils.widgets.get("schema")
DASHBOARD_PATH = dbutils.widgets.get("dashboard_path")
LLM_ENDPOINT = dbutils.widgets.get("llm_endpoint")
MODULE_PATH = dbutils.widgets.get("module_path")

BASE = dbutils.widgets.get("base_path")

print(f"PBIX:      {PBIX_PATH}")
print(f"Catálogo:  {CATALOG}.{SCHEMA}")
print(f"Dashboard: {DASHBOARD_PATH}")
print(f"LLM:       {LLM_ENDPOINT}")
print(f"Módulos:   {MODULE_PATH}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Paso 0 — Extraer modelo del PBIX

# COMMAND ----------

dbutils.notebook.run(
    f"{BASE}/0. extract_pbix_model",
    timeout_seconds=1800,
    arguments={
        "pbix_path": PBIX_PATH,
        "catalog": CATALOG,
        "schema": SCHEMA,
    }
)

# COMMAND ----------

# MAGIC %md
# MAGIC ### Paso 1 — Crear Metric Views base

# COMMAND ----------

dbutils.notebook.run(
    f"{BASE}/1. create_base_metric_views",
    timeout_seconds=1800,
    arguments={
        "pbix_path": PBIX_PATH,
        "catalog": CATALOG,
        "schema": SCHEMA,
        "module_path": MODULE_PATH,
        "llm_endpoint": LLM_ENDPOINT,
    }
)

# COMMAND ----------

# MAGIC %md
# MAGIC ### Paso 2a — Agregar measures a las Metric Views

# COMMAND ----------

dbutils.notebook.run(
    f"{BASE}/2. create_measures",
    timeout_seconds=3600,
    arguments={
        "catalog": CATALOG,
        "schema": SCHEMA,
        "module_path": MODULE_PATH,
        "llm_endpoint": LLM_ENDPOINT,
    }
)

# COMMAND ----------

# MAGIC %md
# MAGIC ### Paso 2b — Crear vistas SQL para el dashboard

# COMMAND ----------

dbutils.notebook.run(
    f"{BASE}/2.1 create_dashboard_views",
    timeout_seconds=1800,
    arguments={
        "catalog": CATALOG,
        "schema": SCHEMA,
        "llm_endpoint": LLM_ENDPOINT,
    }
)

# COMMAND ----------

# MAGIC %md
# MAGIC ### Paso 3 — Crear skeleton del dashboard (datasets + páginas)

# COMMAND ----------

dbutils.notebook.run(
    f"{BASE}/3. create_dashboard_semantic",
    timeout_seconds=600,
    arguments={
        "catalog": CATALOG,
        "schema": SCHEMA,
        "dashboard_path": DASHBOARD_PATH,
    }
)

# COMMAND ----------

# MAGIC %md
# MAGIC ### Paso 4 — Extraer visuales del PBIX

# COMMAND ----------

dbutils.notebook.run(
    f"{BASE}/4. extract_visuals",
    timeout_seconds=1800,
    arguments={
        "pbix_path": PBIX_PATH,
        "catalog": CATALOG,
        "schema": SCHEMA,
    }
)

# COMMAND ----------

# MAGIC %md
# MAGIC ### Paso 4b-1 — Extraer propiedades de visuales (sort, colores)

# COMMAND ----------

dbutils.notebook.run(
    f"{BASE}/4b. extract_visual_props",
    timeout_seconds=1800,
    arguments={
        "pbix_path": PBIX_PATH,
        "catalog": CATALOG,
        "schema": SCHEMA,
    }
)

# COMMAND ----------

# MAGIC %md
# MAGIC ### Paso 4b-2 — Crear traductor de nombres PBI → snake_case

# COMMAND ----------

dbutils.notebook.run(
    f"{BASE}/4b. create_name_translator",
    timeout_seconds=600,
    arguments={
        "catalog": CATALOG,
        "schema": SCHEMA,
    }
)

# COMMAND ----------

# MAGIC %md
# MAGIC ### Paso 5 — Generar dashboard con Claude

# COMMAND ----------

dbutils.notebook.run(
    f"{BASE}/5. generate_dashboard",
    timeout_seconds=1800,
    arguments={
        "catalog": CATALOG,
        "schema": SCHEMA,
        "dashboard_path": DASHBOARD_PATH,
        "llm_endpoint": LLM_ENDPOINT,
    }
)

# COMMAND ----------

# MAGIC %md
# MAGIC ### Paso 5b — Refinar dashboard (validar queries, limpiar counters)

# COMMAND ----------

dbutils.notebook.run(
    f"{BASE}/5b. refine_dashboard",
    timeout_seconds=600,
    arguments={
        "catalog": CATALOG,
        "schema": SCHEMA,
        "dashboard_path": DASHBOARD_PATH,
    }
)

# COMMAND ----------

# MAGIC %md
# MAGIC ### Paso 6 — Agregar filtros del Power BI

# COMMAND ----------

dbutils.notebook.run(
    f"{BASE}/6. add_dashboard_filters",
    timeout_seconds=600,
    arguments={
        "catalog": CATALOG,
        "schema": SCHEMA,
        "dashboard_path": DASHBOARD_PATH,
    }
)

# COMMAND ----------

# MAGIC %md
# MAGIC ### Paso 7 — Aplicar estilos

# COMMAND ----------

dbutils.notebook.run(
    f"{BASE}/7. apply_styles",
    timeout_seconds=600,
    arguments={
        "catalog": CATALOG,
        "schema": SCHEMA,
        "dashboard_path": DASHBOARD_PATH,
    }
)

# COMMAND ----------

# MAGIC %md
# MAGIC ### Paso 8 — Humanizar títulos con LLM

# COMMAND ----------

dbutils.notebook.run(
    f"{BASE}/8. humanize_titles (param)",
    timeout_seconds=600,
    arguments={
        "catalog": CATALOG,
        "schema": SCHEMA,
        "dashboard_path": DASHBOARD_PATH,
        "llm_endpoint": LLM_ENDPOINT,
    }
)
