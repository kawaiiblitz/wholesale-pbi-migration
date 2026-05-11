"""Image embedder for Lakeview dashboards.

Lakeview no resuelve paths externos (Volume UC, Workspace, URLs auth-protected)
dentro de markdown widgets. La forma confiable de mostrar imágenes (logos,
branding del cliente) es embeberlas como data URIs base64.

Este módulo automatiza ese proceso:
  - Lee un mapping {widget_name: image_path}
  - Convierte cada imagen a data URI
  - Inyecta como markdown widget en el dashboard JSON

Funciona con imágenes locales en el workspace (paths absolutos /Workspace/...)
o en Volume UC (paths /Volumes/...).

Uso típico desde un notebook (ver 7b. embed_images.py):

    from image_embedder import embed_images_in_dashboard, load_mapping

    mapping = load_mapping('/Workspace/.../image_mapping.json')
    n = embed_images_in_dashboard(dashboard_dict, mapping,
                                   image_dir='/Volumes/cat/sch/vol/imagenes')
    print(f'{n} imágenes embebidas')
"""

import base64
import json
import os
from pathlib import Path


MIME_BY_EXT = {
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.gif': 'image/gif',
    '.svg': 'image/svg+xml',
    '.webp': 'image/webp',
}


def image_to_data_uri(image_path, mime=None):
    """Convierte una imagen local a data URI base64.

    image_path: ruta absoluta o relativa al archivo de imagen.
    mime: si no se especifica, se infiere de la extensión.

    Retorna: 'data:image/png;base64,<...>'

    NOTA: Lakeview NO rendea .webp dentro de markdown. Convierte a PNG primero:
        sips -s format png imagen.webp --out imagen.png  # macOS
        convert imagen.webp imagen.png  # ImageMagick
    """
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f'Image not found: {path}')

    if mime is None:
        ext = path.suffix.lower()
        mime = MIME_BY_EXT.get(ext, 'image/png')
        if ext == '.webp':
            print(f'WARNING: {path.name} es .webp, Lakeview no la renderea. '
                  'Conviertela a PNG primero.')

    with open(path, 'rb') as f:
        b64 = base64.b64encode(f.read()).decode('utf-8')

    return f'data:{mime};base64,{b64}'


def _to_markdown_widget(widget, data_uri, caption=None):
    """Convierte un widget existente en markdown widget con imagen.

    Si ya es markdown widget, sólo reemplaza el contenido.
    Si es otro tipo (counter, table, etc.), lo convierte preservando name y position.
    """
    lines = [f'![]({data_uri})']
    if caption:
        lines.append(f'**{caption}**')

    # Multilinetextbox style (legacy)
    if 'multilineTextboxSpec' in widget:
        widget['multilineTextboxSpec']['lines'] = lines
        return

    # Modern markdown widget style (textboxSpec with markdown)
    spec = widget.get('spec') or {}
    if spec.get('widgetType') == 'markdown':
        spec['text'] = '\n'.join(lines)
        return

    # Convert to markdown widget
    widget['spec'] = {
        'version': 1,
        'widgetType': 'markdown',
        'text': '\n'.join(lines),
    }
    # Remove queries (markdown widgets don't have queries)
    widget.pop('queries', None)


def embed_images_in_dashboard(dashboard_dict, mapping, image_dir=None):
    """Inyecta imágenes en widgets markdown del dashboard.

    Args:
        dashboard_dict: el dashboard JSON dict (deserialized).
        mapping: dict {widget_name: image_path_or_dict}.
            Si el valor es un string, se usa como path a la imagen.
            Si es un dict, soporta {'path': str, 'caption': str, 'mime': str}.
        image_dir: directorio base si los paths en mapping son relativos.

    Returns:
        Número de widgets actualizados.

    Modifica dashboard_dict in-place.
    """
    base = Path(image_dir) if image_dir else None
    updated = 0
    missing = []

    for page in dashboard_dict.get('pages', []):
        for entry in page.get('layout', []):
            widget = entry.get('widget') or {}
            name = widget.get('name', '')
            if name not in mapping:
                continue

            spec = mapping[name]
            if isinstance(spec, str):
                img_path, caption, mime = spec, None, None
            elif isinstance(spec, dict):
                img_path = spec.get('path')
                caption = spec.get('caption')
                mime = spec.get('mime')
            else:
                continue

            if not img_path:
                continue

            full_path = Path(img_path)
            if base and not full_path.is_absolute():
                full_path = base / img_path

            if not full_path.exists():
                missing.append((name, str(full_path)))
                continue

            data_uri = image_to_data_uri(full_path, mime=mime)
            _to_markdown_widget(widget, data_uri, caption=caption)
            updated += 1

    if missing:
        print(f'WARNING: {len(missing)} imágenes no encontradas:')
        for name, path in missing:
            print(f'  - {name}: {path}')

    return updated


def load_mapping(mapping_path):
    """Carga un mapping de imagen desde JSON.

    El archivo debe ser un JSON con estructura:
        {
          "widget_name_1": "logo_costco.png",
          "widget_name_2": {"path": "tarjeta_rtcc.png", "caption": "RTCC"},
          ...
        }
    """
    with open(mapping_path) as f:
        return json.load(f)


def list_image_widgets(dashboard_dict):
    """Lista widgets que parecen "image placeholders" (markdown vacíos o
    con nombre que sugiere imagen). Útil para construir el mapping inicial.
    """
    candidates = []
    for page in dashboard_dict.get('pages', []):
        for entry in page.get('layout', []):
            widget = entry.get('widget') or {}
            name = widget.get('name', '')
            wtype = widget.get('spec', {}).get('widgetType') or (
                'markdown' if 'multilineTextboxSpec' in widget else 'unknown'
            )
            # Heurística: nombre contiene img/image/logo/foto/tarjeta/card
            looks_image = any(kw in name.lower() for kw in
                              ('img', 'image', 'logo', 'foto', 'tarjeta', 'card', 'banner'))
            if looks_image or wtype == 'markdown':
                candidates.append({
                    'page': page.get('name'),
                    'widget_name': name,
                    'type': wtype,
                    'position': entry.get('position'),
                })
    return candidates
