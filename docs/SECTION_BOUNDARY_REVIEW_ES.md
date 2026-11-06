# Verificación privada de límites de secciones de tesis

**Contexto.** La auditoría de 7.830 tesis detectó 7.318 encabezados tardíos candidatos a bibliografía (93,46 % del corpus); 5.749 de ellos tienen anexos posteriormente detectados. En estas tesis, el encabezado tardío se situó en la mediana al 88,62 % del texto, con 11,38 % de texto por detrás. **Ninguna coincidencia automática ha sido validada manualmente.**

## Objetivo

Evaluar la sensibilidad y los falsos positivos de los detectores de encabezados, y determinar si sería defendible eliminar referencias bibliográficas o limitar el análisis a secciones científicas centrales. No se modifican textos originales ni se generan nuevas etiquetas ODS/PDOT.

Una muestra **intencionadamente equilibrada de 80 tesis** incluye 20 por cada uno de los cuatro estratos:

- Encabezado tardío de bibliografía y anexos posteriores.
- Encabezado tardío de bibliografía sin anexos posteriores detectados.
- Encabezado de referencias únicamente temprano.
- Ningún encabezado de referencias detectado.

Esto permite examinar fallos y casos límite; **no es una muestra probabilística representativa** y sus tasas brutas no deben interpretarse como tasas de error de todo el corpus.

Para impedir la contaminación de la validación de clasificación, se excluyen todas las 450 tesis de la muestra humana anterior. Los archivos originales de dicha muestra no se modifican.

## Comandos de preparación en CEDIA

```bash
cd "$HOME/utn_thesis_atlas_revision"
git pull --ff-only origin main
source "$HOME/.venvs/utn-atlas-audit/bin/activate"

python scripts/prepare_section_boundary_review.py \
  --project-root "$HOME/utn_thesis_atlas" \
  --per-stratum 20 \
  --seed 20261106 \
  --late-fraction 0.55 \
  --private-output-dir data/revision_private/section_boundary_review_v1 \
  --output docs/audits/section_boundary_review_design.json

cat docs/audits/section_boundary_review_design.json
```

**No volver a ejecutar este programa con los mismos nombres de salida después de preparar o editar la hoja.** El programa se niega a sobrescribirla.

El archivo privado `data/revision_private/section_boundary_review_v1/section_boundary_review_private.csv` incluye enlaces de acceso a los documentos, encabezados candidatos, posición de los encabezados y fragmentos contextuales. Contiene texto fuente potencialmente sensible: **no subir ni copiar este CSV a GitHub**.

El informe `docs/audits/section_boundary_review_design.json` contiene solo cuentas agregadas y puede publicarse después de revisión del investigador.

## Rúbrica del evaluador humano

Para cada una de las 80 tesis, revisar el documento original, incluyendo el índice, el contenido inmediatamente antes y después del encabezado y sus anexos. Completar las siguientes columnas del CSV privado:

| Campo | Respuesta |
|---|---|
| human_heading_is_real_references_start | yes / no / uncertain |
| human_corrected_boundary_fraction | Fracción 0–1 si se puede identificar correctamente el inicio de referencias |
| human_tail_contains_scientific_contribution | yes / no / uncertain |
| human_trim_from_boundary_safe | yes / no / uncertain |
| human_notes | Motivo breve y evidencia de la decisión |

Recomendamos verificar las decisiones inciertas con un segundo evaluador; si se declara una tasa de precisión de límites, registrar por separado la concordancia y el criterio de adjudicación.

Una coincidencia con el título "Referencias" NO prueba que todo el texto posterior sea bibliografía: puede haber anexos con resultados, instrumentos, fotografías, datos o código relevantes. Se recomienda diferenciar **exclusión solo de referencias** frente a **exclusión de todo el tramo posterior**.

## Resultado posterior

Si la revisión confirma que la detección de límites es suficientemente fiable, diseñar tres variantes comparables sobre los mismos textos: (1) texto completo, (2) texto completo sin bibliografía identificada de forma validada y con anexos preservados o gestionados explícitamente, (3) selección de secciones científicas. Evaluar en piloto la cobertura y los embeddings; después comparar con las etiquetas humanas independientes de ODS/PDOT.

No usar la menor similitud entre tesis como indicador sustituto de exactitud.


## Auditoría de integridad y avance de la revisión humana

Después de preparar la muestra de 80 tesis, comprobar que el archivo privado permanece íntegro. Este comando **solo lee el CSV privado y el maestro de las 450 tesis** y escribe un resumen agregado.

```bash
cd "$HOME/utn_thesis_atlas_revision"
git pull --ff-only origin main
source "$HOME/.venvs/utn-atlas-audit/bin/activate"

python scripts/audit_section_boundary_review.py \
  --private-csv data/revision_private/section_boundary_review_v1/section_boundary_review_private.csv \
  --validation-master data/revision_private/validation/sample_master_private.csv \
  --output docs/audits/section_boundary_review_progress.json

cat docs/audits/section_boundary_review_progress.json
```

Antes de la codificación manual, el resultado esperado es: `sample_rows=80`, `total_not_started=80`, `total_reviewed=0`, `total_invalid=0`, sin solapamiento con las 450 tesis de validación temática. Si el resultado es diferente, no editar ni regenerar los datos sin inspeccionar el problema.

Las respuestas de las tres columnas `human_heading_is_real_references_start`, `human_tail_contains_scientific_contribution` y `human_trim_from_boundary_safe` deben ser `yes`, `no` o `uncertain`. Una respuesta `uncertain` permanece pendiente de adjudicación. Una decisión `yes` sobre eliminar el tramo final es lógicamente incompatible con afirmar que el tramo contiene contribución científica. El script marca estas contradicciones, pero **no reemplaza el juicio humano**.

Si revisas el resumen y confirmas que solo contiene conteos agregados, puedes publicar **únicamente** `docs/audits/section_boundary_review_progress.json` siguiendo `scripts/git_safety.py`. No publicar nunca el archivo `section_boundary_review_private.csv`, que contiene fragmentos de textos originales y referencias a tesis.
