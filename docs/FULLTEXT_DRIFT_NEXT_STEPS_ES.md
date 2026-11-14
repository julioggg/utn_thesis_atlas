# Diagnóstico de deriva semántica y concentración de clases — revisión Sustainability

**Entrada confirmada (14 noviembre 2026):** 7.830 tesis, clasificaciones E5-original y E5-fulltext con descriptores de `utn_atlas_pipeline.py`. La reconstrucción histórica fue casi exacta y el recálculo se hizo con las mismas 33 descripciones originales.

## Hallazgos de la reclasificación (no validados por expertos)

| Dominio | Cambios top-1 entre legacy y fulltext raw | Porcentaje |
|---|---:|---:|
| 17 ODS | 2.536 / 7.830 | 32,39 % |
| Seis ejes PDOT analíticos | 2.865 / 7.830 | 36,59 % |
| Diez necesidades locales | 2.343 / 7.830 | 29,92 % |

Cambios **netos de prevalencia**, no flujos pareados de tesis individuales: ODS 4 de 2.649 a 1.788 (-861); ODS 12 de 729 a 1.310 (+581); ODS 9 de 1.387 a 963 (-424); ODS 3 de 1.054 a 1.390 (+336); eje PDOT combinado Asentamientos–Movilidad de 2.847 a 4.829 (+1.982); ejes transversales de 1.494 a 483 (-1.011).

**Advertencia:** un descenso neto de ODS 4 no implica corrección demostrada de falsos positivos. La concentración PDOT en 4.829/7.830 (61,7 %) sugiere una hipótesis de dominancia de descriptor que debe contrastarse antes de fijar el método.

## Comparación con la muestra humana ya congelada

| Estrato | N | Cambios ODS | Cambios PDOT | Cambios necesidades |
|---|---:|---:|---:|---:|
| Muestra aleatoria simple | 120 | 42 (35,0 %) | 45 (37,5 %) | 41 (34,2 %) |
| Enriquecimiento dirigido | 330 | 158 (47,9 %) | 130 (39,4 %) | 108 (32,7 %) |

No reemplazar ni reestratificar estas 450 tesis en función de nuevas predicciones. Las hojas ciegas de los dos expertos siguen siendo la misma selección; no incorporar asignaciones nuevas en las hojas. Los 120 casos aleatorios estiman el rendimiento poblacional con incertidumbre, especialmente para ODS poco representados. Los 330 casos enriquecidos sirven para calibración y evaluación por clase, sin agregarlos ingenuamente como si fueran representativos.

## Nuevo diagnóstico de clasificación, transición y longitud

Ejecutar `scripts/reviewer_fulltext_drift_diagnostic.py` **solo con CPU**. Comprueba las 490 fuentes privadas de checkpoints y sus 286.050.084 tokens y 854.145 ventanas, con fingerprint congelado. Mide:

- Dirección de los flujos top-1 entre etiquetas, reportando por separado solo transiciones de 25 o más tesis. Las demás quedan agregadas.
- Concentración Herfindahl, entropía Shannon normalizada, número efectivo de categorías, Jensen–Shannon entre proporciones históricas y fulltext.
- Margen top-1/top-2 de la clase predominante del espacio fulltext.
- Cambios por cuartiles de longitud del texto completo original, conservando el mismo número de documentos por cuartil.

```bash
cd "$HOME/utn_thesis_atlas_revision"
git pull --ff-only origin main
source "$HOME/.venvs/utn-atlas-audit/bin/activate"

python scripts/reviewer_fulltext_drift_diagnostic.py \
  --project-root "$HOME/utn_thesis_atlas" \
  --output docs/audits/reviewer_fulltext_drift_diagnostic.json

python - <<'PY'
import json
from pathlib import Path
p=Path("docs/audits/reviewer_fulltext_drift_diagnostic.json")
d=json.loads(p.read_text(encoding="utf-8"))
print("Estado:",d["status"])
for domain, res in d["taxonomies"].items():
    print("\n",domain.upper())
    print("Concentración histórica:",res["historical_concentration"])
    print("Concentración fulltext:",res["representations"]["fulltext_raw"]["concentration"])
    print("Principales transiciones:",res["top_aggregate_transitions"]["top_changed_label_flows"][:8])
    print("Por cuartiles de longitud:")
    for x in res["by_original_document_token_quartile"]:
        print(x["length_group"],"tokens medianos",x["content_tokens_median"],
              "cambio",x["historical_to_fulltext_raw_changed_share"],
              "proporción clase dominante",x["fulltext_raw_dominant_category_share"])
PY
```

Los resultados publicados son **únicamente agregados** y no se reutiliza la GPU ni se leen PDF. Los documentos fuente, scores individuales y matrices se conservan en CEDIA.

## Condiciones para elegir la representación final

El fulltext **sin centrar** es el comparador principal provisional porque conserva la operación coseno/descriptor del original y aísla el efecto de incluir más texto. El fulltext centrado es una sensibilidad distinta; márgenes mayores no demuestran calidad superior por sí solos.

Se necesitan: (1) auditoría humana real de fronteras de sección en los 80 casos congelados; (2) dos evaluadores independientes para 450 tesis, adjudicación y Cohen kappa; (3) calibración en 330 y evaluación final en 120, idealmente con CIs y análisis por clase; (4) separar taxonomía analítica PDOT del instrumento territorial oficial y documentar las diez necesidades. Sin esos pasos, la redistribución de categorías no constituye validación de impacto ODS o PDOT.
