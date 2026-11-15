# CEDIA — Evaluador C: recepción de Excel C desde data/revision_private (15-11-2026)

## Nombres de archivo y ubicación: NO MOVER

Los dos Excel que el usuario confirmó mediante captura están en:

```text
$HOME/utn_thesis_atlas_revision/data/revision_private/
├── Evaluador_C_Tematico_COMPLETADO_PROPUESTA.xlsx
└── Evaluador_C_Estructural_COMPLETADO_PROPUESTA.xlsx
```

Sus libros fueron examinados directamente como archivos adjuntos en ChatGPT. Hoja fuente de respuestas: `Evaluación C`, columnas 1–13/1–14. No es necesario moverlos, renombrarlos ni cargarlos de nuevo.

## Resultados observados en los dos Excel recibidos

| Control | Temático | Estructural |
|---|---:|---:|
| Casos / filas | 201 | 2 |
| IDs únicos | 201 | 2 |
| Respuestas principales / abstenciones con estructura válida | 201 | 2 |
| Indicaciones explícitas de asistencia IA / identidad IA | 201 | 2 |
| Temático: nota explicita "NO tercera evaluación humana independiente" | 201 | n/a |
| Temático: justificación comienza "Resumen:" | 182 | n/a |

**Alerta científica grave:** ambas hojas identifican al evaluador como `Asistencia IA · 2026-11-15`. El temático reitera que no se trata de una tercera evaluación humana independiente; por tanto, estas 203 propuestas no pueden integrarse como adjudicación humana ni justificar precisión, recall, F1 ni kappa de un modelo frente a un supuesto gold standard. El análisis local del formato no certifica que se hayan examinado las tesis completas.

La hoja estructural muestra que `SB-0022` marca `yes` al encabezado automático del 90,5213 % y a la vez asigna el inicio real al 62,591 %; la justificación indica que el candidato era una bibliografía local de un anexo. Debe resolverse mediante revisión documental independiente: no rectificar automáticamente. `SB-0039` marca `no` al encabezado automático, propone corrección a 53,4774 % y rechaza recorte por contenido pedagógico posterior. Ambos requieren revisión humana para cerrar los 80 casos.

## Preflight privado adicional: ya está implementado

`scripts/audit_uploaded_third_review_proposals.py` reconoce **exactamente** los dos nombres en `data/revision_private/`, verifica los IDs y handles contra las colas privadas congeladas de 201 y 2 casos, examina códigos y abstenciones, registra indicaciones de uso de IA y muestra advertencias de frontera contradictoria. El comando es de solo lectura; no genera etiquetas ni modifica ningún archivo.

```bash
cd "$HOME/utn_thesis_atlas_revision"
git pull --ff-only origin main
source "$HOME/.venvs/utn-atlas-audit/bin/activate"

python scripts/audit_uploaded_third_review_proposals.py
```

Resultado esperado: `STATUS: AI_ASSISTED_PROPOSAL_NOT_INDEPENDENT_HUMAN_GROUND_TRUTH`. Esto NO es un error de ejecución sino el resultado del control de procedencia. Si las identidades de la muestra no coinciden, deténgase y reporte la excepción sin mover ni modificar las fuentes.

## Siguiente etapa metodológica

- Conservar los dos archivos como **propuestas asistidas por IA** en la carpeta privada, sin sustituir las hojas A/B o registros de adjudicación y sin subirlos al repositorio público.
- Hacer una **tercera revisión humana realmente independiente** de los casos seleccionados a partir de los paquetes originales en `data/revision_private/adjudication_packages_v1/` que ocultan las respuestas A/B/IA. No mostrar al adjudicador estas propuestas ni predicciones del modelo.
- Congelar el protocolo y el libro de códigos PDOT verificable ANTES de completar dicha evaluación. Separar las seis categorías analíticas de cualquier correspondencia oficial del PDOT provincial.
- Una vez completada la tercera revisión humana, documentar procedencia y firma/fecha, controlar identidad del revisor y registrar consenso o disenso con sus razones. No presentar acuerdos con las propuestas IA como confirmación independiente.
- Los 120 casos del estrato aleatorio se mantienen separados de los 330 enriquecidos, también en el análisis final. Todas las predicciones y los textos completos siguen privados.

El estado científico es **A/B cargados, 201 casos propuestos para adjudicación temática y dos estructurales pendientes**; la adjudicación humana C **no ha sido acreditada** por estos archivos.
