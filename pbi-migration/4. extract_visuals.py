# Databricks notebook source
# MAGIC %md
# MAGIC # Extraer Visuales del Power BI
# MAGIC
# MAGIC Lee el Report/Layout del .pbix y extrae todos los objetos gráficos
# MAGIC con sus columnas, measures y roles. Permite cruzar con las Metrics Views generadas.

# COMMAND ----------

# MAGIC %pip install pbixray
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Leer el Layout del PBIX

# COMMAND ----------

import io, json, re, zipfile
import pandas as pd

dbutils.widgets.text("pbix_path", "/Volumes/<your_catalog>/<your_schema>/pbix/<your_dashboard>.pbix", "Path del .pbix")
dbutils.widgets.text("catalog", "pbi_migration", "Catálogo destino")
dbutils.widgets.text("schema", "couch", "Schema destino")

pbix_path = dbutils.widgets.get("pbix_path")
CATALOG = dbutils.widgets.get("catalog")
SCHEMA = dbutils.widgets.get("schema")

with open(pbix_path, 'rb') as f:
    pbix_bytes = f.read()

with zipfile.ZipFile(io.BytesIO(pbix_bytes)) as zf:
    raw = zf.read('Report/Layout')
    text = raw.decode('utf-16-le')
    if text[0] == '\ufeff':
        text = text[1:]
    layout = json.loads(text)

sections = layout.get('sections', [])
print(f"PBIX: {pbix_path}")
print(f"Páginas: {len(sections)}")
for s in sections:
    print(f"  - {s.get('displayName', '?')} ({len(s.get('visualContainers', []))} visuales)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Extraer todos los visuales con sus campos

# COMMAND ----------

def get_alias_map(query):
    """Mapea alias (Name) a tabla real (Entity) desde la sección From del query."""
    return {frm.get("Name", ""): frm.get("Entity", "") for frm in query.get("From", [])}

def extract_fields_from_select(select_list, alias_map):
    """Extrae columnas y measures de la lista Select de un prototypeQuery."""
    fields = []
    for sel in select_list:
        name = sel.get("Name", "")

        # Columna
        if "Column" in sel:
            item = sel["Column"]
            src = item.get("Expression", {}).get("SourceRef", {})
            source_alias = src.get("Source", "")
            entity = src.get("Entity", alias_map.get(source_alias, source_alias))
            prop = item.get("Property", "")
            fields.append({
                'field_type': 'Column',
                'table': entity,
                'column': prop,
                'measure_name': '',
                'display_name': name,
            })

        # Measure
        elif "Measure" in sel:
            item = sel["Measure"]
            src = item.get("Expression", {}).get("SourceRef", {})
            source_alias = src.get("Source", "")
            entity = src.get("Entity", alias_map.get(source_alias, source_alias))
            prop = item.get("Property", "")
            fields.append({
                'field_type': 'Measure',
                'table': entity,
                'column': '',
                'measure_name': prop,
                'display_name': name,
            })

        # Aggregation (columna con agregación implícita)
        elif "Aggregation" in sel:
            item = sel["Aggregation"]
            expr = item.get("Expression", {})
            if "Column" in expr:
                col = expr["Column"]
                src = col.get("Expression", {}).get("SourceRef", {})
                source_alias = src.get("Source", "")
                entity = src.get("Entity", alias_map.get(source_alias, source_alias))
                prop = col.get("Property", "")
                agg_func = item.get("Function", 0)
                agg_names = {0: "SUM", 1: "AVG", 2: "COUNT", 3: "MIN", 4: "MAX", 5: "COUNTDISTINCT"}
                fields.append({
                    'field_type': f'Aggregation({agg_names.get(agg_func, agg_func)})',
                    'table': entity,
                    'column': prop,
                    'measure_name': '',
                    'display_name': name,
                })

    return fields

def extract_roles(config):
    """Extrae los roles (Category, Y, Series, Tooltips, etc.) de las projections."""
    sv = config.get("singleVisual", {})
    projections = sv.get("projections", {})
    roles = {}
    # projections es un dict: {"Category": [{"queryRef": "..."}], "Y": [...], ...}
    for role_name, role_items in projections.items():
        if isinstance(role_items, list):
            for item in role_items:
                qref = item.get("queryRef", "")
                if qref:
                    roles[qref] = role_name
    return roles

# Extraer todos los visuales
visual_rows = []
field_rows = []
visual_filter_rows_all = []  # para tabla pbi_visual_filters
visual_id = 0

for section in sections:
    page_name = section.get("displayName", "?")
    page_order = section.get("ordinal", 0)

    for vc in section.get("visualContainers", []):
        visual_id += 1
        config = json.loads(vc.get("config", "{}"))
        sv = config.get("singleVisual", {})
        visual_type = sv.get("visualType", "unknown")
        title = ""
        title_obj = sv.get("vcObjects", {}).get("title", [])
        if title_obj:
            for t in title_obj:
                props = t.get("properties", {})
                text_prop = props.get("text", {})
                if "expr" in text_prop:
                    title = str(text_prop.get("expr", {}).get("Literal", {}).get("Value", ""))
                    title = title.strip("'\"")

        # Si es textbox, extraer su contenido textual desde objects.general[*].paragraphs
        if visual_type == "textbox":
            text_lines = []
            objs = sv.get("objects", {})
            for gen in objs.get("general", []):
                paras = gen.get("properties", {}).get("paragraphs", [])
                for para in paras:
                    line_parts = []
                    for tr in para.get("textRuns", []):
                        v = tr.get("value", "")
                        if v:
                            line_parts.append(str(v))
                    if line_parts:
                        text_lines.append("".join(line_parts))
            textbox_content = "\n".join(text_lines).strip()
            if textbox_content:
                title = textbox_content[:500]  # cap a 500 chars para evitar títulos gigantes

        # Posición
        x = vc.get("x", 0)
        y = vc.get("y", 0)
        width = vc.get("width", 0)
        height = vc.get("height", 0)

        # Query y campos
        query = sv.get("prototypeQuery", {})
        alias_map = get_alias_map(query)
        select_list = query.get("Select", [])
        fields = extract_fields_from_select(select_list, alias_map)
        roles = extract_roles(config)

        # Filtros del visual: parsear expression.Column + filter.Where con valores
        visual_filters = []
        visual_filter_rows = []  # detalle estructurado para tabla pbi_visual_filters
        filters_json = vc.get("filters", "[]")
        try:
            vf = json.loads(filters_json) if isinstance(filters_json, str) else filters_json
            for filt in vf:
                # La columna filtrada vive en filt['expression']['Column']
                expr = filt.get("expression", {})
                col = expr.get("Column", {})
                if not col:
                    # también puede ser Measure o HierarchyLevel - skip por ahora
                    continue
                src = col.get("Expression", {}).get("SourceRef", {})
                entity = src.get("Entity", alias_map.get(src.get("Source", ""), ""))
                prop = col.get("Property", "")

                # Extraer valores del filtro desde filter.Where[*].Condition
                values = []
                operator = "UNKNOWN"
                where_clauses = filt.get("filter", {}).get("Where", [])
                for w in where_clauses:
                    cond = w.get("Condition", {})

                    # IN - lista de valores permitidos
                    if "In" in cond:
                        operator = "IN"
                        in_clause = cond["In"]
                        for val_set in in_clause.get("Values", []):
                            for val in val_set:
                                lit = val.get("Literal", {}).get("Value", "")
                                if lit:
                                    values.append(str(lit).strip("'\""))

                    # Not con In adentro - lista de valores excluidos
                    elif "Not" in cond:
                        inner = cond["Not"].get("Expression", {})
                        if "In" in inner:
                            operator = "NOT IN"
                            for val_set in inner["In"].get("Values", []):
                                for val in val_set:
                                    lit = val.get("Literal", {}).get("Value", "")
                                    if lit:
                                        values.append(str(lit).strip("'\""))

                    # Comparison (=, >, <, etc.)
                    elif "Comparison" in cond:
                        comp = cond["Comparison"]
                        kind = comp.get("ComparisonKind", 0)
                        # 0=Equal, 1=GreaterThan, 2=GreaterOrEqual, 3=LessThan, 4=LessOrEqual
                        op_map = {0: "=", 1: ">", 2: ">=", 3: "<", 4: "<="}
                        operator = op_map.get(kind, "=")
                        right = comp.get("Right", {})
                        lit = right.get("Literal", {}).get("Value", "")
                        if lit:
                            values.append(str(lit).strip("'\""))

                if entity and prop:
                    visual_filters.append(f"{entity}.{prop} {operator} {values}" if values else f"{entity}.{prop}")
                    visual_filter_rows.append({
                        'visual_id': visual_id,
                        'page': page_name,
                        'table': entity,
                        'column': prop,
                        'operator': operator,
                        'values': "|".join(values),
                    })
        except Exception as e:
            print(f"  WARN visual {visual_id}: {str(e)[:100]}")

        visual_rows.append({
            'visual_id': visual_id,
            'page': page_name,
            'page_order': page_order,
            'visual_type': visual_type,
            'title': title,
            'x': x, 'y': y, 'width': width, 'height': height,
            'num_fields': len(fields),
            'measures_used': ", ".join([f['measure_name'] for f in fields if f['field_type'] == 'Measure']),
            'columns_used': ", ".join([f"{f['table']}.{f['column']}" for f in fields if f['field_type'] == 'Column']),
            'visual_filters': ", ".join(visual_filters) if visual_filters else "",
        })

        # Acumular filas detalladas de filtros
        visual_filter_rows_all.extend(visual_filter_rows)

        for f in fields:
            # Asignar rol
            role = roles.get(f['display_name'], '')
            field_rows.append({
                'visual_id': visual_id,
                'page': page_name,
                'visual_type': visual_type,
                'title': title,
                'field_type': f['field_type'],
                'table': f['table'],
                'column': f['column'],
                'measure_name': f['measure_name'],
                'role': role,
                'display_name': f['display_name'],
            })

visuals_df = pd.DataFrame(visual_rows)
fields_df = pd.DataFrame(field_rows)

print(f"{len(visuals_df)} visuales extraídos")
print(f"{len(fields_df)} campos en total")
print(f"\nTipos de visual:")
print(visuals_df['visual_type'].value_counts().to_string())

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Visuales por página

# COMMAND ----------

display(visuals_df)

# COMMAND ----------

display(fields_df)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Guardar en Unity Catalog

# COMMAND ----------

def clean_cols(df):
    import re as _re
    def _clean(c):
        for a, b in [('á','a'),('é','e'),('í','i'),('ó','o'),('ú','u'),('ñ','n'),('Á','A'),('É','E'),('Í','I'),('Ó','O'),('Ú','U'),('Ñ','N')]:
            c = c.replace(a, b)
        c = c.replace(" ", "_").replace("#", "Num").replace("%", "Pct")
        c = _re.sub(r'[^a-zA-Z0-9_]', '_', c)
        while '__' in c:
            c = c.replace('__', '_')
        c = c.strip('_')
        return c
    return df.rename(columns=_clean)

spark.createDataFrame(clean_cols(visuals_df).astype(str)).write.mode("overwrite").saveAsTable(f"{CATALOG}.{SCHEMA}.pbi_visuals")
print(f"✓ {CATALOG}.{SCHEMA}.pbi_visuals ({len(visuals_df)} filas)")

spark.createDataFrame(clean_cols(fields_df).astype(str)).write.mode("overwrite").saveAsTable(f"{CATALOG}.{SCHEMA}.pbi_visual_fields")
print(f"✓ {CATALOG}.{SCHEMA}.pbi_visual_fields ({len(fields_df)} filas)")

# Guardar tabla detallada de filtros por visual (para que paso 5 los aplique)
if visual_filter_rows_all:
    visual_filters_df = pd.DataFrame(visual_filter_rows_all)
    spark.createDataFrame(visual_filters_df.astype(str)).write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{CATALOG}.{SCHEMA}.pbi_visual_filters")
    print(f"✓ {CATALOG}.{SCHEMA}.pbi_visual_filters ({len(visual_filter_rows_all)} filas)")
else:
    # Crear tabla vacía con schema esperado para que paso 5 no falle
    empty_df = pd.DataFrame(columns=['visual_id','page','table','column','operator','values'])
    spark.createDataFrame(empty_df.astype(str)).write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{CATALOG}.{SCHEMA}.pbi_visual_filters")
    print(f"✓ {CATALOG}.{SCHEMA}.pbi_visual_filters (vacía)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Extraer colores y fuentes del tema Power BI

# COMMAND ----------

# Extraer tema del reporte
report_config = layout.get("config", "{}")
if isinstance(report_config, str):
    report_config = json.loads(report_config)

style_rows = []

# 1. Tema base del .pbix (SharedResources)
theme_json = None
with zipfile.ZipFile(io.BytesIO(pbix_bytes)) as zf:
    for name in zf.namelist():
        if 'BaseThemes' in name or 'SharedResources' in name:
            if name.endswith('.json'):
                try:
                    theme_json = json.loads(zf.read(name).decode('utf-8'))
                    print(f"Tema encontrado: {name}")
                except:
                    pass

# Extraer paleta de colores del tema
if theme_json:
    # dataColors — paleta principal de series
    data_colors = theme_json.get("dataColors", [])
    for i, color in enumerate(data_colors):
        style_rows.append({
            'category': 'theme_palette',
            'property': f'dataColor_{i}',
            'value': color,
            'source': 'BaseTheme',
        })

    # foreground/background
    for key in ['foreground', 'background', 'foregroundNeutralSecondary', 'foregroundNeutralTertiary', 'backgroundLight', 'backgroundNeutral', 'tableAccent']:
        val = theme_json.get(key, '')
        if val:
            style_rows.append({
                'category': 'theme_color',
                'property': key,
                'value': val,
                'source': 'BaseTheme',
            })

    # Fuentes del tema
    for font_key in ['fontFamily', 'textSizeSmall', 'textSizeMedium', 'textSizeLarge', 'textSizeExtraLarge']:
        val = theme_json.get(font_key, '')
        if val:
            style_rows.append({
                'category': 'theme_font',
                'property': font_key,
                'value': str(val),
                'source': 'BaseTheme',
            })

    # visualStyles del tema (colores por tipo de visual)
    visual_styles = theme_json.get("visualStyles", {})
    for vtype, vstyle in visual_styles.items():
        if isinstance(vstyle, dict):
            for section_name, section in vstyle.items():
                if isinstance(section, dict):
                    for prop_group, props in section.items():
                        if isinstance(props, dict):
                            for prop_name, prop_val in props.items():
                                if isinstance(prop_val, dict) and 'solid' in prop_val:
                                    color = prop_val['solid'].get('color', '')
                                    if color:
                                        style_rows.append({
                                            'category': 'visual_style',
                                            'property': f'{vtype}.{section_name}.{prop_group}.{prop_name}',
                                            'value': color,
                                            'source': 'BaseTheme',
                                        })

# 2. Colores y fuentes por visual individual
for section in sections:
    page_name = section.get("displayName", "?")
    for vc in section.get("visualContainers", []):
        config = json.loads(vc.get("config", "{}"))
        sv = config.get("singleVisual", {})
        vtype = sv.get("visualType", "unknown")
        objects = sv.get("objects", {})

        for obj_name, obj_list in objects.items():
            if not isinstance(obj_list, list):
                continue
            for obj in obj_list:
                props = obj.get("properties", {})
                for prop_name, prop_val in props.items():
                    # Colores (solid.color)
                    if isinstance(prop_val, dict):
                        solid = prop_val.get("solid", {})
                        if 'color' in solid:
                            color_expr = solid['color']
                            if isinstance(color_expr, dict) and 'Literal' in color_expr.get('expr', {}):
                                color = color_expr['expr']['Literal'].get('Value', '')
                                color = color.strip("'\"")
                                if color and color.startswith('#'):
                                    style_rows.append({
                                        'category': 'visual_color',
                                        'property': f'{obj_name}.{prop_name}',
                                        'value': color,
                                        'source': f'{page_name}/{vtype}',
                                    })
                        # Fuentes
                        if 'expr' in prop_val:
                            expr = prop_val['expr']
                            if isinstance(expr, dict) and 'Literal' in expr:
                                val = str(expr['Literal'].get('Value', ''))
                                val = val.strip("'\"")
                                if prop_name in ('fontFamily', 'fontSize', 'fontColor', 'font', 'textSize'):
                                    style_rows.append({
                                        'category': 'visual_font',
                                        'property': f'{obj_name}.{prop_name}',
                                        'value': val,
                                        'source': f'{page_name}/{vtype}',
                                    })

styles_df = pd.DataFrame(style_rows)

# Resumen
print(f"\n{len(styles_df)} propiedades de estilo extraídas:")
if not styles_df.empty:
    print(styles_df['category'].value_counts().to_string())

    # Paleta de colores
    palette = styles_df[styles_df['category'] == 'theme_palette']
    if not palette.empty:
        print(f"\nPaleta de colores del tema ({len(palette)} colores):")
        for _, row in palette.iterrows():
            print(f"  {row['property']}: {row['value']}")

    # Fuentes
    fonts = styles_df[styles_df['category'].isin(['theme_font', 'visual_font'])]
    if not fonts.empty:
        print(f"\nFuentes:")
        for _, row in fonts.drop_duplicates(subset=['property', 'value']).iterrows():
            print(f"  {row['property']}: {row['value']}")

    # Colores únicos usados en visuales
    vis_colors = styles_df[styles_df['category'] == 'visual_color']['value'].unique()
    if len(vis_colors) > 0:
        print(f"\nColores únicos en visuales ({len(vis_colors)}):")
        for c in sorted(vis_colors):
            print(f"  {c}")

display(styles_df)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Guardar estilos en Unity Catalog

# COMMAND ----------

if not styles_df.empty:
    spark.createDataFrame(styles_df.astype(str)).write.mode("overwrite").saveAsTable(f"{CATALOG}.{SCHEMA}.pbi_styles")
    print(f"✓ {CATALOG}.{SCHEMA}.pbi_styles ({len(styles_df)} filas)")
else:
    print("No se encontraron estilos para guardar")
