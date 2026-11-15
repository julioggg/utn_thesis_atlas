# CEDIA: importar los tres Excel recibidos sin moverlos ni renombrarlos

**Entrada común privada**:
`$HOME/utn_thesis_atlas_revision/data/revision_private/validation/recibidos_sin_validar/`

La carpeta fue seleccionada por el coordinador; todo permanece en `data/revision_private` (excluida de GitHub).

**Archivos originales esperados (nombres exactos):**

- `Validacion_A_450_ODS_PDOT.xlsx`
- `Validacion_450_ODS_PDOT_B.xlsx`
- `Plantilla_revision_estructural_80_tesis_COMPLETA (1).xlsx`

No volver a cargar, renombrar, copiar ni desplazar los archivos. No subir Excel, respuestas, handles ni textos del repositorio institucional al GitHub público.

## 1. Actualizar el código en CEDIA

```bash
cd "$HOME/utn_thesis_atlas_revision"
git pull --ff-only origin main
source "$HOME/.venvs/utn-atlas-audit/bin/activate"
```

## 2. Revisión previa obligatoria — lectura solamente

```bash
python scripts/reconcile_received_validation_folder.py
```

Este comando recorre los tres Excel en su carpeta original y coteja **todos los 450+450+80 IDs con los maestros CEDIA congelados**, sus handles, metadatos originales y categorías admisibles. Reporta únicamente agregados, el número de campos completados y huellas SHA-256 de cada archivo. También distingue casos estructurales revisados, inválidos y pendientes de adjudicación.

**Si aparece cualquier error, no aplicar nada.** Copiar el mensaje de error al coordinador para resolver exclusivamente el formato o una discrepancia de identidad; no inventar ni cambiar decisiones humanas para lograr un estado positivo.

Los dos casos estructurales SB-0022 y SB-0039 identificados previamente por el coordinador pueden quedar como **pendientes de adjudicación**. La importación puede registrar revisiones y sus problemas, pero NO aprobar recortes automáticos ni declarar los 80 casos finalizados.

## 3. Importación privada — uno por vez, exclusivamente después de preflight correcto

**A** (archiva la respuesta en `data/revision_private/validation/coder_A_private.csv` con copia de seguridad automática):

```bash
python scripts/reconcile_received_validation_folder.py --apply A
```

**B** (mismo procedimiento sobre `coder_B_private.csv`):

```bash
python scripts/reconcile_received_validation_folder.py --apply B
```

**80 estructurales** (sobre `data/revision_private/section_boundary_review_v1/section_boundary_review_private.csv`):

```bash
python scripts/reconcile_received_validation_folder.py --apply 80
```

No existe la opción `--apply all`: cada operación queda aislada. Los importadores originales impiden sobrescribir respuestas humanas ya registradas y rehúsan una segunda importación si la copia de seguridad ya existe.

**La importación es un registro administrativo de anotaciones recibidas**, no una declaración de que la codificación fue independiente, correcta o libre de IA.

## 4. Recalcular progreso agregado

```bash
python scripts/audit_annotation_progress.py
python scripts/audit_section_boundary_review.py
```

Esperar un resultado que resuma completitud de A/B y 80, incluidos los casos con inconsistencias. Si en estructura persisten correcciones de límite bajo un encabezado clasificado como incorrecto, el auditor reportará `corrected_candidate_requires_adjudication`; deben resolverse mediante comprobación documental genuina, no recodificando para ocultar errores.

**No ejecutar métricas de exactitud, F1, Cohen kappa, ni publicar tablas de resultados humanos** hasta aprobar un libro de códigos PDOT trazable, verificar las respuestas del evaluador B respecto a la mención documental de Claude y congelar la adjudicación independiente. No interpretar los cambios de embeddings como precisiones humanas.

## Qué cambió en GitHub

- `scripts/reconcile_received_validation_folder.py`: preflight de los **tres nombres existentes** y comandos `--apply A|B|80` sin mover Excel.
- `scripts/import_section_boundary_excel.py`: admite diferencias inocuas de serialización Excel en números y saltos de línea **sin permitir cambios sustantivos** en las nueve columnas originales congeladas.
- `tests/test_reconcile_received_validation_folder.py`: prueba A/B/80 con datos sintéticos y garantiza que el preflight no modifica los originales.

Los archivos Excel se conservan únicamente en CEDIA, y al repositorio público se suben **códigos, pruebas y documentación**. Los reportes posteriores de progreso solo pueden incluir cifras agregadas revisadas por privacidad.
