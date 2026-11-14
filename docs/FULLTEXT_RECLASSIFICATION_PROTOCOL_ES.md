# Reclasificación de 7.830 tesis con los 33 descriptores históricos

## Requisito científico previo: reproducción de la etapa 07

La reconstrucción `scripts/reviewer_legacy_alignment_replay.py`, ejecutada en CEDIA, reprodujo las asignaciones archivadas de 7.830 tesis:

- ODS (17 categorías): **100 %** de coincidencia top-1, top-2 y top-3.
- PDOT (6 ejes): **100 %** de coincidencia top-1, top-2 y top-3.
- Necesidades territoriales (10 categorías): top-1 **7.829/7.830**, top-2 **7.828/7.830**, top-3 **7.829/7.830**, con coincidencia del conjunto top-3 de **7.830/7.830**.
- Error absoluto de puntuaciones en percentil 99: **2,4 × 10⁻⁷** para las tres taxonomías.

La reconstrucción reproduce la **operación histórica**, no valida la verdad de las asignaciones. La discrepancia minoritaria de NECESIDADES debe examinarse por su margen de similitud antes de atribuirla a empates numéricos.

La implementación original observada en `utn_atlas_pipeline.py` era `desc=["passage: "+name+". "+text]` y `score=embedding@descriptor.T`. Los diccionarios usados eran `PDOT`, `ODS`, `NEEDS`. `PDOT_MAP` en `utn_atlas_q1_extras.py` es un mapa descendente de etiquetas, no una entrada de la etapa de clasificación.

## Nuevo experimento: solo CPU, sin modelo y sin relectura de PDF

`scripts/reviewer_fulltext_reclassification.py` exige:

1. El informe de replay y los **33 vectores de descriptores** guardados privadamente.
2. La matriz E5 original de 7.830 × 1.024 y la matriz fulltext confirmada.
3. Coincidencia de SHA256 del código original del clasificador y del inventario.
4. Verificación de 7.830 filas y correspondencia del modelo E5-large congelado.
5. Concordancia top-3 y mínima discrepancia de puntuaciones en el replay original.

Analiza cuatro variantes:
- Original raw.
- Original centrada.
- Texto completo raw.
- Texto completo centrada.

Para cada variante y dominio genera conteos top-1, porcentaje de cambio frente a clasificaciones históricas, comparación de conjuntos top-3, distribución de márgenes top1-top2 y estadísticas de similitudes. El centrado resta la dirección media de los documentos, con adaptación consistente de los vectores de descriptores y renormalización. **No adopta umbrales como calibrados**.

### Ejecutar

```bash
cd "$HOME/utn_thesis_atlas_revision"
git pull --ff-only origin main
source "$HOME/.venvs/utn-atlas-audit/bin/activate"

python scripts/reviewer_fulltext_reclassification.py \
  --project-root "$HOME/utn_thesis_atlas" \
  --output docs/audits/reviewer_fulltext_reclassification_v1.json
```

### Leer únicamente el resumen

```bash
python - <<'PY'
import json
from pathlib import Path

p = Path("docs/audits/reviewer_fulltext_reclassification_v1.json")
d = json.loads(p.read_text(encoding="utf-8"))
print("Estado:", d["status"])
for name, dom in d["domains"].items():
    print("\n", name.upper())
    print("Discrepancias del replay:", dom["numerical_rank_discrepancy_audit"])
    for variant in d["variants"]:
        r = dom["representations"][variant]
        print(
            variant,
            "coincidencia top1 histórica:",
            r["top1_agreement_with_original_forced_assignment_not_accuracy"],
            "margen mediano:", r["top1_minus_top2_margin"]["median"],
            "ambiguas gap<=.01:", r["uncalibrated_margin_le_counts"]["0.010"],
        )
    print("Cambio raw/centrado fulltext:",
          dom["fulltext_raw_vs_fulltext_centered_top1_changed_n"])
PY
```

Archivos privados de resultados por tesis, excluidos de GitHub:
`data/revision_private/reviewer_fulltext_reclassification/reclassification_all_7830_PRIVATE.npz`

**No publicar** ningún `.npy`, `.npz`, vectores individuales, identificadores de tesis o archivos privados. Inspeccionar el JSON agregado y ejecutar `python scripts/git_safety.py` antes de considerar su publicación pública.

## Interpretación y etapas todavía faltantes

La concordancia con las etiquetas históricas **no es accuracy ni F1**. Una nueva distribución de etiquetas ODS/PDOT puede reflejar tanto información adicional del texto completo como anisotropía y sensibilidad a descriptores. Comparar con dos expertos sobre las 450 tesis preparadas y reportar precision/recall/F1 por clase sobre la muestra pertinente; calibrar umbrales y abstención antes de fijar la tabla final. Los 17 ODS, seis PDOT y diez necesidades deben estar documentalmente trazados; la taxonomía analítica PDOT del pipeline no equivale automáticamente a los seis sistemas oficiales del instrumento provincial.
