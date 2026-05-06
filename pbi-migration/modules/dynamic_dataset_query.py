"""
Bug 10: el dataset query del dashboard tiene una lista hardcoded de measures.
Si después se agregan measures a la metric view, el dashboard no las ve.

Este módulo construye el dataset query DINÁMICAMENTE leyendo dimensiones y
measures del estado vivo de la metric view (DESCRIBE EXTENDED).

Llamar desde notebook 3 (`create_dashboard_semantic.py`) en lugar de hardcodear.
"""

import yaml


def build_dataset_query(spark, catalog, schema, mv_name, bust_timestamp=None):
    """
    Lee la definición de la metric view y construye un SELECT dinámico.

    Returns: list of strings (queryLines format esperado por Lakeview).
    """
    if bust_timestamp is None:
        import time
        bust_timestamp = int(time.time())

    # Leer YAML de la metric view del estado vivo
    desc_rows = spark.sql(
        f"DESCRIBE EXTENDED {catalog}.{schema}.{mv_name}"
    ).collect()
    yaml_text = next(
        (r['data_type'] for r in desc_rows if r['col_name'] == 'View Text'),
        None
    )
    if not yaml_text:
        raise ValueError(f"No se pudo leer YAML de {catalog}.{schema}.{mv_name}")

    parsed = yaml.safe_load(yaml_text)
    dims = [d['name'] for d in parsed.get('dimensions', [])]
    measures = [m['name'] for m in parsed.get('measures', [])]

    # Heuristic: cuáles dimensions son temporales (deberían ser STRING en outer)
    # Por simplicidad, todas las dimensions las convertimos a STRING en el outer.
    # Excepción: dimensions que ya son STRING quedan iguales.
    outer_dims = [
        f'TRY_CAST(`{d}` AS STRING) as `{d}`'
        for d in dims
    ]
    outer_measures = [f'`{m}`' for m in measures]

    inner_dims = [f'`{d}`' for d in dims]
    inner_measures = [
        f'TRY_CAST(MEASURE(`{m}`) AS DOUBLE) as `{m}`'
        for m in measures
    ]

    sql = f"""-- bust: {bust_timestamp}
SELECT
    {','.join(chr(10) + '    ' + c for c in (outer_dims + outer_measures)).lstrip()}
FROM (
    SELECT
      {','.join(chr(10) + '      ' + c for c in (inner_dims + inner_measures)).lstrip()}
    FROM {catalog}.{schema}.{mv_name}
    GROUP BY
      {','.join(chr(10) + '      ' + d for d in inner_dims).lstrip()}
)"""

    # Convertir a queryLines (cada línea con \n al final)
    return [l + '\n' for l in sql.split('\n')[:-1]] + (
        [sql.split('\n')[-1]] if sql.split('\n')[-1] else []
    )


def patch_dataset_in_dashboard(dashboard_dict, spark, catalog, schema, mv_name,
                                dataset_name='ds_howyoudrivesales'):
    """
    Reemplaza el queryLines del dataset en el dashboard con uno dinámico.
    Modifica in-place y retorna.
    """
    new_lines = build_dataset_query(spark, catalog, schema, mv_name)
    for ds in dashboard_dict.get('datasets', []):
        if ds.get('name') == dataset_name:
            ds['queryLines'] = new_lines
    return dashboard_dict
