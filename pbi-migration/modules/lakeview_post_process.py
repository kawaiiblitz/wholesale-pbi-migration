"""
Post-procesamiento determinístico para dashboards Lakeview.

Aplica fixes que el LLM consistentemente no hace bien o que son
quirks específicos de Lakeview. Todo es código puro, sin LLM en el loop.

Llamar desde notebook `5. generate_dashboard.py` después de que el LLM
genere el dashboard JSON, ANTES de subirlo al workspace.
"""

import re
import hashlib
import json
import time


def post_process_dashboard(dashboard_dict, dataset_name='ds_howyoudrivesales'):
    """
    Aplica todos los fixes determinísticos a un dashboard Lakeview.
    Modifica el dict in-place y lo retorna.
    """
    convert_case_when_to_precomputed(dashboard_dict, dataset_name)
    apply_counter_titles(dashboard_dict)
    move_time_counters_to_header(dashboard_dict)
    flatten_markdown_blanks(dashboard_dict)
    fix_title_overlap(dashboard_dict)
    bust_dataset_cache(dashboard_dict)
    return dashboard_dict


def convert_case_when_to_precomputed(d, dataset_name):
    """
    Bug 1: Lakeview no procesa SUM(CASE WHEN... ELSE NULL END) ni SUM(IF(...))
    client-side. Solo aggregates simples (SUM/COUNT/AVG sobre col cruda).

    Solución: para cada counter con expresión compleja, mover el CASE/IF al
    OUTER SELECT del dataset query como columna pre-computada `pc_<hash>`,
    y dejar el counter con SUM(`pc_<hash>`).
    """
    for ds in d.get('datasets', []):
        if ds.get('name') != dataset_name:
            continue

        new_columns = {}  # pc_name -> sql expression
        ds_sql = ''.join(ds.get('queryLines', []))

        # Recolectar todas las expresiones complejas usadas en counters
        for page in d.get('pages', []):
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

                if not _is_complex_expression(expr):
                    continue

                # Match outer aggregate (SUM, COUNT, AVG, MIN, MAX) y su contenido interno
                m = re.match(r'^\s*(SUM|COUNT|AVG|MIN|MAX)\s*\((.+)\)\s*$',
                             expr, re.IGNORECASE | re.DOTALL)
                if not m:
                    continue

                outer_agg = m.group(1).upper()
                inner = m.group(2)

                # Generar nombre único determinístico
                col = 'pc_' + hashlib.md5(expr.encode()).hexdigest()[:8]
                new_columns[col] = inner

                # Reemplazar la expresión del counter
                fields[0] = {
                    'name': col,
                    'expression': f'{outer_agg}(`{col}`)'
                }
                spec['encodings']['value']['fieldName'] = col

        # Inyectar las columnas pre-computadas al outer SELECT del dataset
        if new_columns:
            ds['queryLines'] = _inject_precomputed_columns(
                ds.get('queryLines', []),
                new_columns
            )


def _is_complex_expression(expr):
    """¿Tiene CASE WHEN o IF? Esos no los procesa Lakeview client-side."""
    e = expr.upper()
    return 'CASE' in e or re.search(r'\bIF\s*\(', e) is not None


def _inject_precomputed_columns(query_lines, new_columns):
    """Agrega `(<expr>) AS \`pc_xxx\`,` antes del FROM ( externo."""
    full = ''.join(query_lines)
    m = re.search(r'\n\s*FROM\s*\(\s*\n', full)
    if not m:
        return query_lines  # no encontró estructura esperada

    insert_pos = m.start()
    additions = '\n'
    for col, sql in new_columns.items():
        additions += f'    ({sql}) AS `{col}`,\n'
    additions = additions.rstrip(',\n') + '\n'

    new_full = full[:insert_pos] + additions + full[insert_pos:]
    # Reconstruir queryLines preservando los \n
    return [l + '\n' for l in new_full.split('\n')[:-1]]


def apply_counter_titles(d):
    """
    Bug 4 + 8: counters salen sin título visible. displayName en encoding NO
    se ve. Hay que poner spec.frame.title + showTitle.

    Deriva el título del nombre del widget (counter_spend_rtcc_1st →
    'Annual Spend $ · RTCC').
    """
    for page in d.get('pages', []):
        for w in page.get('layout', []):
            spec = w.get('widget', {}).get('spec', {})
            if spec.get('widgetType') != 'counter':
                continue
            name = w['widget'].get('name', '')
            metric = _get_metric_label(name)
            seg = _get_segment(name)
            yr = _get_year(name)
            parts = [metric]
            if seg:
                parts.append(f'· {seg}')
            if yr and yr not in ('1st', '2nd+'):
                parts.append(f'({yr})')
            title = ' '.join(parts)
            if 'frame' not in spec:
                spec['frame'] = {}
            spec['frame']['title'] = title
            spec['frame']['showTitle'] = True
            # Quitar displayName redundante
            if 'encodings' in spec and 'value' in spec['encodings']:
                spec['encodings']['value'].pop('displayName', None)


def move_time_counters_to_header(d):
    """
    Bug 5: Counters tipo MIN(period) / MAX(year) se ven mal en el grid.
    En PBI son contexto del header. Detectarlos y reposicionarlos a y=0
    en la esquina derecha.
    """
    for page in d.get('pages', []):
        for w in page.get('layout', []):
            name = w['widget'].get('name', '').lower()
            if 'min_period' in name:
                w['position'] = {'x': 9, 'y': 0, 'width': 1, 'height': 2}
                spec = w['widget'].get('spec', {})
                if 'frame' not in spec:
                    spec['frame'] = {}
                spec['frame']['title'] = 'Periodo Mín'
                spec['frame']['showTitle'] = True
            elif 'max_year' in name:
                w['position'] = {'x': 10, 'y': 0, 'width': 2, 'height': 2}
                spec = w['widget'].get('spec', {})
                if 'frame' not in spec:
                    spec['frame'] = {}
                spec['frame']['title'] = 'Año Máx'
                spec['frame']['showTitle'] = True


def flatten_markdown_blanks(d):
    """
    Bug 6: Lakeview strippea líneas vacías en `multilineTextboxSpec.lines`.
    Si pones [titulo, '', imagen], guarda solo [titulo].

    Fix: quitar líneas vacías del array antes de subir.
    """
    for page in d.get('pages', []):
        for w in page.get('layout', []):
            md = w.get('widget', {}).get('multilineTextboxSpec')
            if not md:
                continue
            lines = md.get('lines', [])
            md['lines'] = [l for l in lines if l.strip()]


def fix_title_overlap(d):
    """
    Bug operativo: si un título tiene width=12 al inicio (y=0), y los time
    counters están en x=9, x=10 también con y=0 → overlap → nada se ve.

    Fix: si hay widget en y=0 a la derecha (x>=9), reducir width del título
    a 9 para no traslapar.
    """
    for page in d.get('pages', []):
        layout = page.get('layout', [])
        title = next((w for w in layout
                      if w['widget'].get('name', '').startswith('title_')
                      and w['position'].get('y') == 0), None)
        if not title:
            continue
        # ¿Hay otro widget en y=0 con x >= 9?
        has_right_widget = any(
            w is not title
            and w['position'].get('y') == 0
            and w['position'].get('x', 0) >= 9
            for w in layout
        )
        if has_right_widget and title['position'].get('width', 0) > 9:
            title['position']['width'] = 9


def bust_dataset_cache(d):
    """Actualizar el comment `-- bust:` para forzar re-ejecución del query."""
    for ds in d.get('datasets', []):
        lines = ds.get('queryLines', [])
        if lines and lines[0].startswith('-- bust:'):
            lines[0] = f'-- bust: {int(time.time())}\n'


# ----- Helpers para derivar títulos de nombres de widgets -----

def _get_metric_label(counter_name):
    n = counter_name.lower()
    if 'spend' in n:
        return 'Annual Spend $'
    if 'shops' in n:
        return 'Annual Shops'
    if 'renewal' in n:
        return 'Renewal Rate'
    if 'members' in n:
        return 'Member Base'
    if 'min_period' in n:
        return 'Periodo Mín'
    if 'max_year' in n:
        return 'Año Máx'
    return 'Penetration %'


def _get_segment(counter_name):
    n = counter_name.lower()
    if 'etcc' in n:
        return 'ETCC'
    if 'rtcc' in n:
        return 'RTCC'
    if 'exc' in n:
        return 'EXC'
    if 'reg' in n:
        return 'REG'
    return ''


def _get_year(counter_name):
    n = counter_name.lower()
    if '2nd' in n or '2ndmasyear' in n:
        return '2nd+'
    if '1st' in n:
        return '1st'
    if 'total' in n:
        return 'Total'
    return ''


# ----- API helpers -----

def patch_dashboard_via_lakeview_api(host, token, dashboard_id,
                                     display_name, dashboard_dict, warehouse_id):
    """
    Bug 7: workspace import no recompila el dashboard runtime. Usar la API
    de Lakeview directamente fuerza recompilación.
    """
    import requests

    serialized = json.dumps(dashboard_dict)
    url = f"https://{host}/api/2.0/lakeview/dashboards/{dashboard_id}"
    payload = {
        'display_name': display_name,
        'serialized_dashboard': serialized,
        'warehouse_id': warehouse_id
    }
    r = requests.patch(url, headers={'Authorization': f'Bearer {token}'},
                       json=payload, timeout=60)
    r.raise_for_status()
    return r.json()


def publish_dashboard(host, token, dashboard_id, embed_credentials=False):
    import requests
    url = f"https://{host}/api/2.0/lakeview/dashboards/{dashboard_id}/published"
    r = requests.post(url, headers={'Authorization': f'Bearer {token}'},
                      json={'embed_credentials': embed_credentials},
                      timeout=60)
    r.raise_for_status()
    return r.json()
