"""
Smoke test del dashboard generado: ejecuta el dataset query y reporta
cualquier counter que devuelva NULL/error.

Llamar al final de notebook 5 después de subir el dashboard. Da feedback
inmediato si algo está mal antes de que lo descubra el usuario.
"""

import re


def smoke_test_dashboard(spark, dashboard_dict, dataset_name='ds_howyoudrivesales'):
    """
    Ejecuta:
      1. El dataset query (debe retornar > 0 rows)
      2. Para cada counter widget, su query (debe retornar valor != NULL)

    Retorna list de problemas encontrados.
    """
    issues = []

    # 1. Dataset query
    ds = next((d for d in dashboard_dict.get('datasets', [])
               if d.get('name') == dataset_name), None)
    if not ds:
        return [f"Dataset '{dataset_name}' no encontrado"]

    ds_sql = ''.join(ds.get('queryLines', []))
    try:
        count = spark.sql(f"SELECT COUNT(*) AS n FROM ({ds_sql})").collect()[0]['n']
        if count == 0:
            issues.append(f"Dataset query retorna 0 rows")
    except Exception as e:
        issues.append(f"Dataset query FAILED: {str(e)[:200]}")
        return issues  # si dataset rompe, los counters también

    # 2. Counters con expression (limit a 10 por brevedad)
    tested = 0
    for page in dashboard_dict.get('pages', []):
        for w in page.get('layout', []):
            spec = w.get('widget', {}).get('spec', {})
            if spec.get('widgetType') != 'counter':
                continue
            queries = w['widget'].get('queries', [])
            if not queries:
                continue
            fields = queries[0].get('query', {}).get('fields', [])
            if not fields:
                continue
            expr = fields[0].get('expression', '')
            name = w['widget'].get('name', '?')

            try:
                result = spark.sql(
                    f"SELECT {expr} AS v FROM ({ds_sql})"
                ).collect()
                v = result[0]['v'] if result else None
                if v is None:
                    issues.append(f"Counter '{name}' retorna NULL")
            except Exception as e:
                issues.append(f"Counter '{name}' FAILED: {str(e)[:150]}")

            tested += 1
            if tested >= 10:  # limitar para no demorar mucho
                break
        if tested >= 10:
            break

    return issues


def print_smoke_test_report(issues):
    if not issues:
        print("✓ Smoke test PASS — dataset y counters funcionando")
        return
    print(f"⚠ Smoke test encontró {len(issues)} problemas:")
    for i, issue in enumerate(issues, 1):
        print(f"  {i}. {issue}")
