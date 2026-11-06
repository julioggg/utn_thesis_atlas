# Pipeline experimental de embeddings de las 7.830 tesis — dos particiones MIG

## Advertencia sobre el estado

Este programa **existe y tiene pruebas sintéticas**, pero NO ha sido ejecutado todavía sobre los 7.830 textos. Es un **candidato de representación** de texto completo, NO una clasificación ODS/PDOT validada. Solo el usuario puede lanzar el cálculo en su sesión autorizada de CEDIA.

Entrada: `$HOME/utn_thesis_atlas/data/processed/04_clean_corpus.parquet`.

Salida **privada**: `$HOME/utn_thesis_atlas_revision/data/revision_private/fulltext_e5_large_v1/fulltext_e5_large_7830_PRIVATE.npy` y subdirectorios de checkpoints. NUNCA subirlos a GitHub.

Reporte público candidato **solo si finaliza y se revisa**: `docs/audits/fulltext_e5_large_full_corpus_v1.json`.

## Método fijo

- Modelo: `intfloat/multilingual-e5-large`, versión exacta verificada desde la caché Hugging Face.
- Dos procesos CUDA independientes, uno por MIG 2g.10gb (R535); cada proceso dispone de aproximadamente 9,62 GiB, no 40 GiB.
- Ventanas de 384 tokens de contenido, 48 tokens de solapamiento, prefijo `passage: `, 512 tokens máximo de entrada.
- Media ponderada de embeddings de ventanas normalizadas por el número de tokens nuevos; norma L2 final unitaria.
- Sin eliminación de bibliografías ni anexos no validados.
- Partición por índice par/impar, sin duplicar tesis.
- Checkpoints privados atómicos cada 16 tesis y comprobación rigurosa del manifiesto de parámetros, digest del Parquet, hashes de scripts y revisión exacta del modelo.

El conteo exacto previo es: 7.830 tesis, 286.050.084 tokens de texto completo, **854.145 ventanas**, máximo 1.240 ventanas por tesis. Este pipeline fija `--max-chunks 1500` para no excluir las 42 tesis que superaban el límite exploratorio de 400 ventanas. Si existen textos vacíos, límites excedidos, checkpoint corrupto, matrices no normalizadas, distinta versión de modelo, conteos diferentes o índices duplicados, se **detiene y no declara éxito**.

## Ejecutar únicamente con permiso de cómputo y almacenamiento

En Singularity:

```bash
cd "$HOME/utn_thesis_atlas_revision"
git pull --ff-only origin main
source "$HOME/.venvs/utn-atlas-audit/bin/activate"

python scripts/reviewer_full_corpus_two_mig.py \
  --project-root "$HOME/utn_thesis_atlas" \
  --run-id fulltext_e5_large_v1 \
  --chunk-tokens 384 \
  --overlap 48 \
  --batch-size 1 \
  --max-chunks 1500 \
  --checkpoint-docs 16 \
  --output docs/audits/fulltext_e5_large_full_corpus_v1.json
```

**No ejecutar una segunda copia de este proceso en paralelo** sobre el mismo directorio de checkpoints. Si se interrumpe antes de generar la matriz final, relanzar exactamente el mismo comando desde el mismo commit de los scripts. Se revalidarán los bloques completos y se recalcularán únicamente los que faltan. Si falla, examinar localmente `data/revision_private/fulltext_e5_large_v1/mig_slot0.log` y `mig_slot1.log`.

No eliminar checkpoints ni archivos `.pending` sin inspeccionar el estado del trabajo. Si ya existe la matriz final, el programa se niega a sobrescribirla. En caso de fallo de integridad, se requiere intervención del investigador.

## Comprobación final de resultados

Solo después de terminar correctamente:

```bash
cat docs/audits/fulltext_e5_large_full_corpus_v1.json
git add docs/audits/fulltext_e5_large_full_corpus_v1.json
python scripts/git_safety.py
git diff --cached --stat
git commit -m "Document 7830-thesis verified fulltext E5 candidate embeddings"
git push origin main
```

No subir los vectores `.npy`, checkpoints `.npz`, muestras privadas, logs ni las tesis. El dato de hash de código y corpus publicado no contiene contenido de tesis; revisarlo antes de publicar.

## Interpretación

La nueva matriz preserva los 7.830 índices y habilita análisis reproducibles que antes estaban limitados por truncamiento. **No demuestra que las nuevas etiquetas ODS sean más correctas**, ni que haya impacto en los objetivos de desarrollo sostenible. La clasificación definitiva requiere descriptores originales versionados, comparación con E5-base/TF-IDF, calibración de abstención sobre anotaciones independientes y la reconstrucción completa de tablas y figuras. La decisión sobre quitar bibliografías o anexos debe esperar las 80 revisiones estructurales.

El manuscrito debe describir las limitaciones del experimento original, distinguir la reestimación de los resultados y documentar versiones de software y hardware.
