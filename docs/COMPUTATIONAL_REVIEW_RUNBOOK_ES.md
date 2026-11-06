# Revisión mayor de *Sustainability*: ejecución computacional integral en CEDIA

## Estado y procedencia

El editor emitió **major revision** el 3 de noviembre de 2026. Los cuatro revisores piden validación independiente, E5 fulltext, umbrales, comparación contra baseline léxico, sensibilidad a descriptores y modelos, correcciones estadísticas y figuras consistentes.

**Código implementado NO equivale a análisis ejecutado**: los datos privados y GPUs residen en CEDIA, no en GitHub. Las pruebas sintéticas de GitHub verifican lógica de programas, pero no reproducen resultados con las 7.830 tesis.

| Análisis | Archivo | Base de datos | ¿Puede ejecutarse sin codificadores? |
|---|---|---|---|
| Estadística, cinco facultades, ODS 4, rarefacción, dispersion, post hoc, umbrales, cobertura candidata | `scripts/reviewer_stage1_stats.py` | 07 + 05 | Sí |
| Centroides, kNN, Rao–Stirling, puentes y tendencias 2021–25 | `scripts/reviewer_stage2_geometry.py` | 07 + 05 | Sí |
| k=50/75/100 y estabilidad de semillas UMAP | `scripts/reviewer_stage3_stability.py` | 07 + 05 | Sí, con dependencias |
| Tablas 2/3 y figuras 3/4/5 de base original sin validación | `scripts/reviewer_rebuild_figures.py` | 07 | Sí |
| Descubrimiento de código fuente de descriptores | `scripts/reviewer_descriptor_inventory.py` | scripts/configs originales | Sí |
| Manifiesto privado **vacío** para preservar procedencia | `scripts/reviewer_prepare_descriptors.py` | etiquetas existentes | Sí |
| E5-large vs E5-base con las mismas tesis/fragmentos | `scripts/reviewer_alternate_encoder_pilot.py` | 04 + GPU | Sí, sujeto a descarga de modelo |
| Descriptores reescritos, top2, mean-center, abstención | `scripts/reviewer_descriptor_sensitivity.py` | 05 + manifiesto | Solo después de verificar manualmente los descriptores |
| TF-IDF léxico 1–2 gramas frente a E5 | `scripts/reviewer_keyword_baseline.py` | 07 + manifiesto | Solo después de verificar manualmente los descriptores |
| Kappa, etiquetas adjudicadas, precision/recall/F1, calibración 330 vs prueba 120 | `scripts/reviewer_human_validation_metrics.py` | 450 fichas humanas | **No**: requiere dos evaluadores y adjudicación real |

Ningún algoritmo inventa etiquetas humanas ni elimina anexos. Las cifras de similitud siguen siendo **alineación temática**, no impacto real en sostenibilidad.

## 1. Preparación de entorno CEDIA

Dentro de Singularity con las particiones MIG ya comprobadas:

```bash
cd "$HOME/utn_thesis_atlas_revision"
git pull --ff-only origin main
source "$HOME/.venvs/utn-atlas-audit/bin/activate"

python -m pip install 'scikit-learn>=1.4,<2' 'umap-learn>=0.5,<0.7' 'matplotlib>=3.7,<4'

python - <<'PY'
import numpy, pandas, scipy, sklearn, umap, matplotlib, torch
print("CUDA disponible:",torch.cuda.is_available())
print("scikit-learn:",sklearn.__version__)
print("UMAP:",umap.__version__)
PY
```

El nuevo modelo `intfloat/multilingual-e5-base` no forma parte del caché verificado de CEDIA. El comando integral incluye una opción explícita para autorizar la descarga del modelo. Si Hugging Face no está disponible, ese paso fallará por separado y el resto de auditorías seguirá ejecutándose.

## 2. Ejecutar toda la suite sin inventar referencias

```bash
python scripts/run_reviewer_computational_suite.py \
  --project-root "$HOME/utn_thesis_atlas" \
  --stages all \
  --allow-model-download \
  --suite-id reviewer_suite_v1 \
  --output docs/audits/reviewer_suite_run_status.json

cat docs/audits/reviewer_suite_run_status.json
```

**Comportamiento esperado**: las estadísticas, geometría, estabilidad, figuras, inventario y comparación de encoders se intentan automáticamente. El generador de plantilla de descriptores se niega a sobrescribir versiones existentes; los pasos que requieren descriptores **se marcan como bloqueados** hasta que el investigador revise la procedencia y complete el manifiesto `data/revision_private/descriptor_inventory/verified_descriptors_PRIVATE.json`.

Si falla algún paso, revisar **solo localmente** los logs privados:

`data/revision_private/computational_suite/reviewer_suite_v1/<etapa>.log`

No publicar logs: podrían contener rutas internas y material sensible.

## 3. Recuperar descriptores originales sin inventarlos

Abrir únicamente en CEDIA:

`data/revision_private/descriptor_inventory/descriptor_source_candidates_PRIVATE.json`

Verificar en el código ORIGINAL los 17 descriptores ODS, seis ejes PDOT y diez necesidades locales; registrar título/versión del PDOT, fuente de las diez necesidades y quien escribió los descriptores. El código `reviewer_prepare_descriptors.py` deja vacíos `descriptor`, `paraphrase_1`, `paraphrase_2`, `source_document`, `source_location`, `verified_by`. Tras completarlos y congelarlos, marcar `verified: true` **solo con autorización del investigador**, y ejecutar:

```bash
python scripts/run_reviewer_computational_suite.py \
  --project-root "$HOME/utn_thesis_atlas" \
  --stages descriptors,keywords \
  --suite-id reviewer_verified_descriptors_v1 \
  --output docs/audits/reviewer_verified_descriptor_run_status.json
```

Al publicar, se puede compartir una copia revisada y autorizada de los descriptores (sin identificadores ni texto de tesis) con licencia apropiada. La matriz de puntuaciones por tesis queda privada.

## 4. Verificar, revisar y publicar agregados

Los informes candidate a publicar están en `docs/audits/`. Primero comprobar **valores, limitaciones y privacidad**; luego añadir solamente los JSON de salida revisados individualmente. Por ejemplo:

```bash
cat docs/audits/reviewer_suite_run_status.json

git add docs/audits/reviewer_suite_run_status.json
python scripts/git_safety.py
git diff --cached --stat
git commit -m "Record reviewer computation suite status"
git push origin main
```

No ejecutar `git add -A` sin revisar. **Nunca** subir `data/`, texto completo, hojas de codificadores, puntuaciones individuales, documentos, nombres de autores, identificadores ni embeddings.

Las figuras actuales se generan solamente en `data/revision_private/reviewer_publication_figures` y describen el **modelo legacy no validado**. No son figuras finales del artículo hasta congelar la nueva clasificación y validar su calidad.

## 5. Por qué no se puede declarar resuelta la revisión

1. Los dos evaluadores aún no han anotado las 450 tesis; los dos conjuntos codificados están en blanco.
2. La revisión estructural de 80 tesis aún no ha adjudicado límites de bibliografía/anexos; recortar automáticamente es prematuro.
3. Los nuevos embeddings fulltext del corpus completo, bajo un protocolo aceptado, siguen pendientes: se procesaron 12 tesis en el piloto y 854.145 ventanas fueron estimadas exactamente por censo.
4. Los descriptores originales y las diez necesidades deben documentarse desde la fuente, no deducirse de nombres de categorías.
5. Los cambios de manuscrito (título, marco regulatorio ecuatoriano, ética, licencias, referencias y respuestas punto a punto) son independientes de estos cálculos.
6. La cifra k=75 original tiene silhouette 0,056761 frente a k=50 con 0,056471. El estudio nuevo KMeans/UMAP diagnostica sensibilidad, **no reproduce necesariamente la metodología original**.

**No enviar al editor resultados no ejecutados, falsos indicadores de impacto, inferencias basadas en UMAP hulls ni tasas poblacionales calculadas de la muestra enriquecida.**
