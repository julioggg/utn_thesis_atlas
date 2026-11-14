# Reproducción empírica del clasificador histórico de ODS/PDOT/necesidades

## Evidencia del código original

La revisión de `utn_atlas_pipeline.py` en CEDIA mostró:

```python
def align_tax(df, emb, tax, prefix):
    model = load_model()
    names = list(tax)
    desc = ["passage: " + n + ". " + tax[n] for n in names]
    t_emb = model.encode(desc, batch_size=16, normalize_embeddings=True,
                         convert_to_numpy=True, show_progress_bar=False)
    sims = emb @ t_emb.T
    order = np.argsort(-sims, axis=1)
    ...
```

El código principal llama a `align_tax(df, emb, PDOT, "pdot")` en línea 481, `ODS` en 482 y `NEEDS` en 483; guarda `07_alignment_pdot_ods_needs.parquet` en línea 484. La entrada de tesis es `05_embeddings.npy`, que corresponde al antiguo método limitado a 512 tokens.

`utn_atlas_q1_extras.py` solo aplica `df["pdot_top"].map(PDOT_MAP)` en línea 162 para una transformación posterior de etiquetas; `PDOT_MAP` no interviene en la etapa `step_alignment()`.

**Implicación:** el diccionario correcto para reproducir las clasificaciones históricas es `PDOT` de `utn_atlas_pipeline.py`. Esta evidencia de linaje no verifica que sea una transcripción exacta del PDOT oficial.

## Prueba empírica antes de recomputar 7.830 predicciones

`scripts/reviewer_legacy_alignment_replay.py` carga exclusivamente los diccionarios congelados `PDOT/ODS/NEEDS` del original (comprobando el SHA256), genera las 33 secuencias `passage: <clave>. <valor>` y calcula embeddings del modelo E5-large desde la revisión congelada usada para el fulltext. Reproduce la similitud y compara **etiquetas top-1, top-2, top-3 y sus puntuaciones** con los campos originales de `07`.

Distingue explícitamente las implementaciones: el atlas histórico invocaba `SentenceTransformer.model.encode`, mientras la prueba utiliza `AutoModel` con agrupamiento promedio ponderado por máscara de atención. La coincidencia no se presupone: debe **medirse** antes de afirmar fidelidad al clasificador.

```bash
cd "$HOME/utn_thesis_atlas_revision"
git pull --ff-only origin main
source "$HOME/.venvs/utn-atlas-audit/bin/activate"

python scripts/reviewer_legacy_alignment_replay.py \
  --project-root "$HOME/utn_thesis_atlas" \
  --device auto \
  --batch-size 8 \
  --output docs/audits/reviewer_legacy_alignment_replay.json

cat docs/audits/reviewer_legacy_alignment_replay.json
```

- Lee únicamente los checkpoints de corpus ya producidos y las asignaciones históricas.
- Codifica **33 descripciones**; NO vuelve a codificar los 7.830 documentos.
- Necesita el modelo E5-large congelado en caché de CEDIA. Si falla la carga offline, inspeccionar la caché y la configuración original `load_model()`; no descargar una revisión alternativa ni eliminar los checkpoints.
- Guarda embeddings de descriptores y puntuaciones reconstruidas **solo en** `data/revision_private/reviewer_alignment_replay/historical_replay_descriptor_vectors_and_scores_PRIVATE.npz`.
- El JSON público es un **candidato de informe agregado**, que debe inspeccionarse antes de `git add` / `git push`.

## Interpretación de salida

La evidencia clave es la **concordancia por rango** y la distribución de error absoluto de puntuación original. Si la reproducción con `AutoModel` difiere, investigar la versión exacta de `load_model()`, `SentenceTransformer`, precisión y pooling. No ajustar los resultados históricos artificialmente, ni seleccionar versiones por mejorar un resultado.

Una reproducción del pasado no equivale a validación externa de las etiquetas. La procedencia oficial de la taxonomía PDOT y de las diez necesidades territoriales sigue pendiente.

Después, con la reproducción confirmada, se debe aplicar el conjunto exacto de descriptores a la nueva matriz privada fulltext de 7.830 × 1.024, comparar categorías, márgenes, incertidumbre y centrado geométrico y más tarde evaluar against human gold labels. No adoptar umbrales sin etiquetado independiente.
