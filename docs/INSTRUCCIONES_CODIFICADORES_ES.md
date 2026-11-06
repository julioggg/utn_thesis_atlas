# Instrucciones operativas para dos evaluadores independientes (versión preliminar)

Este archivo explica cómo usar los formularios privados de 450 tesis generados en CEDIA. La documentación de criterios temáticos y el protocolo de desacuerdos están en ANNOTATION_PROTOCOL.md. **La preparación de formularios NO equivale a validación.**

## Antes de comenzar

1. Obtener las autorizaciones institucionales y confirmar la versión exacta del PDOT de Imbabura y la rúbrica oficial que respalda los seis ejes usados en el artículo.
2. Seleccionar a dos evaluadores con experiencia pertinente en investigación, sostenibilidad y planificación territorial. Sus codificaciones deben ser genuinamente independientes; no utilizar ni mostrar resultados del modelo.
3. Realizar primero una práctica de unas 20 tesis **fuera** de la muestra de 450. Resolver dudas y congelar el manual de codificación.
4. El coordinador conserva el archivo maestro; cada evaluador recibe únicamente su hoja correspondiente y acceso legítimo a los documentos.
5. No volver a ejecutar prepare_blinded_validation_sample.py cuando los evaluadores hayan comenzado: **recrea los CSV y puede sobrescribir trabajo**. Crear previamente una copia protegida y conservar el original.

## Archivos internos (no publicar)

En data/revision_private/validation/ se encuentran:

- sample_master_private.csv: uso exclusivo del coordinador; contiene los estratos, identificadores y predicciones de la versión original.
- coder_A_private.csv: evaluación ciega del primer especialista.
- coder_B_private.csv: evaluación ciega del segundo especialista.

No subir los CSV a GitHub, no enviarlos sin autorización y no cambiar study_id, private_source_handle ni el número de filas.

## Cómo llenar cada fila

Cada persona examina objetivos, problema investigado, metodología, resultados y conclusiones. No se infiere correspondencia ODS/PDOT por la mera mención de términos en una bibliografía o por ser una tesis universitaria.

| Columna | Qué escribir |
|---|---|
| sdg_primary | Código ODS 1 a ODS 17, por ejemplo ODS 4 |
| sdg_secondary | Opcional: un segundo ODS distinto del primario |
| sdg_no_match | yes solo si no hay correspondencia ODS sustentable; en ese caso dejar los códigos vacíos |
| pdot_primary | Código PDOT 1 a PDOT 6, por ejemplo PDOT 2 |
| pdot_secondary | Opcional: un segundo eje PDOT diferente |
| pdot_no_match | yes solo si no hay correspondencia PDOT sustentable |
| uncertain | yes o no, según la incertidumbre del evaluador |
| brief_evidence | Ubicación concreta de la evidencia: sección, capítulo o página; no basta una etiqueta aislada |
| coder_notes | Observaciones, texto ilegible, falta de documento o ambigüedad |

Escribir **no** en las banderas de no correspondencia cuando exista una etiqueta primaria. No copiar automáticamente los resultados originales ni utilizar un LLM como sustituto de los evaluadores humanos.

## Auditoría automática de integridad y progreso

Ejecutar desde la copia de revisión en CEDIA:

    cd "$HOME/utn_thesis_atlas_revision"
    git pull --ff-only origin main
    source "$HOME/.venvs/utn-atlas-audit/bin/activate"

    python scripts/audit_annotation_progress.py \
      --private-dir data/revision_private/validation \
      --output docs/audits/annotation_progress.json

    cat docs/audits/annotation_progress.json

El resultado es agregado y no contiene etiquetas individuales. Antes de distribuir los archivos, ambos deberían mostrar 450 filas no iniciadas y cero codificaciones completas. Si no coincide, revisar las hojas privadas localmente.

El chequeo verifica códigos, referencias de tesis, duplicados, banderas yes/no, conflictos entre no correspondencia y etiquetas, y existencia de evidencia textual. La herramienta **no** verifica si un juicio es científicamente correcto.

## Evaluación estadística posterior

Tras terminar y congelar ambas hojas, preservar sus versiones originales, medir acuerdo entre evaluadores, adjudicar discrepancias con un tercero y evaluar las predicciones de los modelos contra esa referencia. Reportar el subconjunto aleatorio y el enriquecido **por separado**: no interpretar las proporciones de las 450 tesis como prevalencias representativas de las 7.830.

La capacitación y la elaboración del protocolo son independientes de la comparación computacional de distintas estrategias de embeddings.
