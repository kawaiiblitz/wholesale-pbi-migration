# Databricks notebook source
# MAGIC %md
# MAGIC # Embed Images (paso 7b — opcional)
# MAGIC
# MAGIC Inyecta imágenes (logos, branding del cliente) en widgets markdown del
# MAGIC dashboard Lakeview, como data URIs base64.
# MAGIC
# MAGIC **Por qué:** Lakeview no resuelve paths externos en markdown widgets.
# MAGIC La única forma confiable de mostrar imágenes es embeberlas en base64.
# MAGIC
# MAGIC **Cuándo correr:** después de `7. apply_styles`, antes de publicar.
# MAGIC
# MAGIC **Pre-requisitos:**
# MAGIC 1. Las imágenes deben estar en un Volume UC o Workspace path accesible
# MAGIC    desde el notebook.
# MAGIC 2. Un archivo `image_mapping.json` que mapee widget_name → image_path.
# MAGIC 3. Imágenes en PNG/JPG/SVG (NO .webp, Lakeview no lo rendea).

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Parámetros

# COMMAND ----------

dbutils.widgets.text("catalog", "<your_catalog>", "Catálogo")
dbutils.widgets.text("schema", "<your_schema>", "Schema")
dbutils.widgets.text("dashboard_path",
                     "/Workspace/Users/<your-email>@databricks.com/pbi-migration/<your_dashboard>.lvdash.json",
                     "Path del dashboard")
dbutils.widgets.text("image_dir",
                     "/Volumes/<your_catalog>/<your_schema>/<your_volume>/imagenes",
                     "Carpeta con las imágenes")
dbutils.widgets.text("mapping_path",
                     "/Workspace/Users/<your-email>@databricks.com/pbi-migration/image_mapping.json",
                     "Path al JSON con mapping {widget_name: image_path}")
dbutils.widgets.text("module_path",
                     "/Workspace/Users/<your-email>@databricks.com/pbi-migration/modules",
                     "Path a los módulos Python")

CATALOG = dbutils.widgets.get("catalog")
SCHEMA = dbutils.widgets.get("schema")
DASHBOARD_PATH = dbutils.widgets.get("dashboard_path")
IMAGE_DIR = dbutils.widgets.get("image_dir")
MAPPING_PATH = dbutils.widgets.get("mapping_path")
MODULE_PATH = dbutils.widgets.get("module_path")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Cargar módulo

# COMMAND ----------

import sys, os, json
sys.path.insert(0, MODULE_PATH if os.path.isdir(MODULE_PATH) else os.path.dirname(os.path.abspath('')))

from image_embedder import (
    embed_images_in_dashboard,
    load_mapping,
    list_image_widgets,
)
from lakeview_post_process import (
    patch_dashboard_via_lakeview_api,
    publish_dashboard,
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Leer dashboard actual

# COMMAND ----------

import requests, base64

token = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().get()
host = spark.conf.get("spark.databricks.workspaceUrl")

resp = requests.get(
    f"https://{host}/api/2.0/workspace/export",
    params={"path": DASHBOARD_PATH, "format": "AUTO"},
    headers={"Authorization": f"Bearer {token}"},
    timeout=30,
)
resp.raise_for_status()
dashboard_json_str = base64.b64decode(resp.json()["content"]).decode("utf-8")
dashboard = json.loads(dashboard_json_str)

print(f"Dashboard cargado: {len(dashboard.get('pages', []))} páginas")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. (Opcional) Identificar widgets candidatos para imágenes
# MAGIC
# MAGIC Útil para construir el mapping inicial si no lo tienes aún.

# COMMAND ----------

candidates = list_image_widgets(dashboard)
print(f"Widgets candidatos a imagen ({len(candidates)}):")
for c in candidates[:20]:
    print(f"  page={c['page']!r} widget={c['widget_name']!r} type={c['type']}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Cargar mapping y embebir imágenes
# MAGIC
# MAGIC El mapping debe ser un JSON tipo:
# MAGIC ```json
# MAGIC {
# MAGIC   "img_logo_costco": "logo_costco.png",
# MAGIC   "img_card_rtcc": {"path": "tarjeta_rtcc.png", "caption": "RTCC"},
# MAGIC   "img_card_reg": {"path": "tarjeta_reg.png", "caption": "REG"}
# MAGIC }
# MAGIC ```

# COMMAND ----------

mapping = load_mapping(MAPPING_PATH)
print(f"Mapping cargado: {len(mapping)} widgets")

n = embed_images_in_dashboard(dashboard, mapping, image_dir=IMAGE_DIR)
print(f"\n{n} imágenes embebidas")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Publicar dashboard

# COMMAND ----------

# Re-encode and upload
new_json_str = json.dumps(dashboard)
new_b64 = base64.b64encode(new_json_str.encode("utf-8")).decode("utf-8")

import_resp = requests.post(
    f"https://{host}/api/2.0/workspace/import",
    json={"path": DASHBOARD_PATH, "content": new_b64, "format": "AUTO", "overwrite": True},
    headers={"Authorization": f"Bearer {token}"},
    timeout=60,
)
import_resp.raise_for_status()
print(f"✓ Dashboard actualizado en workspace: {DASHBOARD_PATH}")

# Si tienes dashboard_id, también puedes hacer PATCH y publicar:
# patch_dashboard_via_lakeview_api(host, token, dashboard_id, dashboard)
# publish_dashboard(host, token, dashboard_id)
