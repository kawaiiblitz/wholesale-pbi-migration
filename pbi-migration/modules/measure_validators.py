"""
Validadores determinísticos para measures generadas por LLM en notebook 2.

Detectan y AUTO-CORRIGEN bugs comunes (sin volver a llamar al LLM):
- SUM/AVG sobre columnas STRING → reemplaza por COUNT(*)
- Divisiones sin NULLIF → auto-envuelve denominador
- THEN <flag_string> en CASE WHEN → reemplaza por THEN 1

El principio: nada hardcoded. Lee el schema vivo del source para saber
qué columnas son STRING.
"""

import re


def fix_measure_expression(expr, source_columns_types):
    """
    Aplica todos los auto-fixes a la expresión de una measure.
    `source_columns_types` es dict {col_name: 'STRING'/'BIGINT'/...}.
    Retorna (expr_corregida, list_de_fixes_aplicados).
    """
    fixes = []
    original = expr

    expr, applied = _fix_sum_of_strings(expr, source_columns_types)
    fixes.extend(applied)

    expr, applied = _fix_division_without_nullif(expr)
    fixes.extend(applied)

    expr, applied = _fix_then_string_flag(expr, source_columns_types)
    fixes.extend(applied)

    return expr, fixes


def _fix_sum_of_strings(expr, columns_types):
    """SUM(col)/AVG(col) donde col es STRING → COUNT(*)."""
    fixes = []
    string_cols = {c for c, t in columns_types.items()
                   if t.upper() == 'STRING'}

    for fn in ['SUM', 'AVG']:
        pattern = rf'{fn}\(`?(\w+)`?\)'
        for m in re.finditer(pattern, expr):
            col = m.group(1)
            if col in string_cols:
                expr = expr.replace(m.group(0), 'COUNT(*)', 1)
                fixes.append(f"{fn}({col}) → COUNT(*) (col es STRING)")

    return expr, fixes


def _fix_division_without_nullif(expr):
    """`/ X` donde X no es NULLIF(...) → `/ NULLIF(X, 0)`."""
    fixes = []

    # Buscar `/ <expr>` donde expr no empieza con NULLIF
    # Patrón conservador: divisor es MEASURE(...) o (...)
    def replace_div(m):
        divisor = m.group(1).strip()
        if divisor.upper().startswith('NULLIF') or divisor.upper().startswith('TRY_DIVIDE'):
            return m.group(0)  # ya protegido
        fixes.append(f"División sin NULLIF: / {divisor[:30]}... → / NULLIF(..., 0)")
        return f' / NULLIF({divisor}, 0)'

    pattern = r'\s*/\s*(MEASURE\([^)]+\)|\([^()]+\)|\w+)'
    expr = re.sub(pattern, replace_div, expr)

    return expr, fixes


def _fix_then_string_flag(expr, columns_types):
    """
    `CASE WHEN ... THEN <string_col>` donde string_col es STRING → THEN 1.
    Ejemplo: THEN cc_member_base_flag → THEN 1.
    """
    fixes = []
    string_cols = {c for c, t in columns_types.items()
                   if t.upper() == 'STRING'}

    pattern = r'\bTHEN\s+(\w+)\b'
    def replace_then(m):
        col = m.group(1)
        if col in string_cols:
            fixes.append(f"THEN {col} → THEN 1 (col es STRING)")
            return 'THEN 1'
        return m.group(0)

    expr = re.sub(pattern, replace_then, expr)
    return expr, fixes


def get_source_columns_types(spark, catalog, schema, table):
    """Lee tipos de columnas de la tabla source del schema vivo."""
    df = spark.sql(f"""
        SELECT column_name, data_type
        FROM {catalog}.information_schema.columns
        WHERE table_schema = '{schema}'
          AND table_name = '{table}'
    """)
    return {r['column_name']: r['data_type'] for r in df.collect()}


def validate_and_fix_all_measures(measures_list, source_columns_types):
    """
    Aplica fix a una lista de measures.
    `measures_list` es lista de dicts con al menos 'name' y 'expr'.
    Retorna (measures_fijadas, report).
    """
    fixed = []
    report = []
    for m in measures_list:
        new_expr, fixes = fix_measure_expression(
            m.get('expr', ''),
            source_columns_types
        )
        new_m = dict(m)
        new_m['expr'] = new_expr
        fixed.append(new_m)
        if fixes:
            report.append({
                'measure': m.get('name', '?'),
                'fixes': fixes
            })
    return fixed, report
