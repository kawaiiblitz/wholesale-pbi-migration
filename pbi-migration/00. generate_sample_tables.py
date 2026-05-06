# Databricks notebook source
# MAGIC %md
# MAGIC # Generar Tablas de Ejemplo desde PBIX
# MAGIC
# MAGIC Lee el modelo tabular del .pbix, extrae la estructura de cada tabla
# MAGIC (columnas + tipos), y genera datos sintéticos en Unity Catalog.
# MAGIC
# MAGIC **Genérico para cualquier PBIX.**

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Parámetros

# COMMAND ----------

# MAGIC %pip install pbixray
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

import json, io, zipfile, random, string
from datetime import datetime, timedelta
import pandas as pd

dbutils.widgets.text("pbix_path", "", "Path del archivo .pbix en Volumes")
dbutils.widgets.text("catalog", "pbi_migration", "Catálogo destino")
dbutils.widgets.text("schema", "default", "Schema destino")
dbutils.widgets.text("rows_per_table", "500", "Filas a generar por tabla")
dbutils.widgets.dropdown("overwrite", "false", ["true", "false"], "Sobreescribir si existe")

PBIX_PATH = dbutils.widgets.get("pbix_path")
CATALOG = dbutils.widgets.get("catalog")
SCHEMA = dbutils.widgets.get("schema")
ROWS = int(dbutils.widgets.get("rows_per_table"))
OVERWRITE = dbutils.widgets.get("overwrite") == "true"

print(f"PBIX: {PBIX_PATH}")
print(f"Destino: {CATALOG}.{SCHEMA}")
print(f"Filas por tabla: {ROWS}")
print(f"Sobreescribir: {OVERWRITE}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Leer modelo del PBIX

# COMMAND ----------

from pbixray import PBIXRay

with open(PBIX_PATH, 'rb') as f:
    pbix_bytes = f.read()

model = PBIXRay(io.BytesIO(pbix_bytes))

# Extraer estructura de tablas
tables_info = {}

# Método 1: usar model.schema si existe
try:
    schema_df = model.schema
    for _, row in schema_df.iterrows():
        table = row.get('TableName', row.get('table_name', ''))
        col = row.get('ColumnName', row.get('column_name', row.get('ExplicitName', '')))
        dtype = row.get('DataType', row.get('data_type', row.get('ExplicitDataType', 'String')))

        if not table or not col:
            continue
        # Skip internal PBI tables
        if table.startswith('LocalDateTable') or table.startswith('DateTableTemplate'):
            continue
        if col.startswith('RowNumber'):
            continue

        if table not in tables_info:
            tables_info[table] = []
        tables_info[table].append({'column': col, 'data_type': str(dtype)})
    print(f"Método schema: {len(tables_info)} tablas")
except Exception as e:
    print(f"model.schema no disponible: {e}")

# Método 2: usar model.tables si schema no funcionó
if not tables_info:
    try:
        for table_name in model.tables:
            if table_name.startswith('LocalDateTable') or table_name.startswith('DateTableTemplate'):
                continue
            try:
                tdf = model.get_table(table_name)
                cols = []
                for c in tdf.columns:
                    dtype = str(tdf[c].dtype)
                    cols.append({'column': c, 'data_type': dtype})
                if cols:
                    tables_info[table_name] = cols
            except:
                pass
        print(f"Método tables: {len(tables_info)} tablas")
    except Exception as e:
        print(f"model.tables no disponible: {e}")

# Método 3: extraer del DataModel dentro del ZIP
if not tables_info:
    try:
        with zipfile.ZipFile(io.BytesIO(pbix_bytes)) as zf:
            for name in zf.namelist():
                if 'DataModel' in name or 'DataMashup' in name:
                    print(f"  Found: {name}")
        # Try reading the tabular model JSON
        for name in zf.namelist():
            if name.endswith('.json') and 'model' in name.lower():
                content = json.loads(zf.read(name))
                if 'model' in content:
                    for table in content['model'].get('tables', []):
                        tname = table.get('name', '')
                        if tname.startswith('LocalDateTable') or tname.startswith('DateTableTemplate'):
                            continue
                        cols = []
                        for col in table.get('columns', []):
                            cols.append({
                                'column': col.get('name', ''),
                                'data_type': col.get('dataType', 'string'),
                            })
                        if cols:
                            tables_info[tname] = cols
        print(f"Método ZIP JSON: {len(tables_info)} tablas")
    except Exception as e:
        print(f"Método ZIP: {e}")

if not tables_info:
    raise Exception("No se pudo extraer la estructura de tablas del PBIX")

print(f"\nTablas encontradas: {len(tables_info)}")
for tname, cols in tables_info.items():
    print(f"  {tname}: {len(cols)} columnas")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2b. Leer valores reales del PBIX (vocabulario de filtros)
# MAGIC
# MAGIC Para que los datos sintéticos sean coherentes con las measures DAX,
# MAGIC extraemos los valores literales que aparecen en filtros de los visuales.
# MAGIC Ej: si un visual filtra `CC_MEMBER_GROUP_TYPE IN ('Regular Gold & Business')`,
# MAGIC ese valor entra al vocabulario para esa columna en lugar de placeholders genéricos.

# COMMAND ----------

# Diccionario {column_name_lowercase: [valores reales de filtros]}
real_values_by_column = {}

try:
    with zipfile.ZipFile(io.BytesIO(pbix_bytes)) as zf:
        layout_raw = zf.read('Report/Layout')
        layout_text = layout_raw.decode('utf-16-le').lstrip('﻿')
        layout_json = json.loads(layout_text)

    def collect_filter_values(filter_obj, col_to_values):
        """Recorrer un filter['filter']['Where'] y extraer literales por columna."""
        col_prop = None
        expr = filter_obj.get("expression", {})
        col = expr.get("Column", {})
        if col:
            col_prop = col.get("Property", "")

        if not col_prop:
            return

        for w in filter_obj.get("filter", {}).get("Where", []):
            cond = w.get("Condition", {})

            # IN
            if "In" in cond:
                for val_set in cond["In"].get("Values", []):
                    for v in val_set:
                        lit = v.get("Literal", {}).get("Value", "")
                        if lit:
                            col_to_values.setdefault(col_prop.lower(), set()).add(
                                str(lit).strip("'\"")
                            )

            # Comparison =
            elif "Comparison" in cond:
                lit = cond["Comparison"].get("Right", {}).get("Literal", {}).get("Value", "")
                if lit:
                    col_to_values.setdefault(col_prop.lower(), set()).add(
                        str(lit).strip("'\"")
                    )

            # Not(In)
            elif "Not" in cond:
                inner = cond["Not"].get("Expression", {})
                if "In" in inner:
                    for val_set in inner["In"].get("Values", []):
                        for v in val_set:
                            lit = v.get("Literal", {}).get("Value", "")
                            if lit:
                                col_to_values.setdefault(col_prop.lower(), set()).add(
                                    str(lit).strip("'\"")
                                )

    # Recorrer todos los visuales y sus filtros
    for section in layout_json.get("sections", []):
        # Filtros a nivel de página
        page_filters_raw = section.get("filters", "[]")
        page_filters = json.loads(page_filters_raw) if isinstance(page_filters_raw, str) else page_filters_raw
        for f in page_filters:
            collect_filter_values(f, real_values_by_column)

        for vc in section.get("visualContainers", []):
            vc_filters_raw = vc.get("filters", "[]")
            vc_filters = json.loads(vc_filters_raw) if isinstance(vc_filters_raw, str) else vc_filters_raw
            for f in vc_filters:
                collect_filter_values(f, real_values_by_column)

    # Filtros a nivel reporte
    report_filters_raw = layout_json.get("filters", "[]")
    report_filters = json.loads(report_filters_raw) if isinstance(report_filters_raw, str) else report_filters_raw
    for f in report_filters:
        collect_filter_values(f, real_values_by_column)

    # Adicionalmente: extraer literales que aparecen en las DAX expressions de measures.
    # Esto cubre comparaciones como `executive_flag = 'Y'` o `cc_members_count = 0`
    # que no se reflejan en filtros visuales pero sí en las definiciones DAX.
    try:
        from pbixray import PBIXRay as _PB
        _model = _PB(io.BytesIO(pbix_bytes))
        _measures_df = _model.dax_measures
        import re as _re
        for _, mrow in _measures_df.iterrows():
            dax = str(mrow.get('Expression', mrow.get('DAX', '')))
            # Patrón principal: TableName[COLUMN] = 'value'  o  COLUMN = 'value'
            for m in _re.finditer(
                r"\[([A-Z_][A-Z0-9_]*)\]\s*(?:=|<>|!=|IN)\s*[\"']([^\"']{1,80})[\"']",
                dax, _re.IGNORECASE
            ):
                col = m.group(1).lower()
                val = m.group(2)
                real_values_by_column.setdefault(col, set()).add(val)
            # Patrón numérico: TableName[COLUMN] = 0  (puede tener sufijo L de Long)
            for m in _re.finditer(
                r"\[([A-Z_][A-Z0-9_]*)\]\s*(?:=|<>|!=)\s*(-?\d+(?:\.\d+)?)L?",
                dax, _re.IGNORECASE
            ):
                col = m.group(1).lower()
                val = m.group(2)  # sin la L
                real_values_by_column.setdefault(col, set()).add(val)
    except Exception as e:
        print(f"  WARN no pude extraer literales DAX: {e}")

    # Convertir sets a listas ordenadas
    real_values_by_column = {k: sorted(v) for k, v in real_values_by_column.items()}
    print(f"Vocabulario real extraído del PBIX: {len(real_values_by_column)} columnas con valores reales")
    for col, vals in list(real_values_by_column.items())[:15]:
        print(f"  {col}: {vals[:5]}{'...' if len(vals) > 5 else ''}")
except Exception as e:
    print(f"WARN: no se pudo extraer vocabulario del PBIX: {e}")
    real_values_by_column = {}

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Generar datos sintéticos

# COMMAND ----------

def pbi_type_to_generator(data_type, col_name):
    """Retorna una función que genera valores random para el tipo dado."""
    dt = str(data_type).lower()
    cn = col_name.lower()

    # Si tenemos vocabulario real desde los filtros del PBIX, usarlo
    # excepto para columnas numéricas pequeñas (0/1) donde el vocab del DAX
    # captura literales de filtro y forzaría a SUM = 0.
    if cn in real_values_by_column:
        vals = real_values_by_column[cn]
        if vals:
            # Si todos los valores son numéricos y pequeños, mezclar con aleatorios
            try:
                int_vals = [int(float(v)) for v in vals]
                if all(0 <= v <= 9 for v in int_vals) and any(
                    k in cn for k in ['count', 'qty', 'cantidad', 'visits', 'shops', 'trxn']
                ):
                    # 30% del vocab (para que filtros matcheen), 70% random 1-9
                    return lambda: random.choice(int_vals) if random.random() < 0.3 else random.randint(1, 9)
            except (ValueError, TypeError):
                pass
            return lambda: random.choice(vals)

    # Detectar por nombre de columna
    if any(k in cn for k in ['fecha', 'date', 'time', 'timestamp']):
        base = datetime(2024, 1, 1)
        return lambda: base + timedelta(days=random.randint(0, 730))
    if any(k in cn for k in ['email', 'correo']):
        return lambda: f"user{random.randint(1,999)}@example.com"
    if any(k in cn for k in ['pais', 'country']):
        countries = ['MX', 'US', 'CA', 'BR', 'CO', 'AR', 'CL', 'PE', 'ES', 'FR']
        return lambda: random.choice(countries)
    if any(k in cn for k in ['estado', 'state', 'region']):
        states = ['Norte', 'Sur', 'Este', 'Oeste', 'Centro', 'Noroeste', 'Sureste']
        return lambda: random.choice(states)
    # Columnas dimensionales tipo warehouse/almacén/bodega/sucursal
    if any(k in cn for k in ['warehouse', 'almacen', 'bodega', 'sucursal', 'tienda', 'store']):
        whs = ['Alpha', 'Beta', 'Gamma', 'Delta', 'Epsilon', 'Zeta', 'Eta', 'Theta', 'Iota', 'Kappa']
        return lambda: random.choice(whs)
    # Distritos/territorios
    if any(k in cn for k in ['district', 'distrito', 'territorio', 'territory', 'zone', 'zona']):
        districts = ['Norte', 'Sur', 'Centro', 'Bajío', 'Pacífico', 'Golfo', 'Península']
        return lambda: random.choice(districts)
    # Facility / planta / centro
    if any(k in cn for k in ['facility', 'planta', 'centro', 'plant']):
        return lambda: f"FAC-{random.choice(['A','B','C','D','E','F'])}{random.randint(1,9)}"
    # Account type / membership type
    if any(k in cn for k in ['account_type', 'membership_type', 'tipo_cuenta', 'tipo_membresia']):
        types = ['Standard', 'Premium', 'Executive', 'Business', 'Gold']
        return lambda: random.choice(types)
    if any(k in cn for k in ['nombre', 'name']):
        names = ['Ana García', 'Carlos López', 'María Rodríguez', 'José Martínez',
                 'Laura Hernández', 'Pedro Sánchez', 'Sofia Torres', 'Diego Ramírez',
                 'Valentina Cruz', 'Andrés Morales', 'Camila Flores', 'Luis Reyes']
        return lambda: random.choice(names)
    if any(k in cn for k in ['id', 'clave', 'code', 'key', 'folio', 'ref']):
        return lambda: f"{random.randint(10000, 99999)}"
    if any(k in cn for k in ['tipo', 'type', 'status', 'category', 'clasificacion']):
        options = ['Tipo A', 'Tipo B', 'Tipo C', 'Tipo D']
        return lambda: random.choice(options)
    if 'pct' in cn or 'percent' in cn or 'porcentaje' in cn or 'cumplimiento' in cn:
        return lambda: round(random.uniform(0, 100), 2)
    # Visitas / shops: enteros pequeños-medianos
    if any(k in cn for k in ['visits', 'visitas', 'shops', 'compras']):
        return lambda: random.randint(1, 50)
    # Transacciones
    if 'trxn' in cn or 'transac' in cn:
        return lambda: random.randint(0, 30)
    if any(k in cn for k in ['monto', 'amount', 'total', 'price', 'cost', 'sales', 'revenue', 'compensacion']):
        return lambda: round(random.uniform(100, 100000), 2)
    if any(k in cn for k in ['rfc']):
        return lambda: ''.join(random.choices(string.ascii_uppercase, k=4)) + str(random.randint(100000, 999999))
    if any(k in cn for k in ['version']):
        return lambda: f"{random.randint(1,5)}.{random.randint(0,9)}"
    if any(k in cn for k in ['warning', 'advertencia']):
        return lambda: random.choice(['', '', '', 'W001', 'W002'])
    if any(k in cn for k in ['year', 'anio', 'año']):
        return lambda: random.choice([2023, 2024, 2025, 2026])
    if any(k in cn for k in ['period', 'periodo', 'mes', 'month', 'week', 'semana']):
        return lambda: random.randint(1, 12)
    # Flags binarios: el LLM en paso 2 a veces traduce condiciones DAX como `flag = 'Y'`,
    # por lo que devolver 'Y'/'N' da matching parcial.
    if any(k in cn for k in ['flag', 'is_', 'has_', 'activo', 'active', 'enabled']):
        return lambda: random.choice(['Y', 'N'])
    # Counts pequeños: el LLM compara contra '0' y '1', por eso valores enteros bajos.
    if any(k in cn for k in ['count', '_count', 'cantidad', 'qty']):
        return lambda: random.randint(0, 5)

    # Detectar por tipo de dato
    if any(t in dt for t in ['int', 'long', 'whole']):
        return lambda: random.randint(0, 10000)
    if any(t in dt for t in ['double', 'decimal', 'float', 'currency', 'number']):
        return lambda: round(random.uniform(0, 100000), 2)
    if any(t in dt for t in ['bool']):
        return lambda: random.choice([True, False])
    if any(t in dt for t in ['date', 'time']):
        base = datetime(2024, 1, 1)
        return lambda: base + timedelta(days=random.randint(0, 730))

    # Default: string
    words = ['Alpha', 'Beta', 'Gamma', 'Delta', 'Epsilon', 'Zeta', 'Eta', 'Theta',
             'Iota', 'Kappa', 'Lambda', 'Mu', 'Nu', 'Xi', 'Omicron', 'Pi']
    return lambda: random.choice(words)


random.seed(42)
generated_tables = {}

for table_name, columns in tables_info.items():
    print(f"\n--- {table_name} ({len(columns)} cols, {ROWS} rows) ---")

    data = {}
    for col_info in columns:
        col_name = col_info['column']
        col_type = col_info['data_type']
        gen = pbi_type_to_generator(col_type, col_name)
        data[col_name] = [gen() for _ in range(ROWS)]

    df = pd.DataFrame(data)
    generated_tables[table_name] = df

    # Show sample
    print(f"  Columnas: {list(df.columns)[:8]}{'...' if len(df.columns) > 8 else ''}")
    print(f"  Sample:")
    display(df.head(3))

print(f"\n✓ {len(generated_tables)} tablas generadas en memoria")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Crear tablas en Unity Catalog

# COMMAND ----------

results = []

for table_name, df in generated_tables.items():
    # Limpiar nombre para UC (snake_case, sin espacios ni caracteres especiales)
    safe_name = table_name.lower().replace(' ', '_').replace('-', '_').replace('.', '_')
    safe_name = ''.join(c if c.isalnum() or c == '_' else '_' for c in safe_name)
    safe_name = safe_name.strip('_')

    full_name = f"{CATALOG}.{SCHEMA}.{safe_name}"

    # Limpiar nombres de columnas
    clean_df = df.copy()
    clean_cols = {}
    for c in clean_df.columns:
        clean = c.lower().replace(' ', '_').replace('-', '_').replace('.', '_')
        clean = ''.join(ch if ch.isalnum() or ch == '_' else '_' for ch in clean)
        clean = clean.strip('_')
        clean_cols[c] = clean
    clean_df = clean_df.rename(columns=clean_cols)

    try:
        # Check if exists
        exists = False
        try:
            spark.sql(f"SELECT 1 FROM {full_name} LIMIT 1").collect()
            exists = True
        except:
            pass

        if exists and not OVERWRITE:
            print(f"  SKIP {full_name} (ya existe, overwrite=false)")
            results.append({"table": full_name, "pbi_name": table_name, "status": "SKIP", "rows": 0})
            continue

        # Create — mantener tipos numéricos en columnas que claramente lo son.
        # Si todos los valores son numéricos válidos, NO los convertimos a string.
        for col in clean_df.columns:
            sample = clean_df[col].dropna()
            if len(sample) == 0:
                clean_df[col] = clean_df[col].astype(str)
                continue
            # Intentar convertir a numérico
            converted = pd.to_numeric(sample, errors='coerce')
            if converted.notna().sum() / len(sample) >= 0.95:
                # Mayoría son numéricos: mantener tipo numérico (float para flexibilidad)
                clean_df[col] = pd.to_numeric(clean_df[col], errors='coerce')
            else:
                clean_df[col] = clean_df[col].astype(str)
        sdf = spark.createDataFrame(clean_df)
        sdf.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(full_name)

        print(f"  ✓ {full_name} ({len(df)} rows, {len(df.columns)} cols)")
        results.append({"table": full_name, "pbi_name": table_name, "status": "OK", "rows": len(df)})

    except Exception as e:
        print(f"  ✗ {full_name}: {str(e)[:150]}")
        results.append({"table": full_name, "pbi_name": table_name, "status": f"FAIL: {str(e)[:100]}", "rows": 0})

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Guardar mapeo de tablas

# COMMAND ----------

# Guardar el mapeo PBI table → UC table para referencia
mapping_rows = []
for table_name, columns in tables_info.items():
    safe_name = table_name.lower().replace(' ', '_').replace('-', '_').replace('.', '_')
    safe_name = ''.join(c if c.isalnum() or c == '_' else '_' for c in safe_name).strip('_')
    full_name = f"{CATALOG}.{SCHEMA}.{safe_name}"

    for col in columns:
        clean_col = col['column'].lower().replace(' ', '_').replace('-', '_')
        clean_col = ''.join(c if c.isalnum() or c == '_' else '_' for c in clean_col).strip('_')
        mapping_rows.append({
            'pbi_table': table_name,
            'uc_table': full_name,
            'pbi_column': col['column'],
            'uc_column': clean_col,
            'data_type': col['data_type'],
        })

mapping_df = pd.DataFrame(mapping_rows)
spark.createDataFrame(mapping_df).write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{CATALOG}.{SCHEMA}.pbi_table_mapping")
print(f"✓ Mapeo guardado en {CATALOG}.{SCHEMA}.pbi_table_mapping ({len(mapping_rows)} columnas)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Resumen

# COMMAND ----------

results_df = pd.DataFrame(results)
ok = sum(1 for r in results if r['status'] == 'OK')
skip = sum(1 for r in results if r['status'] == 'SKIP')
fail = len(results) - ok - skip

print(f"{'='*60}")
print(f"TABLAS GENERADAS")
print(f"{'='*60}")
print(f"PBIX: {PBIX_PATH}")
print(f"Destino: {CATALOG}.{SCHEMA}")
print(f"OK: {ok} | SKIP: {skip} | FAIL: {fail}")
print()
for r in results:
    icon = "✓" if r['status'] == 'OK' else "⊘" if r['status'] == 'SKIP' else "✗"
    print(f"  {icon} {r['pbi_name']} → {r['table']} ({r['rows']} rows)")

print(f"\nMapeo: {CATALOG}.{SCHEMA}.pbi_table_mapping")
display(results_df)
