# Wholesale PBI Migration Pipeline

Pipeline para migrar dashboards de Power BI (.pbix) a dashboards Databricks Lakeview (AI/BI), con metric views generadas a partir del modelo tabular del PBIX. Plantilla específica para industria **wholesale / retail club** (membresías, renewal rate, segmentación de socios).

**Origen:** fork sanitizado de [`yvillavicencioDBX/SAT`](https://github.com/yvillavicencioDBX/SAT) (Yolanda Villavicencio).


---

## Para qué sirve

Tomas un archivo `.pbix` exportado desde Power BI Desktop y obtienes:

1. **Un modelo semántico en Unity Catalog** (Metric Views) con measures DAX traducidas a SQL.
2. **Un dashboard Lakeview** (`.lvdash.json`) con páginas, widgets, slicers y textboxes del PBI original.
3. **Datos sintéticos opcionales** para QA (no se usan con datos reales del cliente).

---

## Prerequisitos

- Workspace Databricks con Serverless SQL Warehouse y Foundation Model API (Claude Sonnet 4 o equivalente).
- Catálogo Unity Catalog donde escribir tablas y metric views.
- Volumen UC para subir el archivo `.pbix`.
- Tablas reales del cliente ya cargadas en UC (en producción) o el paso 00 (sintético) si es demo.

---

## Estructura del pipeline (orden de ejecución)

| # | Notebook | Qué hace |
|---|---|---|
| **00** | `00. generate_sample_tables` | Solo demo. Genera tablas sintéticas a partir del modelo del PBIX |
| **0** | `0. extract_pbix_model` | Extrae metadata: measures DAX, relaciones, columnas, filtros de contexto |
| **1** | `1. create_base_metric_views` | Crea Metric Views base (source + joins + dimensiones) sin measures |
| **2** | `2. create_measures` (LLM) | Traduce DAX → SQL. **Incluye auto-fix de bugs comunes (modules/measure_validators.py).** |
| **2.1** | `2.1 create_dashboard_views` | Vistas SQL planas para el dashboard |
| **3** | `3. create_dashboard_semantic` | Skeleton del dashboard. **Dataset query construido dinámicamente (modules/dynamic_dataset_query.py).** |
| **4** | `4. extract_visuals` | Visuales, posiciones, campos, filtros per-visual, contenido textual de textboxes |
| **4b** | `4b. extract_visual_props` | Sort, formato condicional, propiedades de columna |
| **4b** | `4b. create_name_translator` | Mapea nombres PBI (CamelCase) → snake_case |
| **5** | `5. generate_dashboard` (LLM) | Genera widgets. **Post-procesamiento determinístico al final (modules/lakeview_post_process.py).** |
| **5b** | `5b. refine_dashboard` | Limpia widgets (props inválidas, queries malformadas) |
| **6** | `6. add_dashboard_filters` | Convierte slicers PBI en filter widgets |
| **7** | `7. apply_styles` | Aplica estilos (colores, formato) |
| **7b** | `7b. embed_images` (opcional) | Embebe logos/branding del cliente como base64 (`modules/image_embedder.py`) |
| **8** | `8. humanize_titles (param)` (LLM) | Humaniza titulares técnicos |
| **9** | `9. migration_report` | (Opcional) reporte de migración |
| **10** | `10. export_metric_views` | (Opcional) exporta YAML de cada metric view |

---

## Cómo correr

### Vía orquestador (todo de corrido)

Abre `0. Orquestador Migracion PBI.py` en Databricks y configura los widgets:

| Widget | Valor |
|---|---|
| `pbix_path` | `/Volumes/<catalog>/<schema>/pbix/<archivo>.pbix` |
| `catalog` | catálogo destino del cliente |
| `schema` | schema destino |
| `dashboard_path` | `/Users/<email>/pbi-migration/<nombre>.lvdash.json` |
| `llm_endpoint` | `databricks-claude-sonnet-4` |
| `module_path` | `/Workspace/Users/<email>/pbi-migration/modules` |
| `base_path` | `/Users/<email>/pbi-migration` |

**En producción NO corras el paso 00.** Las tablas las trae el cliente.

---

## Imágenes del dashboard (logos, tarjetas, branding)

El PBIX suele traer imágenes (logos, tarjetas) que el pipeline no migra automáticamente porque Lakeview no tiene widget de imagen nativo. La solución es embeberlas como base64 dentro de un markdown widget.

**Workflow rápido (4 pasos):**

1. Sube las imágenes (PNG/JPG) a un Volume UC: `/Volumes/<catalog>/<schema>/<volume>/imagenes/`
2. Crea un `image_mapping.json` con `{widget_name: filename}` (template en `config/image_mapping.example.json`)
3. Corre el notebook `7b. embed_images.py` apuntando al dashboard, carpeta de imágenes y mapping
4. El notebook convierte cada imagen a base64 y la inyecta en el widget correspondiente

Listo. Si las imágenes están en `.webp`, conviértelas a PNG primero (Lakeview no rendea webp).

### Workflow manual (si prefieres script propio)

```python
from image_embedder import embed_images_in_dashboard, load_mapping

mapping = load_mapping('/Workspace/.../image_mapping.json')
n = embed_images_in_dashboard(
    dashboard,
    mapping,
    image_dir='/Volumes/<catalog>/<schema>/<volume>/imagenes'
)
print(f'{n} imágenes embebidas')
```

Y luego subes el dashboard via Lakeview API (no via workspace import, que no
fuerza recompilación). El módulo `lakeview_post_process.py` tiene los helpers
`patch_dashboard_via_lakeview_api` y `publish_dashboard`.

### Notas operativas

- **Markdown widgets strippean líneas vacías**: si pones `[image, '', label]`, Lakeview guarda solo `[image]`. El módulo `lakeview_post_process.py` filtra blanks automáticamente en post-procesamiento.
- **Tamaño**: las imágenes base64 inflan el .lvdash.json ~33%. Una página con 4 imágenes de 50KB cada una agrega ~270KB al JSON. Manejable hasta varios MB.
- **Opcional**: si quieres mantener las imágenes "fuera" del JSON, puedes guardar un volume backup en `dbfs:/Volumes/<catalog>/<schema>/<volume>/imagenes/` y un script que las inyecte como base64 en el dashboard cada vez que se regenere. Útil si el cliente reemplaza branding seguido.

---

## Validación anti-alucinación (paso 2)

El paso 2 traduce DAX → SQL usando un LLM. Después de cada traducción se aplican validadores deterministas (`modules/measure_validators.py`):

- `SUM(col)` o `AVG(col)` donde `col` es STRING → auto-corregido a `COUNT(*)`
- División sin `NULLIF` → auto-envuelve denominador
- `CASE WHEN ... THEN <string_flag> ELSE 0 END` → auto-corrige a `THEN 1`

Además, si el SQL traducido contiene literales que NO aparecen en el DAX original, la measure se marca como `NEEDS_REVIEW` en `pbi_measure_validation`.

```sql
SELECT measure, original_dax_measure, suspicious_literals
FROM <catalog>.<schema>.pbi_measure_validation
WHERE status = 'NEEDS_REVIEW';
```

---

## Post-procesamiento del dashboard (paso 5)

Después de que el LLM genere widgets, `modules/lakeview_post_process.py` aplica fixes deterministas que el LLM consistentemente no hace bien:

| Fix | Por qué |
|---|---|
| Convertir `SUM(CASE WHEN... ELSE NULL END)` en counters → columna pre-computada `pc_<hash>` en outer SELECT del dataset, counter usa `SUM(pc_xxx)` simple | Lakeview client-side no procesa CASE WHEN, deja counters en "No data" |
| Asignar `spec.frame.title` a cada counter (derivado del nombre del widget) | `displayName` en encoding NO se ve; `frame.title` sí |
| Mover counters de `MIN(period)` y `MAX(year)` a la esquina derecha del header | Son contexto temporal, no métricas |
| Strippear líneas vacías de `multilineTextboxSpec.lines` | Lakeview las descarta al guardar |
| Reducir width del título a 9 si hay widgets en x>=9 con y=0 | Evita overlap del header con time counters |
| Refrescar comment `-- bust:` del dataset query | Fuerza re-ejecución (evita cache) |

---

## Smoke test (paso 5)

Al final del paso 5, `modules/smoke_test.py` ejecuta el dataset query y verifica que los counters retornen valores válidos:

```
✓ Smoke test PASS — dataset y counters funcionando
```

Si algo falla, lista los counters problemáticos antes de que el usuario los descubra en el browser.

---

## Limitaciones conocidas

| # | Limitación | Workaround |
|---|---|---|
| 1 | Imágenes del PBIX no se migran | Subir al volume y embedir en markdown como base64 (ver sección Imágenes) |
| 2 | Layout exacto pixel→grid es aproximado | Post-procesamiento ajusta lo más común; resto se afina en editor Lakeview |
| 3 | Pivot tables (matrix visuals) del PBI no tienen equivalente directo | Se generan como `table` widgets simples (sin totals jerárquicos) |
| 4 | Custom visuals (WordCloud, mapas custom, etc.) | Ignorados |
| 5 | Bookmarks, drillthrough, paginated reports | Ignorados |

---

## Estructura del repo

```
.
├── README.md
├── databricks.yml
├── wholesale-howyoudrivesales.lvdash.json   ← skeleton de referencia (Costco)
└── pbi-migration/
    ├── 0. Orquestador Migracion PBI.py     ← entrada principal
    ├── 0. extract_pbix_model.py
    ├── 00. generate_sample_tables.py       ← solo QA
    ├── 1. create_base_metric_views.py
    ├── 2. create_measures.py
    ├── 2.1 create_dashboard_views.py
    ├── 3. create_dashboard_semantic.py
    ├── 4. extract_visuals.py
    ├── 4b. extract_visual_props.py
    ├── 4b. create_name_translator.py
    ├── 5. generate_dashboard.py
    ├── 5b. refine_dashboard.py
    ├── 6. add_dashboard_filters.py
    ├── 7. apply_styles.py
    ├── 7b. embed_images.py                  ← embebir logos/branding del cliente
    ├── 8. humanize_titles (param).py
    ├── 9. migration_report.py
    ├── 10. export_metric_views.py
    ├── config/                              ← guías que el LLM lee en pasos 2, 5
    │   ├── REGLAS_DASHBOARD.md
    │   ├── DAX_TO_SQL_GUIDE.md
    │   ├── CLAUDE_DASHBOARD_GUIDE.md
    │   ├── AIBI_DASHBOARD_SKILL.md
    │   ├── CONVERSION_GUIDE.md
    │   └── image_mapping.example.json       ← template para paso 7b
    └── modules/
        ├── llm_converter.py
        ├── parser.py
        ├── pbix_parser.py
        ├── dax_function_reference.py
        ├── metrics_view_docs.py
        ├── lakeview_post_process.py        ← Post-procesamiento determinístico (paso 5)
        ├── measure_validators.py           ← Auto-fix de measures (paso 2)
        ├── dynamic_dataset_query.py        ← Dataset query dinámico (paso 3)
        ├── image_embedder.py               ← Embebir imágenes base64 (paso 7b)
        └── smoke_test.py                   ← Validación post-generación (paso 5)
```

---

## Flujo de entrega recomendado

1. Correr el pipeline completo (`0` a `8`).
2. Consultar `pbi_measure_validation` y revisar cada `NEEDS_REVIEW`.
3. Para cada measure sospechosa: comparar `sql_expr_preview` contra `original_dax_measure`. Si el LLM agregó condiciones inventadas, editar el YAML de la metric view manualmente.
4. Validar que measures críticas devuelven valores no-NULL:
   ```sql
   SELECT MEASURE(<measure_name>) FROM <catalog>.<schema>.mv_<tabla>;
   ```
5. Abrir el dashboard publicado y comparar contra el PBIX original página por página.
6. (Opcional) Subir imágenes del cliente al volume y embedirlas como base64 (ver sección Imágenes).
7. Ajustes finos de layout/colores en el editor Lakeview.

---

## Créditos

- Pipeline original: Yolanda Villavicencio (Databricks Field Engineering)
- Fixes wholesale + post-procesamiento determinístico: Raquel Peña (Databricks Field Engineering)
