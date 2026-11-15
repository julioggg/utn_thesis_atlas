# Protocolo operativo tras declaración de autoría humana de A, B y C

**15 de noviembre de 2026.** El coordinador comunicó que los revisores A/B/C sostienen haber asignado personalmente las categorías de las tesis y que las marcas de IA de sus hojas se refieren exclusivamente a **formato o agilización de la redacción**, no a generación de las decisiones de clasificación.

## Trazabilidad científica

- La declaración verbal comunicada por el coordinador es relevante y **permite avanzar con análisis descriptivo de concordancia**. No prueba por sí sola independencia; no cambiar ni borrar la procedencia explícita de los archivos.
- El Excel C contiene literalmente `NO tercera evaluación humana independiente` en sus 201 casos y un valor `Asistencia IA` en identidad. Eso entra en conflicto textual con la declaración posterior: obtener una **aclaración escrita atribuible a cada evaluador**, explicando el alcance exacto del uso de IA, si leyó textos completos, si consultó etiquetas A/B o E5, y si ratifica las decisiones que figuran en su Excel. La aclaración se anexa al expediente en carpeta privada, sin reescribir los archivos.
- Las 182/201 justificaciones C que comienzan por `Resumen:` requieren especial control de calidad: verificar una selección de las respectivas tesis completas y documentar fuentes de evidencia de resultados y conclusiones. No inferir que el revisor no consultó las tesis únicamente por el texto abreviado, pero tampoco darlo por comprobado.
- Las seis categorías PDOT son **analíticas**; preparar un libro de códigos aprobado con criterios de inclusión/exclusión y trazabilidad al documento territorial oficial antes de fijar el gold standard.

## Paso computacional, seguro y ejecutable ahora

Se añadió `scripts/reviewer_three_coder_comparison.py`. Trabaja con el registro maestro privado, A, B y el Excel C **tal como fue recibido** en `data/revision_private/`. Comprueba IDs y handles, códigos C, diferencias de etiquetas principales y produce:

- `docs/audits/reviewer_ab_c_primary_agreement_descriptive.json`: SOLO métricas agregadas, acuerdo y kappa A/B separados en **120 aleatorios** y **330 enriquecidos**, y patrones A/B/C **en los 201 casos seleccionados**.
- `data/revision_private/validation/three_coder_comparison_PRIVATE.csv`: cola privada con las propuestas de A/B/C y **seis campos de consenso final completamente vacíos**. No se asume que la mayoría constituya adjudicación verdadera.

```bash
cd "$HOME/utn_thesis_atlas_revision"
git pull --ff-only origin main
source "$HOME/.venvs/utn-atlas-audit/bin/activate"

python scripts/reviewer_three_coder_comparison.py
```

**No repetir** `reconcile_received_validation_folder.py --apply`, porque A/B/80 ya están importados y respaldados. No ejecutar `reviewer_human_validation_metrics.py --adjudicated` hasta construir un documento de referencia consensuado y aprobado, que no se crea automáticamente.

## Guardar los descargos de los revisores

Guardar las declaraciones originales en una carpeta privada:

```bash
mkdir -p "$HOME/utn_thesis_atlas_revision/data/revision_private/validation/provenance_declarations"
```

Cada declaración debe contener identidad y rol del revisor, fecha, nombre del Excel ratificado, declaración de que examinó las fuentes originales, si decidió ODS y PDOT personalmente, detalles de herramientas IA usadas (solo edición de redacción o sugerencias de clasificación), independencia respecto de A/B y E5, y explicación de por qué el libro conserva mensajes como `NO tercera evaluación humana independiente`. **No exigir declaración falsa**; aceptar y registrar cualquier intervención IA que efectivamente ocurrió. Una transcripción preparada por el coordinador debe identificarse como tal hasta ser ratificada por el revisor.

## Paso humano de adjudicación

1. Revisar el CSV privado de comparación. Las etiquetas C sirven para orientar la revisión, pero **nadie acepta la mayoría automáticamente**.
2. Confirmar con los documentos originales los casos con desacuerdo A/B y las excepciones de fuente. Documentar acta de consenso por los expertos.
3. Los casos de consenso A=B que no entraron en los 201 deben mantener la trazabilidad de ambas fuentes; no presuponer que la no selección por sí sola prueba veracidad.
4. Resolver estructuralmente SB-0022 y SB-0039 con el TXT/PDF original y registrar su dictamen, manteniendo la restricción de no recortar contenido científico.
5. Solo con etiquetas finales ratificadas, libro PDOT aprobado y procedencia documentada, implementar la evaluación independiente de E5 (incluido fulltext raw y centered) sobre las 120 aleatorias; las 330 enriquecidas pueden servir para calibración de abstención.

**Limitación:** el acuerdo A/B es una propiedad de consistencia entre revisores, NO exactitud de E5; la evaluación C está condicionada a 201 casos seleccionados por reglas de discrepancia y no puede extrapolarse a las 450 ni a las 7.830 tesis.
