# Databricks notebook source
# MAGIC %md
# MAGIC # Extraer Propiedades Avanzadas de Visuales Power BI
# MAGIC
# MAGIC Extrae sort, conditional formatting, visual links y column properties
# MAGIC del Report/Layout del .pbix. Complementa el notebook `4. extract_visuals`.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Parámetros

# COMMAND ----------

import io, json, zipfile
import pandas as pd

dbutils.widgets.text("pbix_path", "/Volumes/<your_catalog>/<your_schema>/pbix/<your_dashboard>.pbix", "Path del .pbix")
dbutils.widgets.text("catalog", "pbi_migration", "Catálogo destino")
dbutils.widgets.text("schema", "default", "Schema destino")

pbix_path = dbutils.widgets.get("pbix_path")
CATALOG = dbutils.widgets.get("catalog")
SCHEMA = dbutils.widgets.get("schema")

with open(pbix_path, 'rb') as f:
    pbix_bytes = f.read()

with zipfile.ZipFile(io.BytesIO(pbix_bytes)) as zf:
    raw = zf.read('Report/Layout')
    text = raw.decode('utf-16-le').lstrip('\ufeff')
    layout = json.loads(text)

sections = layout.get('sections', [])
print(f"PBIX: {pbix_path}")
print(f"Páginas: {len(sections)}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Extraer Sort

# COMMAND ----------

def get_alias_map(query):
    return {frm.get("Name", ""): frm.get("Entity", "") for frm in query.get("From", [])}

sort_rows = []
visual_id = 0

for section in sections:
    page_name = section.get("displayName", "?")
    for vc in section.get("visualContainers", []):
        visual_id += 1
        config = json.loads(vc.get("config", "{}"))
        sv = config.get("singleVisual", {})
        visual_type = sv.get("visualType", "unknown")

        # Sort del prototypeQuery (OrderBy)
        query = sv.get("prototypeQuery", {})
        alias_map = get_alias_map(query)
        order_by = query.get("OrderBy", [])

        for i, ob in enumerate(order_by):
            direction = "ascending" if ob.get("Direction", 1) == 1 else "descending"
            expr = ob.get("Expression", {})

            sort_field = ""
            sort_table = ""
            if "Column" in expr:
                col = expr["Column"]
                src = col.get("Expression", {}).get("SourceRef", {})
                sort_table = src.get("Entity", alias_map.get(src.get("Source", ""), ""))
                sort_field = col.get("Property", "")
            elif "Measure" in expr:
                m = expr["Measure"]
                src = m.get("Expression", {}).get("SourceRef", {})
                sort_table = src.get("Entity", alias_map.get(src.get("Source", ""), ""))
                sort_field = m.get("Property", "")
            elif "Aggregation" in expr:
                agg = expr["Aggregation"]
                inner = agg.get("Expression", {})
                if "Column" in inner:
                    col = inner["Column"]
                    src = col.get("Expression", {}).get("SourceRef", {})
                    sort_table = src.get("Entity", alias_map.get(src.get("Source", ""), ""))
                    sort_field = col.get("Property", "")

            if sort_field:
                sort_rows.append({
                    'visual_id': visual_id,
                    'page': page_name,
                    'visual_type': visual_type,
                    'sort_order': i + 1,
                    'sort_field': f"{sort_table}.{sort_field}" if sort_table else sort_field,
                    'direction': direction,
                    'source': 'prototypeQuery.OrderBy',
                })

        # hasDefaultSort flag
        if sv.get("hasDefaultSort"):
            # Buscar sort en dataTransforms
            dt = vc.get("dataTransforms")
            if dt:
                if isinstance(dt, str):
                    dt = json.loads(dt)
                sorts = dt.get("sorts", [])
                for i, s in enumerate(sorts):
                    field_ref = s.get("field", {})
                    direction = "ascending" if s.get("direction", 1) == 1 else "descending"
                    sort_field = ""
                    sort_table = ""
                    if "Column" in field_ref:
                        col = field_ref["Column"]
                        src = col.get("Expression", {}).get("SourceRef", {})
                        sort_table = src.get("Entity", "")
                        sort_field = col.get("Property", "")
                    elif "Measure" in field_ref:
                        m = field_ref["Measure"]
                        src = m.get("Expression", {}).get("SourceRef", {})
                        sort_table = src.get("Entity", "")
                        sort_field = m.get("Property", "")
                    if sort_field:
                        sort_rows.append({
                            'visual_id': visual_id,
                            'page': page_name,
                            'visual_type': visual_type,
                            'sort_order': i + 1,
                            'sort_field': f"{sort_table}.{sort_field}" if sort_table else sort_field,
                            'direction': direction,
                            'source': 'dataTransforms.sorts',
                        })

sort_df = pd.DataFrame(sort_rows)
print(f"Sort rules extraídos: {len(sort_df)}")
if not sort_df.empty:
    display(sort_df)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Extraer Conditional Formatting

# COMMAND ----------

cond_rows = []
visual_id = 0

for section in sections:
    page_name = section.get("displayName", "?")
    for vc in section.get("visualContainers", []):
        visual_id += 1
        config = json.loads(vc.get("config", "{}"))
        sv = config.get("singleVisual", {})
        visual_type = sv.get("visualType", "unknown")
        objects = sv.get("objects", {})

        for obj_name, obj_list in objects.items():
            if not isinstance(obj_list, list):
                continue
            for obj in obj_list:
                props = obj.get("properties", {})
                selector = obj.get("selector", {})

                for prop_name, prop_val in props.items():
                    if not isinstance(prop_val, dict):
                        continue

                    # Conditional formatting: look for rules or gradient
                    expr = prop_val.get("expr", {})
                    solid = prop_val.get("solid", {})

                    # Rule-based conditional formatting
                    if isinstance(expr, dict) and "Conditional" in expr:
                        cond = expr["Conditional"]
                        cases = cond.get("Cases", [])
                        for case in cases:
                            condition = case.get("Condition", {})
                            value = case.get("Value", {}).get("Literal", {}).get("Value", "")
                            cond_rows.append({
                                'visual_id': visual_id,
                                'page': page_name,
                                'visual_type': visual_type,
                                'object': obj_name,
                                'property': prop_name,
                                'format_type': 'rule',
                                'value': str(value).strip("'\""),
                                'condition': json.dumps(condition, ensure_ascii=False)[:200],
                                'selector': json.dumps(selector, ensure_ascii=False)[:100] if selector else "",
                            })

                    # FillRule (gradient / color scale)
                    if "FillRule" in expr if isinstance(expr, dict) else False:
                        fill_rule = expr["FillRule"]
                        input_ref = fill_rule.get("Input", {})
                        rule = fill_rule.get("FillRule", {})
                        # Extract min/mid/max colors
                        for point in ["Min", "Mid", "Max"]:
                            point_data = rule.get(point, {})
                            color = point_data.get("Value", point_data.get("Literal", {}).get("Value", ""))
                            if color:
                                cond_rows.append({
                                    'visual_id': visual_id,
                                    'page': page_name,
                                    'visual_type': visual_type,
                                    'object': obj_name,
                                    'property': prop_name,
                                    'format_type': f'gradient_{point.lower()}',
                                    'value': str(color).strip("'\""),
                                    'condition': json.dumps(input_ref, ensure_ascii=False)[:200],
                                    'selector': json.dumps(selector, ensure_ascii=False)[:100] if selector else "",
                                })

                    # Solid color with expression (dynamic color)
                    if solid:
                        color_val = solid.get("color", {})
                        if isinstance(color_val, dict) and "expr" in color_val:
                            inner_expr = color_val["expr"]
                            if "Conditional" in inner_expr or "FillRule" in inner_expr:
                                cond_rows.append({
                                    'visual_id': visual_id,
                                    'page': page_name,
                                    'visual_type': visual_type,
                                    'object': obj_name,
                                    'property': prop_name,
                                    'format_type': 'dynamic_color',
                                    'value': '',
                                    'condition': json.dumps(inner_expr, ensure_ascii=False)[:200],
                                    'selector': json.dumps(selector, ensure_ascii=False)[:100] if selector else "",
                                })

cond_df = pd.DataFrame(cond_rows)
print(f"Conditional formatting rules extraídos: {len(cond_df)}")
if not cond_df.empty:
    display(cond_df)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Extraer Visual Links (drill-through / navegación)

# COMMAND ----------

link_rows = []
visual_id = 0

for section in sections:
    page_name = section.get("displayName", "?")
    for vc in section.get("visualContainers", []):
        visual_id += 1
        config = json.loads(vc.get("config", "{}"))
        sv = config.get("singleVisual", {})
        visual_type = sv.get("visualType", "unknown")

        # visualLink in vcObjects
        vc_objects = sv.get("vcObjects", {})
        visual_links = vc_objects.get("visualLink", [])
        for vl in visual_links:
            props = vl.get("properties", {})
            nav_type = ""
            target_page = ""
            url = ""

            # Navigation type
            nav_val = props.get("type", {}).get("expr", {}).get("Literal", {}).get("Value", "")
            if nav_val:
                nav_type = str(nav_val).strip("'\"")

            # Target page (for page navigation)
            show_val = props.get("show", {}).get("expr", {}).get("Literal", {}).get("Value", "")
            if show_val:
                target_page = str(show_val).strip("'\"")

            link_rows.append({
                'visual_id': visual_id,
                'page': page_name,
                'visual_type': visual_type,
                'nav_type': nav_type,
                'target_page': target_page,
            })

link_df = pd.DataFrame(link_rows)
print(f"Visual links extraídos: {len(link_df)}")
if not link_df.empty:
    display(link_df)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Extraer Column Properties (formato de columnas en tablas)

# COMMAND ----------

colprop_rows = []
visual_id = 0

for section in sections:
    page_name = section.get("displayName", "?")
    for vc in section.get("visualContainers", []):
        visual_id += 1
        config = json.loads(vc.get("config", "{}"))
        sv = config.get("singleVisual", {})
        visual_type = sv.get("visualType", "unknown")

        col_props = sv.get("columnProperties", {})
        for col_name, col_config in col_props.items():
            width = ""
            alignment = ""
            if isinstance(col_config, dict):
                width = col_config.get("width", "")
                align_val = col_config.get("alignment", "")
                if isinstance(align_val, dict):
                    alignment = str(align_val.get("expr", {}).get("Literal", {}).get("Value", "")).strip("'\"")
                else:
                    alignment = str(align_val)

            colprop_rows.append({
                'visual_id': visual_id,
                'page': page_name,
                'visual_type': visual_type,
                'column_name': col_name,
                'width': str(width) if width else "",
                'alignment': alignment if alignment else "",
            })

colprop_df = pd.DataFrame(colprop_rows)
print(f"Column properties extraídos: {len(colprop_df)}")
if not colprop_df.empty:
    display(colprop_df)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Consolidar y guardar en una sola tabla

# COMMAND ----------

# Normalizar todas las propiedades a un esquema común
all_props = []

# Sort
for _, r in sort_df.iterrows():
    all_props.append({
        'visual_id': str(r['visual_id']),
        'page': r['page'],
        'visual_type': r['visual_type'],
        'property_type': 'sort',
        'key': r['sort_field'],
        'value': r['direction'],
        'detail': f"order:{r['sort_order']} source:{r['source']}",
    })

# Conditional formatting
for _, r in cond_df.iterrows():
    all_props.append({
        'visual_id': str(r['visual_id']),
        'page': r['page'],
        'visual_type': r['visual_type'],
        'property_type': 'cond_format',
        'key': f"{r['object']}.{r['property']}",
        'value': r['value'],
        'detail': f"type:{r['format_type']} condition:{r['condition']}",
    })

# Visual links
for _, r in link_df.iterrows():
    all_props.append({
        'visual_id': str(r['visual_id']),
        'page': r['page'],
        'visual_type': r['visual_type'],
        'property_type': 'visual_link',
        'key': r['nav_type'],
        'value': r['target_page'],
        'detail': '',
    })

# Column properties
for _, r in colprop_df.iterrows():
    all_props.append({
        'visual_id': str(r['visual_id']),
        'page': r['page'],
        'visual_type': r['visual_type'],
        'property_type': 'column_prop',
        'key': r['column_name'],
        'value': f"width:{r['width']}" if r['width'] else "",
        'detail': f"align:{r['alignment']}" if r['alignment'] else "",
    })

props_df = pd.DataFrame(all_props)
print(f"Total propiedades consolidadas: {len(props_df)}")
if not props_df.empty:
    print(props_df['property_type'].value_counts().to_string())
    display(props_df)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. Guardar en Unity Catalog

# COMMAND ----------

TABLE_NAME = f"{CATALOG}.{SCHEMA}.pbi_visual_props"

if not props_df.empty:
    spark.createDataFrame(props_df.astype(str)).write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(TABLE_NAME)
    print(f"✓ {TABLE_NAME} ({len(props_df)} filas)")
else:
    print("— No hay propiedades para guardar")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 8. Resumen

# COMMAND ----------

print(f"{'='*60}")
print(f"PROPIEDADES EXTRAÍDAS → {TABLE_NAME}")
print(f"{'='*60}")
print(f"  Sort rules:              {len(sort_df)}")
print(f"  Conditional formatting:  {len(cond_df)}")
print(f"  Visual links:            {len(link_df)}")
print(f"  Column properties:       {len(colprop_df)}")
print(f"  {'─'*40}")
print(f"  TOTAL:                   {len(props_df)}")

