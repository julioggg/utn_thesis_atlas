# CEDIA: importación completada de A, B y auditoría estructural (15 noviembre 2026)

## Evidencia reproducible del flujo de importación

Según las salidas de la terminal de CEDIA recibidas el 15-11-2026, el script `scripts/reconcile_received_validation_folder.py` validó las identidades y los formatos de los tres archivos privados en `data/revision_private/validation/recibidos_sin_validar/`, luego ejecutó importaciones explícitas, una por una, con backups previos.

- **A:** 450/450 entradas completas, 0 inválidas; 3.674 celdas humanas incorporadas a `validation/coder_A_private.csv`.
- **B:** 450/450 entradas completas, 0 inválidas; 3.395 celdas humanas incorporadas a `validation/coder_B_private.csv`.
- **Secciones:** 80 casos íntegros y disjuntos de la muestra temática; 340 celdas humanas incorporadas a `section_boundary_review_v1/section_boundary_review_private.csv`.
- **Estado estructural con código original:** 78 revisadas, 2 clasificadas como inválidas por `corrected_candidate_requires_adjudication`. Ese motivo es una corrección documental que necesita **adjudicación**, no necesariamente un error del evaluador. El auditor actualizado distingue los estados sin alterar CSV alguno.
- Se guardaron `coder_A_before_excel_import_PRIVATE.csv`, `coder_B_before_excel_import_PRIVATE.csv` y `section_boundary_review_before_excel_import_PRIVATE.csv`.
- Los tres Excel recibidos y sus handles permanecen únicamente en CEDIA, sin publicación al repositorio.

## Cambio de auditoría

Se actualizó `audit_section_boundary_review.assess_row` para que una posición corregida tras rechazar el encabezado artificial, si no hay otra contradicción, reporte `needs_adjudication` con la razón `corrected_candidate_requires_adjudication`. Si existe contradicción auténtica (`human_trim_from_boundary_safe=yes` cuando hay contenido científico, campo mal formado, etc.), la fila sigue siendo `invalid`. Este cambio es semántico, no una alteración de los dictámenes del evaluador.

### Ejecutar después de `git pull`

```bash
cd "$HOME/utn_thesis_atlas_revision"
git pull --ff-only origin main
source "$HOME/.venvs/utn-atlas-audit/bin/activate"

python scripts/audit_annotation_progress.py
python scripts/audit_section_boundary_review.py
python scripts/prepare_section_boundary_adjudication.py
```

El último comando escribe solamente la plantilla de adjudicación **privada** `data/revision_private/section_boundary_review_v1/section_boundary_adjudication_PRIVATE.csv`; si hay dos casos, quedan identificados por `review_id` y con campos del adjudicador vacíos. Incluye observaciones humanas, posiciones, contextos y referencias a la fuente; es información privada y no se debe subir a GitHub.

La persona adjudicadora debe abrir los TXT completos de `data/revision_private/validation_excel_packages/Revision_estructural_80_tesis_PRIVADO.zip` (o el documento original correspondiente), determinar el inicio correcto y la presencia de evidencia científica posterior. Debe conservar el dictamen anterior, no sustituirlo por una etiqueta fabricada para desbloquear el sistema. Solo un protocolo separado podría autorizar el recorte automático.

## Bloqueos antes de métricas de clasificación

1. A y B están completos en formato, pero **esto no verifica independencia ni origen humano real**. El archivo recibido de B contenía una atribución a Claude comunicada previamente; documentar la explicación del evaluador y si se usó asistencia automática. La declaración de ausencia de IA no se demuestra por el simple hecho de importar el archivo.
2. Es imprescindible aprobar un **libro de códigos PDOT** trazable al documento oficial, indicando que la taxonomía de seis grupos usada por el algoritmo es analítica.
3. Una vez comprobados los protocolos y congeladas las respuestas independientes, preparar **adjudicación de desacuerdos A/B**. Los resultados posteriores deben separar los 120 casos aleatorios y los 330 de enriquecimiento; no se obtienen indicadores de generalización al comparar con etiquetas no adjudicadas.
4. Ninguna de estas operaciones valida el desempeño del modelo, implica impacto sobre ODS ni autoriza publicar datos identificables de tesis.

Este documento registra resultados de comandos informados por el usuario; no afirma que los archivos privados hayan sido revisados directamente desde GitHub.
