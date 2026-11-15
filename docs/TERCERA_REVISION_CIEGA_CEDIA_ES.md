# Paquetes para tercera evaluación ciega — 201 tesis y 2 fronteras pendientes

**Hallazgos reales del usuario en CEDIA, 15-11-2026:**

- 450 casos completos por evaluador temático A y B (misma muestra, dos archivos privados).
- La lista de revisión contiene **201/450 casos distintos** (44,7 %).
- Motivos superpuestos, NO mutuamente excluyentes: diferencias en ODS (incluidas etiquetas secundarias o bandera de no correspondencia) n=104; PDOT n=99; al menos un indicador de incertidumbre n=63; alguna bandera no-match n=3. NO deducir de estos números el acuerdo exacto en etiqueta primaria.
- Auditoría estructural: 78 revisados sin señal de conflicto lógico; **SB-0022 y SB-0039** requieren interpretación documental, 0 inválidos tras corregir semántica del auditor.
- **NO hay aún consenso adjudicado ni evaluación de precisión del clasificador E5.**

## Preparar paquetes con TESIS COMPLETAS para tercero C

Se creó `scripts/export_third_reviewer_blinded_packets.py`. Verifica que las colas privadas congeladas coincidan con los registros originales de A/B y estructura, coteja los handles contra el parquet original y extrae el texto completo de cada uno. No necesita GPU ni recalcula embeddings.

```bash
cd "$HOME/utn_thesis_atlas_revision"
git pull --ff-only origin main
source "$HOME/.venvs/utn-atlas-audit/bin/activate"

python scripts/export_third_reviewer_blinded_packets.py \
  --project-root "$HOME/utn_thesis_atlas"

ls -lh data/revision_private/adjudication_packages_v1/*.zip
```

Dos ZIP en `data/revision_private/adjudication_packages_v1/`:

- `Evaluador_C_Tematico_CIEGO_PRIVADO.zip`: hoja de respuestas en blanco para 201 casos (cantidad recalculada a partir de la cola), tabla de fuentes y `Evidencias/TH-XXXX.txt` con **201 textos completos originales**; incluye los 17 ODS y 6 categorías PDOT analíticas, más instrucciones.
- `Evaluador_C_Estructural_CIEGO_PRIVADO.zip`: hoja de respuestas independiente para dos casos estructurales, con candidato automático, contextos, y `Evidencias/SB-XXXX.txt`.

**Control de cegamiento:** los paquetes no contienen decisiones A, B, sus notas, sus discrepancias, descriptores o predicciones de E5, ni estratos de muestreo. El tercero C registra su propio juicio antes de ver otras respuestas. Una vez congelada su revisión, un experto coordinador puede hacer la conciliación documentada utilizando el CSV privado de comparación A/B.

**Privacidad:** los ZIP completos NO están cifrados; usar únicamente canales autorizados con control de acceso. No enviar a GitHub público, repositorios externos ni canales sin permiso para los textos íntegros.

## Qué debe hacer C

1. Extraer el ZIP antes de abrir rutas relativas a `Evidencias/`. Cada registro del Excel cita su TXT completo.
2. Para el temático, revisar contribución real y evidencia; llenar `sdg_primary`, `sdg_secondary`, `sdg_no_match`, `pdot_primary`, `pdot_secondary`, `pdot_no_match`, `uncertain`, `brief_evidence`, `coder_notes` e identidad/fecha.
3. Para el estructural, evaluar el encabezado, proponer frontera correcta si la evidencia permite identificarla, documentar si la cola contiene resultados científicos y solo aprobar recortes si encabezado auténtico y ninguna contribución posterior.
4. No consultar respuestas A/B ni usar IA para decidir categorías bajo el protocolo de evaluación independiente.
5. Requiere **libro de códigos PDOT aprobado y trazable** antes de iniciar codificación temática: los seis rótulos del atlas son analíticos y no se han verificado como transcripción oficial del instrumento 2023–2027.

Los CSV de discrepancias de A/B y estructura permanecen en CEDIA y NO se entregan al tercero durante la primera codificación independiente. Estos archivos tampoco se alteran al generar el paquete.

## Plan de resultados y precauciones

Después de recibir C, congelar sus respuestas y desarrollar consenso/adjudicación documentada; registrar casos sin correspondencia y ambigüedad sin forzarlos a una categoría. Únicamente después de aprobar el protocolo y consenso con trazabilidad se estimará precisión y F1 de E5, manteniendo 120 tesis del estrato aleatorio como prueba separada de las 330 enriquecidas.

**Proveniencia:** el Excel B recibido tenía una declaración de generación por Claude, aunque el evaluador manifestó que hizo la revisión personalmente. La importación formal y la completitud no verifican su proceso. Documentar por escrito la distinción entre revisión efectuada por humano, asistencia IA y cualquier intervención en decisión de etiquetas antes de llamar `ground truth` a las respuestas.
