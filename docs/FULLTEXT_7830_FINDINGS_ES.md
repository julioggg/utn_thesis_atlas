# 7.830 tesis: resultado E5 fulltext y advertencia sobre anisotropía

**Fecha de análisis:** 14 de noviembre de 2026. **Base verificada:** `docs/audits/fulltext_e5_large_full_corpus_v1.json` y `docs/audits/fulltext_vs_legacy_7830_comparison.json` (commit `14d303b`).

## Cobertura computacional y reproducibilidad

- Corpus: **7.830 tesis**, orden 04/05-index/06/07 idéntico.
- Total **286.050.084 tokens** de contenido E5, **854.145 ventanas**.
- Arquitectura: **dos shards pares/impares** de 3.915 tesis; ejecución secuencial sobre una MIG después de recuperar 2.144 tesis validadas por checkpoints.
- Checkpoints finales: **490**; cada tesis posee embedding privado unitario de **1.024 dimensiones**.
- Modelo: `intfloat/multilingual-e5-large`, revisión `3d7cfbdacd47fdda877c5cd8a79fbcc4f2a574f3`; prefijo `passage: `, ventanas de contenido 384, solapamiento 48, inferencia FP16, PyTorch 2.5.1+cu121, Transformers 4.57.6.
- El código conserva corpus y embeddings originales; las matrices privadas no se publican.

## Comparación con embeddings originales truncados

| Métrica | Atlas original | Atlas E5 completo |
|---|---:|---:|
| Mediana de coseno entre tesis diferentes (100.000 pares, seed 42) | 0,840759 | 0,928560 |
| Media de coseno entre tesis diferentes | 0,839951 | 0,928362 |
| Norma del vector medio global | 0,916447 | 0,963530 |

Otros resultados: mediana de coseno para la misma tesis entre versiones = **0,942280**; correlación de rangos Spearman entre las semejanzas de pares = **0,431283**; coincidencia promedio del conjunto de vecinos más próximos, top-10, entre versiones = **33,75 %** (256 tesis ancla).

**Lectura metodológica:** las representaciones han cambiado apreciablemente y el nuevo espacio es considerablemente anisotrópico. El coseno promedio entre vectores unitarios distintos está determinado por la norma de su media:

```text
mean_cosine_off_diagonal = (N * ||mean_vector||^2 - 1) / (N - 1)
```

Esta identidad explica cuantitativamente por qué aparece una similitud promedio elevada cuando los vectores comparten dirección común. La causa exacta puede incluir anisotropía inherente a E5, lenguaje académico repetitivo y/o contenido documental redundante: **las cifras no permiten separar esas causas**.

Un coseno de 1,0 entre documentos distintos puede derivar de redondeo numérico, documentos repetidos o embeddings casi idénticos; investigar posibles pares individualmente **solo en entorno privado** antes de concluir duplicación.

## Siguiente análisis, sin GPU

El script `scripts/reviewer_fulltext_anisotropy.py` calcula (a) espacios originales y (b) los mismos espacios tras restar su vector medio y normalizar de nuevo. Comparará similitudes, estabilidad de los vecinos, correlaciones y distribución de los residuos. **No elimina datos, no cambia los embeddings originales y no determina cuál clasificador es más exacto**.

```bash
cd "$HOME/utn_thesis_atlas_revision"
git pull --ff-only origin main
source "$HOME/.venvs/utn-atlas-audit/bin/activate"

python scripts/reviewer_fulltext_anisotropy.py \
  --project-root "$HOME/utn_thesis_atlas" \
  --pairs 100000 \
  --anchors 256 \
  --k 10 \
  --output docs/audits/reviewer_fulltext_anisotropy.json

cat docs/audits/reviewer_fulltext_anisotropy.json
```

Un descenso de coseno tras el centrado es una transformación geométrica esperable, **no evidencia suficiente de mejor alineación temática**. Para clasificar ODS/PDOT en un espacio centrado se deben transformar coherentemente los vectores de descriptores y calibrar umbrales usando referencias humanas independientes.

## Próximos bloqueos científicos

- Verificar y congelar los textos y fuentes de los 17 descriptores ODS, seis ejes PDOT y diez necesidades locales. Ejecutar entonces TF-IDF y sensibilidad de descriptores; no crear taxonomías inventadas.
- Codificar independientemente la muestra humana de 450 tesis, adjudicar, evaluar por clase, calibrar en las 330 enriquecidas y probar en las 120 aleatorias.
- Completar la revisión manual de 80 límites de secciones antes de eliminar bibliografía o anexos de futuras representaciones.
- Repetir las estadísticas inferenciales y figuras con **la versión final de clasificaciones y embeddings**. Los siete informes del paquete anterior pertenecen al atlas original y sirven como línea base, no sustituyen esos resultados.
- Actualizar el manuscrito y las respuestas a los cuatro revisores con métricas verificadas y limitaciones explícitas.

**Conclusión:** procesamiento integral resuelto; calidad de clasificación y efecto territorial demostrados, NO.
