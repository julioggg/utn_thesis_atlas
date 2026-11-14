# Auditoría de correspondencia documental del PDOT Imbabura para revisión mayor

**Preparado:** 14 de noviembre de 2026. **Estado:** fuentes institucionales identificadas; correspondencia entre descriptores del clasificador y fuentes del PDOT **todavía NO validada**.

## Documentos normativos y oficiales identificados

1. **PDOT provincial Imbabura 2023–2027.** Prefectura, [repositorio oficial](https://www.imbabura.gob.ec/index.php/pdot-aprobado-2023-2027), publicado como [PDF técnico del 30 de octubre de 2024](https://www.imbabura.gob.ec/index.php/pdot-aprobado-2023-2027/file/2656-pdot-imbabura-2023-2027).
2. **Ordenanza Provincial 005-PCI-2024**, aprobación de la actualización del PDOT 2023–2027 ([texto institucional](https://www.imbabura.gob.ec/phocadownloadpap/S-Actos-legislativos/Ordenanzas/ordenanzas2024/ordenanza-provincial-nro-005-pci-2024.pdf)), registrada en la edición especial del Registro Oficial 2160 del 5 de marzo de 2025 ([referencia oficial](https://www.registroficial.gob.ec/edicion-especial-no-2160/)).
3. **Ordenanza Provincial 001-PCI-2026**, reforma del PDOT 2023–2027 y alineación al Plan Nacional de Desarrollo 2025–2029. Fechada 12 de febrero de 2026 ([PDF del GAD provincial](https://www.imbabura.gob.ec/phocadownloadpap/S-Actos-legislativos/Ordenanzas/2026/ordenanza_provincial_nro_001-pci-2026.pdf)). El [repositorio de documentos oficiales](https://www.imbabura.gob.ec/index.php/pdot-aprobado-2023-2027) publica también versión aprobada/descargable de marzo de 2026.
4. **Secretaría Nacional de Planificación.** [Guía oficial para formulación/actualización PDOT 2023–2027](https://planificacion.presidencia.gob.ec/guia-para-la-formulacion-actualizacion-de-los-planes-de-desarrollo-y-ordenamiento-territorial/), aprobada por Acuerdo SNP-SNP-2023-0049-A.

## Discrepancia que requiere tratamiento metodológico

La exposición de motivos de la reforma provincial 001-PCI-2026 enumera **seis componentes territoriales**: físico ambiental; social cultural; económico productivo; asentamientos humanos; movilidad, energía y conectividad; político institucional.

En el atlas computacional original, las **seis categorías de similitud PDOT** incluyen un eje combinado `Asentamientos Humanos Movilidad Energía Conectividad` y uno `Ejes Transversales`. Esta taxonomía no es, de forma literal, el mismo conjunto de seis componentes descrito por la Ordenanza 001-PCI-2026. Se debe verificar el PDOT original completo de 2024 y la trazabilidad de los descriptores antes de presentarlos como etiquetas oficiales.

**Hipótesis posibles para contrastar, sin asumir cuál es cierta:** los seis rótulos del atlas pudieron resumir un esquema administrativo anterior, agrupar categorías como decisión analítica, o contener una etiqueta sintética de ejes transversales; también pudieron definirse con una guía diferente. No asignarles origen institucional hasta documentarlo.

## Conflicto de implementación

El inventario AST privado encontró:
- `utn_atlas_pipeline.py:PDOT`, seis etiquetas.
- `utn_atlas_q1_extras.py:PDOT_MAP`, seis etiquetas, **descripciones incompatibles** según reconciliación V2.
- `utn_atlas_pipeline.py:ODS`, 17 etiquetas.
- `utn_atlas_pipeline.py:NEEDS`, diez necesidades locales.

La reconciliación V2 completó únicamente correspondencias de ODS y NEEDS; los seis textos PDOT quedaron sin preselección debido al conflicto. **No se ha determinado todavía qué variable generó `07_alignment_pdot_ods_needs.parquet`.**

El nuevo script `scripts/reviewer_pdot_source_lineage.py` coteja hash SHA256 de los scripts de origen contra el inventario congelado, compara todas las descripciones por eje y recoge referencias AST a `PDOT` y `PDOT_MAP` sin ejecutar código. Los valores completos y las líneas del script quedan exclusivamente en `data/revision_private/descriptor_inventory/pdot_source_lineage_PRIVATE.json` en CEDIA.

### Ejecución

```bash
cd "$HOME/utn_thesis_atlas_revision"
git pull --ff-only origin main
source "$HOME/.venvs/utn-atlas-audit/bin/activate"

python scripts/reviewer_pdot_source_lineage.py \
  --project-root "$HOME/utn_thesis_atlas"

cat docs/audits/reviewer_pdot_source_lineage_status.json
```

El resumen público no incluye cadenas de descriptores, ni tesis ni rutas personales. El diagnóstico AST aporta evidencia de linaje, pero no prueba por sí solo qué ejecución histórica usó cada variable; revisar llamadas, versiones y fecha de ejecución.

## Decisión para el artículo

Mantener separado (a) el PDOT documental oficial, con edición/vigencia explícita; (b) la taxonomía analítica usada en el pipeline original; y (c) un posible nuevo conjunto de descriptores derivado de la versión oficial actual, siempre con fuente y versión. Comparar sensibilidad entre (b) y (c) si se justifica metodológicamente, **sin reetiquetar retrospectivamente las predicciones originales**.

Una alineación coseno entre tesis y descriptores PDOT es afinidad semántica respecto al texto escogido, no una medida directa de ejecución o impacto de políticas provinciales.
