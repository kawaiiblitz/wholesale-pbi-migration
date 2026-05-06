# Reglas para Databricks Lakeview Dashboards (.lvdash.json)

## 1. Formato del archivo

| Regla | Detalle |
|-------|---------|
| Extensión | **`.lvdash.json`** para que Databricks lo detecte como dashboard |
| Keys de primer nivel | `datasets`, `pages`, `uiSettings` |
| NO usar | `serialized_dashboard` (eso es solo para la API REST, no para archivos) |
| uiSettings obligatorio | `{"theme": {"widgetHeaderAlignment": "ALIGNMENT_UNSPECIFIED"}, "applyModeEnabled": false}` |
| layoutVersion en cada página | Agregar `"layoutVersion": "GRID_V1"` junto a `"pageType"` en cada página para habilitar grid de 12 columnas. **Sin esto, el grid se interpreta como 6 columnas.** |

## 2. Version y disaggregated por tipo de widget

| Widget | `version` | `disaggregated` | Expresión de campos | `fieldName` en encoding |
|--------|-----------|-----------------|---------------------|------------------------|
| **counter** | `2` | `false` | `SUM(\`campo\`)` | `sum(campo)` |
| **table** | `2` | `true` | `` \`campo\` `` | `campo` |
| **bar** | `3` | `true` | `` \`campo\` `` | `campo` |
| **line** | `3` | `true` | `` \`campo\` `` | `campo` |

| **pie** | `3` | `true` | `` \`campo\` `` | `campo` |

## 3. Sort según version

| Version | Dónde va el sort | Ejemplo |
|---------|-----------------|---------|
| v2 (counter, table) | N/A o en SQL | `ORDER BY` en la query |
| v3 (bar, line, pie) | Dentro de `scale` | `"scale": {"type": "categorical", "sort": {"by": "x-reversed"}}` |

## 4. Text widgets (títulos y subtítulos)

| Regla | Detalle |
|-------|---------|
| Propiedad | `multilineTextboxSpec.lines` (array de strings) |
| Multilínea | **NO funciona** — el array se concatena en un solo string |
| Solución | Usar **widgets separados** para título y subtítulo |
| Markdown | Soporta `#`, `##`, `####` |
| Iconos | Unicode directo en el texto: `# ⚙ TÍTULO` |

## 5. Orientación de barras (horizontal vs vertical)

Consultar las etiquetas de la variable categórica:

```sql
SELECT DISTINCT `campo_categorico` FROM (dataset_query)
```

| Max longitud etiqueta | Orientación | Categoría en | Valor en |
|----------------------|-------------|-------------|----------|
| **> 8 caracteres** | Horizontal | eje Y | eje X |
| **≤ 8 caracteres** | Vertical | eje X | eje Y |

### Proceso de verificación obligatorio

**Antes de crear cualquier bar chart**, ejecutar esta query para decidir la orientación:

```sql
SELECT `campo_categorico`, LENGTH(`campo_categorico`) AS len
FROM (dataset_query)
ORDER BY len DESC
LIMIT 1
```

Si el resultado `len > 8` → la gráfica **debe** ser horizontal (categoría en Y).

**Esto aplica a TODOS los bar charts, sin excepción.** Ejemplos reales:
- `GASOLINA PREMIUM` (16 chars) → horizontal obligatorio
- `CRUDO MAYA EXP.` (15 chars) → horizontal obligatorio
- `RMNE` (4 chars) → vertical está bien
- `DIESEL` (6 chars) → vertical está bien

**Error común:** asumir que una gráfica es vertical sin consultar los datos. Siempre verificar primero.

## 6. Tamaños de widgets (grid de 12 columnas)

### Prioridad de dimensionamiento

1. **Primero**: calcular altura según número de categorías (bars) o proporción cuadrada (pies)
2. **Después**: compactar líneas y counters a tamaño estándar preferido (h=4)
3. **Finalmente**: rellenar huecos estirando widgets al más alto de la sección

### Tamaños estándar preferidos

| Widget | Ancho | Alto | Notas |
|--------|-------|------|-------|
| **text título** | w:12 | h:1 | Full width |
| **text subtítulo** | w:4-6 | h:1 | Según sección |
| **counter** | w:2 | h:4 | Se estira para rellenar sección |
| **line** | w:3 | h:4 | Tamaño compacto preferido |
| **pie** | w:6 | h:5 | Proporción cuadrada para círculo |
| **table** | w:8-12 | h:6+ | Según columnas |

### Bar charts — altura según categorías (regla principal)

La cantidad de categorías **siempre** determina la altura de las barras horizontales:

```
h = ceil(1 + n_categorías × 0.5), mínimo 3
```

| Categorías | Altura |
|-----------|--------|
| 2-3 | h=3 |
| 4 | h=3 |
| 5 | h=4 |
| 6 | h=4 |
| 7 | h=5 |

### Bar charts — ancho según posición

| Posición | Ancho |
|----------|-------|
| Sola en fila | w:6-12 |
| 2 barras lado a lado | w:3 cada una (en sección de 6) o w:6 (en 12) |
| Bar junto a counters | w:2-4 |

### Pie charts — proporción cuadrada

```
h ≈ w (para que el círculo no se aplaste)
```

| Ancho | Altura |
|-------|--------|
| w:2 | h:3 |
| w:4 | h:4 |
| w:6 | h:5 |

### Lines y counters — compactar a h:4

Líneas y counters usan **h:4 como estándar**, a menos que necesiten más espacio por:
- Eje Y rotado muy largo → `h = max(4, ceil(len_label / 4) + 2)`
- Relleno de sección → se estiran al más alto de la fila

## 7. Regla de relleno (sin espacios vacíos)

**Todos los widgets en una misma fila de sección deben estirarse a la altura del widget más alto.**

Ejemplo: si una barra tiene h=5 y los counters a su lado tienen h=2, los counters se estiran a h=4 (sec_h - 1 por el subtítulo).

```
sec_h = altura del widget más alto en la sección
counters.height = sec_h - 1  (si comparten fila con subtítulo)
```

## 8. Ejes — nombres legibles

| Regla | Detalle |
|-------|---------|
| Nunca usar | Nombres técnicos: `recibo_snr_mbd`, `quema_mmpcd` |
| Siempre usar | Nombres legibles: `Recibo SNR (Mbd)`, `Quema (MMpcd)` |
| Dónde | `encodings.x.displayName` y `encodings.y.displayName` |

## 9. Regla de división equitativa en secciones

**Widgets del mismo tipo lado a lado deben tener el mismo ancho.**

Para dividir el ancho disponible entre N widgets:
```
ancho_por_widget = ancho_disponible / N (redondeado)
```

Si el ancho no se divide exactamente, dar a cada widget el mismo ancho y ajustar el último:
```
Ejemplo: 12 cols / 2 widgets = 6 + 6 ✓
Ejemplo: 12 cols / 3 widgets = 4 + 4 + 4 ✓
Ejemplo: 6 cols / 2 widgets = 3 + 3 ✓
Ejemplo: 6 cols / 3 widgets = 2 + 2 + 2 ✓
```

**Regla:** si la sección compartida (3 cols) no permite división equitativa, convertirla en sección de fila completa (6 cols).

## 10. Grid y layout

| Regla | Detalle |
|-------|---------|
| Grid | **12 columnas** de ancho (requiere `"layoutVersion": "GRID_V1"` en la página) |
| Sin huecos | Todos los widgets borde a borde, sin celdas vacías |
| Secciones pareadas | Dos secciones lado a lado (izq 6 cols, der 6 cols) |
| Alineación vertical | Ambas secciones de una fila usan la misma `sec_h` |
| Recalcular Y | Al cambiar alturas, **siempre** recalcular todas las posiciones Y debajo |

## 11. Datasets

| Regla | Detalle |
|-------|---------|
| Definición | `name` (ID), `displayName`, `queryLines` (array de strings SQL) |
| Referencia | Widgets usan `datasetName` = `name` del dataset (el ID, no displayName) |
| Periodo anterior | Query separado con `MAX(fecha) - INTERVAL 1 DAY` |

## 12. Git ↔ Databricks

| Paso | Comando/Acción |
|------|----------------|
| Push local | `git add` + `git commit` + `git push` |
| Sync normal | `databricks repos update <ID> --branch main` |
| Si hay conflicto | **Borrar repo + recrear**: `databricks repos delete <ID>` → `databricks repos create <URL> gitHub --path <PATH>` |
| Token GitHub | Fine-grained: `Contents: Read/Write` + `Metadata: Read` |

## 13. Validación

| Qué hacer | Cómo |
|-----------|------|
| Antes de crear widgets | Exportar dashboard funcional y comparar estructura |
| Comando | `databricks workspace export "/path/to/working.lvdash.json"` |
| Contar categorías | `SELECT COUNT(DISTINCT campo) FROM (query)` |
| Medir etiquetas | `SELECT DISTINCT campo FROM (query)` → calcular max longitud |

## 14. Proceso completo para un nuevo dashboard

1. **Inventariar visuales**: tipo de widget, columnas, cálculo
2. **Consultar datos**: contar categorías, medir longitud de etiquetas
3. **Asignar orientación**: etiquetas > 8 chars → horizontal, sino vertical
4. **Calcular alturas**: regla de categorías (bars), regla de eje Y rotado (lines), regla cuadrada (pies)
5. **Diseñar grid**: secciones pareadas, rellenar huecos, recalcular Y
6. **Aplicar version correcta**: counters/tables v2, charts v3
7. **Nombrar ejes**: displayName legible en cada encoding
8. **Guardar como `.lvdash.json`** y push a Git
