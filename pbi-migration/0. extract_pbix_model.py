# Databricks notebook source
# MAGIC %md
# MAGIC # 0. Extraer modelo de Power BI (determinista)
# MAGIC
# MAGIC Lee un .pbix y extrae toda la metadata:
# MAGIC - Measures con su DAX
# MAGIC - Relaciones entre tablas
# MAGIC - Columnas calculadas
# MAGIC - Filtros de contexto DAX
# MAGIC - Slicers por pagina
# MAGIC - En que paginas se usa cada measure
# MAGIC
# MAGIC Guarda todo en Unity Catalog. No usa LLM.

# COMMAND ----------

# MAGIC %pip install pbixray
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Parametros

# COMMAND ----------

from pbixray import PBIXRay
import pandas as pd
import io, json, re, zipfile
from collections import defaultdict

dbutils.widgets.text("pbix_path", "/Volumes/<your_catalog>/<your_schema>/pbix/<your_dashboard>.pbix", "Path del .pbix")
dbutils.widgets.text("catalog", "pbi_migration", "Catalogo destino")
dbutils.widgets.text("schema", "couch", "Schema destino")

pbix_path = dbutils.widgets.get("pbix_path")
CATALOG = dbutils.widgets.get("catalog")
SCHEMA = dbutils.widgets.get("schema")

print(f"PBIX: {pbix_path}")
print(f"Destino: {CATALOG}.{SCHEMA}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Funciones auxiliares

# COMMAND ----------

def extract_context_filters(dax):
    """Extrae los filtros de contexto de una expresion DAX."""
    if not dax:
        return []
    filters = []

    for m in re.finditer(r"ALL\(\s*'?([^')]+)'?\s*\)", dax, re.IGNORECASE):
        filters.append({"tipo": "ALL", "target": m.group(1).strip(), "efecto": "Quita TODOS los filtros de esta tabla"})

    for m in re.finditer(r"ALL\(\s*'?([^')\[]+)'?\[([^\]]+)\]\s*\)", dax, re.IGNORECASE):
        filters.append({"tipo": "ALL(columna)", "target": f"{m.group(1).strip()}[{m.group(2)}]", "efecto": f"Quita filtro de {m.group(2)}"})

    for m in re.finditer(r"ALLEXCEPT\(\s*'?([^'),]+)'?\s*,\s*(.+?)\)", dax, re.IGNORECASE):
        filters.append({"tipo": "ALLEXCEPT", "target": m.group(1).strip(), "efecto": f"Quita todos los filtros EXCEPTO: {m.group(2).strip()}"})

    for m in re.finditer(r"REMOVEFILTERS\(\s*(.+?)\s*\)", dax, re.IGNORECASE):
        filters.append({"tipo": "REMOVEFILTERS", "target": m.group(1).strip(), "efecto": f"Quita filtro de {m.group(1).strip()}"})

    for m in re.finditer(r"FILTER\(\s*'?([^'),]+)'?\s*,\s*(.+?)\)", dax, re.IGNORECASE):
        filters.append({"tipo": "FILTER", "target": m.group(1).strip(), "efecto": f"Aplica condicion: {m.group(2).strip()[:60]}"})

    calc_match = re.finditer(r"CALCULATE\s*\((.+)\)", dax, re.IGNORECASE | re.DOTALL)
    for cm in calc_match:
        inner = cm.group(1)
        parts = inner.split(",")
        for part in parts[1:]:
            part = part.strip()
            if not re.match(r"(ALL|FILTER|ALLEXCEPT|REMOVEFILTERS|KEEPFILTERS|USERELATIONSHIP|CROSSFILTER|TREATAS|DATESYTD|TOTALYTD|DATEADD|SAMEPERIODLASTYEAR)\s*\(", part, re.IGNORECASE):
                if "=" in part or ">" in part or "<" in part or "IN " in part.upper():
                    filters.append({"tipo": "CALCULATE filtro", "target": part[:60], "efecto": f"Filtro directo: {part[:60]}"})

    for m in re.finditer(r"SELECTEDVALUE\(\s*'?([^')\[]+)'?\[([^\]]+)\]", dax, re.IGNORECASE):
        filters.append({"tipo": "SELECTEDVALUE", "target": f"{m.group(1).strip()}[{m.group(2)}]", "efecto": f"Lee valor seleccionado de {m.group(2)}"})

    for m in re.finditer(r"KEEPFILTERS\(\s*(.+?)\s*\)", dax, re.IGNORECASE):
        filters.append({"tipo": "KEEPFILTERS", "target": m.group(1).strip()[:60], "efecto": f"Interseccion de filtros: {m.group(1).strip()[:60]}"})

    for m in re.finditer(r"USERELATIONSHIP\(\s*'?([^')\[]+)'?\[([^\]]+)\]\s*,\s*'?([^')\[]+)'?\[([^\]]+)\]", dax, re.IGNORECASE):
        filters.append({"tipo": "USERELATIONSHIP", "target": f"{m.group(1).strip()}[{m.group(2)}] -> {m.group(3).strip()}[{m.group(4)}]", "efecto": f"Activa relacion inactiva: {m.group(1).strip()}[{m.group(2)}] con {m.group(3).strip()}[{m.group(4)}]"})

    for m in re.finditer(r"CROSSFILTER\(\s*'?([^')\[]+)'?\[([^\]]+)\]\s*,\s*'?([^')\[]+)'?\[([^\]]+)\]\s*,\s*(\w+)", dax, re.IGNORECASE):
        direction = m.group(5).strip()
        filters.append({"tipo": "CROSSFILTER", "target": f"{m.group(1).strip()}[{m.group(2)}] <-> {m.group(3).strip()}[{m.group(4)}]", "efecto": f"Cambia direccion de filtro a {direction}"})

    for m in re.finditer(r"TREATAS\(\s*(.+?)\s*,\s*'?([^')\[]+)'?\[([^\]]+)\]", dax, re.IGNORECASE):
        filters.append({"tipo": "TREATAS", "target": f"{m.group(2).strip()}[{m.group(3)}]", "efecto": f"Aplica valores como filtro virtual: {m.group(1).strip()[:60]} -> {m.group(2).strip()}[{m.group(3)}]"})

    for m in re.finditer(r"(DATESYTD|TOTALYTD)\(\s*'?([^')\[]+)'?\[([^\]]+)\]", dax, re.IGNORECASE):
        filters.append({"tipo": "TIME_YTD", "target": f"{m.group(2).strip()}[{m.group(3)}]", "efecto": f"Year-to-date sobre {m.group(3)}"})

    for m in re.finditer(r"DATEADD\(\s*'?([^')\[]+)'?\[([^\]]+)\]\s*,\s*(-?\d+)\s*,\s*(\w+)", dax, re.IGNORECASE):
        filters.append({"tipo": "TIME_DATEADD", "target": f"{m.group(1).strip()}[{m.group(2)}]", "efecto": f"Desplaza {m.group(3)} {m.group(4)} sobre {m.group(2)}"})

    for m in re.finditer(r"SAMEPERIODLASTYEAR\(\s*'?([^')\[]+)'?\[([^\]]+)\]", dax, re.IGNORECASE):
        filters.append({"tipo": "TIME_SPLY", "target": f"{m.group(1).strip()}[{m.group(2)}]", "efecto": f"Mismo periodo anio anterior sobre {m.group(2)}"})

    return filters


def get_alias_map(query):
    return {frm.get("Name", ""): frm.get("Entity", "") for frm in query.get("From", [])}


def clean_cols(df):
    """Limpia nombres de columnas para Delta."""
    import re as _re
    def _clean(c):
        for a, b in [('\u00e1','a'),('\u00e9','e'),('\u00ed','i'),('\u00f3','o'),('\u00fa','u'),('\u00f1','n'),
                      ('\u00c1','A'),('\u00c9','E'),('\u00cd','I'),('\u00d3','O'),('\u00da','U'),('\u00d1','N'),
                      ('a\u0301','a'),('e\u0301','e'),('i\u0301','i'),('o\u0301','o'),('u\u0301','u'),('n\u0303','n')]:
            c = c.replace(a, b)
        c = c.replace(" ", "_").replace("#", "Num").replace("%", "Pct")
        c = _re.sub(r'[^a-zA-Z0-9_]', '_', c)
        while '__' in c:
            c = c.replace('__', '_')
        c = c.strip('_')
        return c
    return df.rename(columns=_clean)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Extraer modelo del .pbix

# COMMAND ----------

model = PBIXRay(pbix_path)

# Measures
measures_df = model.dax_measures
print(f"{len(measures_df)} measures encontradas")

# Relaciones
rels_df = model.relationships
print(f"{len(rels_df)} relaciones")

# Columnas calculadas
try:
    calc_cols = model.dax_columns
    print(f"{len(calc_cols)} columnas calculadas")
except Exception as e:
    print(f"No hay columnas calculadas: {e}")
    calc_cols = pd.DataFrame()

# Layout
with open(pbix_path, 'rb') as f:
    pbix_bytes = f.read()
with zipfile.ZipFile(io.BytesIO(pbix_bytes)) as zf:
    raw = zf.read('Report/Layout')
    text = raw.decode('utf-16-le')
    if text[0] == '\ufeff':
        text = text[1:]
    layout = json.loads(text)
print(f"Layout: {len(layout.get('sections', []))} paginas")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Filtros de contexto DAX

# COMMAND ----------

context_rows = []
for _, row in measures_df.iterrows():
    name = row.get("Name", "")
    table = row.get("TableName", "")
    dax = str(row.get("Expression", ""))
    filters = extract_context_filters(dax)
    if filters:
        for f in filters:
            context_rows.append({
                "Measure": name,
                "Tabla Medida": table,
                "Tipo Filtro": f["tipo"],
                "Target": f["target"],
                "Efecto": f["efecto"],
            })
    else:
        context_rows.append({
            "Measure": name,
            "Tabla Medida": table,
            "Tipo Filtro": "(ninguno)",
            "Target": "",
            "Efecto": "Measure simple -- respeta todos los filtros externos",
        })

context_df = pd.DataFrame(context_rows)
print(f"{len(context_rows)} filtros de contexto")
display(context_df)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Slicers por pagina

# COMMAND ----------

page_filter_rows = []
for section in layout.get("sections", []):
    page_name = section.get("displayName", "?")
    for vc in section.get("visualContainers", []):
        config = json.loads(vc.get("config", "{}"))
        sv = config.get("singleVisual", {})
        if sv.get("visualType") != "slicer":
            continue
        query = sv.get("prototypeQuery", {})
        alias_map = get_alias_map(query)
        for sel in query.get("Select", []):
            if "Column" in sel:
                item = sel["Column"]
                src = item.get("Expression", {}).get("SourceRef", {})
                entity = src.get("Entity", alias_map.get(src.get("Source", ""), ""))
                prop = item.get("Property", "")
                page_filter_rows.append({
                    "Pagina": page_name,
                    "Tabla": entity,
                    "Columna": prop,
                    "Slicer": f"{entity}.{prop}",
                })

page_filters_df = pd.DataFrame(page_filter_rows)
print(f"{len(page_filter_rows)} slicers en {page_filters_df['Pagina'].nunique() if not page_filters_df.empty else 0} paginas")
display(page_filters_df)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Measure pages — en que paginas se usa cada measure

# COMMAND ----------

measure_pages = {}
for section in layout.get("sections", []):
    page_name = section.get("displayName", "?")
    for vc in section.get("visualContainers", []):
        config = json.loads(vc.get("config", "{}"))
        sv = config.get("singleVisual", {})
        query = sv.get("prototypeQuery", {})
        alias_map = get_alias_map(query)
        for sel in query.get("Select", []):
            if "Measure" in sel:
                item = sel["Measure"]
                prop = item.get("Property", "")
                if prop not in measure_pages:
                    measure_pages[prop] = set()
                measure_pages[prop].add(page_name)

slicers_by_page = {}
for _, row in page_filters_df.iterrows():
    page = row["Pagina"]
    if page not in slicers_by_page:
        slicers_by_page[page] = []
    slicers_by_page[page].append(row["Slicer"])

print(f"{len(measure_pages)} measures usadas en visuales")
for name, pages in sorted(measure_pages.items()):
    print(f"  {name}: {', '.join(sorted(pages))}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. Tabla combinada: Measures + Filtros + Paginas + Slicers

# COMMAND ----------

combined_rows = []
for _, row in measures_df.iterrows():
    name = row.get("Name", "")
    table = row.get("TableName", "")
    dax = str(row.get("Expression", ""))

    ctx_filters = extract_context_filters(dax)
    ctx_str = "; ".join([f"{f['tipo']}({f['target']})" for f in ctx_filters]) if ctx_filters else "Ninguno (respeta filtros)"

    pages = sorted(measure_pages.get(name, set()))
    page_slicers = set()
    for p in pages:
        page_slicers.update(slicers_by_page.get(p, []))

    combined_rows.append({
        "Measure": name,
        "Tabla": table,
        "DAX": dax,
        "Filtros de Contexto": ctx_str,
        "Paginas donde se usa": ", ".join(pages) if pages else "(no usada en visuales)",
        "Filtros de Pagina (slicers)": ", ".join(sorted(page_slicers)) if page_slicers else "(sin slicers)",
    })

combined_df = pd.DataFrame(combined_rows)
display(combined_df)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 8. Resumen

# COMMAND ----------

print(f"=== RESUMEN DEL MODELO ===")
print(f"Measures:             {len(measures_df)}")
print(f"Relaciones:           {len(rels_df)}")
try:
    print(f"Columnas calculadas:  {len(calc_cols)}")
except:
    print(f"Columnas calculadas:  0")
print(f"Paginas:              {len(layout.get('sections', []))}")
print(f"Slicers:              {len(page_filter_rows)}")
print(f"Filtros de contexto:  {len(context_rows)}")

print(f"\nMeasures por tabla:")
for table, group in measures_df.groupby("TableName"):
    print(f"  {table}: {len(group)}")
    for _, row in group.iterrows():
        dax = str(row.get("Expression", ""))[:80]
        print(f"    - {row.get('Name', '')}: {dax}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 9. Guardar en Unity Catalog

# COMMAND ----------

spark.createDataFrame(clean_cols(combined_df).astype(str)).write.mode("overwrite").saveAsTable(f"{CATALOG}.{SCHEMA}.pbi_measures")
print(f"OK {CATALOG}.{SCHEMA}.pbi_measures")

spark.createDataFrame(clean_cols(context_df).astype(str)).write.mode("overwrite").saveAsTable(f"{CATALOG}.{SCHEMA}.pbi_context_filters")
print(f"OK {CATALOG}.{SCHEMA}.pbi_context_filters")

spark.createDataFrame(clean_cols(page_filters_df).astype(str)).write.mode("overwrite").saveAsTable(f"{CATALOG}.{SCHEMA}.pbi_page_filters")
print(f"OK {CATALOG}.{SCHEMA}.pbi_page_filters")

if not rels_df.empty:
    spark.createDataFrame(clean_cols(rels_df).astype(str)).write.mode("overwrite").saveAsTable(f"{CATALOG}.{SCHEMA}.pbi_relationships")
    print(f"OK {CATALOG}.{SCHEMA}.pbi_relationships")

if not calc_cols.empty:
    spark.createDataFrame(clean_cols(calc_cols).astype(str)).write.mode("overwrite").saveAsTable(f"{CATALOG}.{SCHEMA}.pbi_calculated_columns")
    print(f"OK {CATALOG}.{SCHEMA}.pbi_calculated_columns")

print(f"\nTablas guardadas en {CATALOG}.{SCHEMA}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 10. Obtener tablas existentes en Unity Catalog

# COMMAND ----------

existing_tables = {}
existing_table_types = {}
try:
    tables_in_catalog = spark.sql(f"SHOW TABLES IN {CATALOG}.{SCHEMA}").collect()
    table_names = [r.tableName for r in tables_in_catalog]
    for tname in table_names:
        if tname.startswith("pbi_") or tname.startswith("mv_") or tname.startswith("v_dashboard_"):
            continue
        try:
            cols = spark.sql(f"DESCRIBE {CATALOG}.{SCHEMA}.{tname}").collect()
            col_names = [r.col_name for r in cols if not r.col_name.startswith('#')]
            existing_tables[tname] = col_names
        except Exception as desc_err:
            print(f"  SKIP {tname}: {str(desc_err)[:100]}")
    print(f"Tablas de datos en {CATALOG}.{SCHEMA}:")
    for tname, cols in existing_tables.items():
        print(f"  {tname}: {len(cols)} columnas")
except Exception as e:
    print(f"Error listando tablas: {e}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Listo
# MAGIC
# MAGIC Las siguientes tablas estan disponibles en Unity Catalog:
# MAGIC - `pbi_measures` — Measures con DAX, filtros, paginas, slicers
# MAGIC - `pbi_context_filters` — Filtros de contexto DAX por measure
# MAGIC - `pbi_page_filters` — Slicers por pagina
# MAGIC - `pbi_relationships` — Relaciones entre tablas
# MAGIC - `pbi_calculated_columns` — Columnas calculadas
# MAGIC
# MAGIC Variables disponibles para el siguiente notebook:
# MAGIC - `measures_df`, `rels_df`, `calc_cols`
# MAGIC - `context_df`, `page_filters_df`
# MAGIC - `measure_pages`, `slicers_by_page`
# MAGIC - `existing_tables`, `existing_table_types`
