# Recuperación de E5 fulltext tras volver a CEDIA con una sola MIG

## Diagnóstico confirmado

- Se validaron **134 checkpoints privados** del procesamiento anterior: 67 por shard, 16 tesis cada uno, 2.144 tesis recuperables de 7.830.
- La ejecución de `reviewer_full_corpus_two_mig.py` se detuvo **antes de iniciar procesos** porque `nvidia-smi -L` ahora presenta solamente **una** instancia MIG, y el orquestador original exige **dos**.
- No eliminar, mover, renombrar ni reescribir los checkpoints o `run_parameters_PRIVATE.json`. Ambos contienen la huella SHA256 del script original `reviewer_full_corpus_two_mig.py` y de su codificador `pilot_fulltext_embeddings.py`.

### Estrategia

El nuevo archivo `scripts/resume_fulltext_one_mig.py` NO modifica los scripts originales ni el manifiesto congelado. Usa **una GPU MIG**, ejecuta secuencialmente el worker 0 y el worker 1, recupera todos los checkpoints de cada grupo, verifica el censo completo y ensambla `fulltext_e5_large_7830_PRIVATE.npy`.

La ejecución puede interrumpirse y reanudarse bajo el mismo identificador, siempre que los archivos originales permanezcan inmutables. El informe público candidato se crea **únicamente** al completar la reconstrucción íntegra.

### 1. Comprobación sin GPU

```bash
cd "$HOME/utn_thesis_atlas_revision"
git pull --ff-only origin main
source "$HOME/.venvs/utn-atlas-audit/bin/activate"

python scripts/resume_fulltext_one_mig.py \
  --project-root "$HOME/utn_thesis_atlas" \
  --verify-only
```

La salida esperada, si no se han creado checkpoints nuevos, es 1.072 tesis verificadas en cada shard, total 2.144. Si aparecen diferencias SHA256, no intentes regenerar el manifiesto: se debe inspeccionar el cambio.

### 2. Reanudar con la única GPU asignada

Ejecutar solo si `torch.cuda.device_count() == 1` y no hay otra ejecución trabajando sobre esos directorios.

```bash
python scripts/resume_fulltext_one_mig.py \
  --project-root "$HOME/utn_thesis_atlas" \
  --output docs/audits/fulltext_e5_large_full_corpus_v1.json
```

El programa procesará primero las tesis pares pendientes y después las impares pendientes en la misma instancia MIG. Se mantienen los checkpoints privados, los SHA256 del corpus y los scripts, el máximo de 1.500 fragmentos por documento y la versión de modelo precongelada.

Los logs privados se guardan en:
- `data/revision_private/fulltext_e5_large_v1/single_mig_resume_slot0.log`
- `data/revision_private/fulltext_e5_large_v1/single_mig_resume_slot1.log`

Para seguir el progreso de manera no intrusiva desde otra consola:

```bash
for d in 0 1; do
  printf 'Shard %s: ' "$d"
  find "data/revision_private/fulltext_e5_large_v1/mig_slot$d" \
    -maxdepth 1 -name 'batch_*.npz' | wc -l
done
```

**No ejecutar dos instancias del recuperador sobre la misma carpeta.** Si CEDIA permite recuperar **dos MIG**, también puedes usar el orquestador original sin cambios; no intercalar ambas estrategias mientras una esté activa.

### 3. Resultados y criterios de éxito

Para publicar un candidato de informe agregado, el programa exige:
- 7.830 filas sin duplicados en el orden original;
- 286.050.084 tokens de contenido y 854.145 ventanas;
- vectores normalizados y matriz privada `7.830 × 1.024`;
- mismo modelo E5-large y revisión exacta; descriptores y clasificación NO se recalculan;
- coincidencia de SHA256 del corpus y del código con el manifiesto congelado.

Después de verificar manualmente el informe, publicar **únicamente** el JSON `docs/audits/fulltext_e5_large_full_corpus_v1.json`. No subir la matriz, checkpoints, logs ni texto privado.

### 4. Dependencias científicas restantes

La creación de un embedding para cada tesis no aporta precisión/F1 automáticamente. Siguen pendientes la verificación de los descriptores SDG/PDOT/necesidades, la clasificación, la evaluación con dos expertos sobre 450 tesis, y la decisión de recorte basada en 80 revisiones estructurales.
