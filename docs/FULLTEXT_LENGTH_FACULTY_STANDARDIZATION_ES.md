# Diagnóstico ajustado por facultad de la deriva semántica E5-fulltext

**Fecha:** 14 de noviembre de 2026. **Estado:** método de sensibilidad preparado y probado con datos sintéticos; resultados de CEDIA aún pendientes.

## Hallazgos que justifican el contraste

Se procesaron las mismas 7.830 tesis con descriptores históricos verificables, sin recalcular E5. La transición de embeddings truncados a texto completo arrojó:

| Dominio | Tesis que cambian top-1 | Cambio |
|---|---:|---:|
| ODS | 2.536 | 32,39 % |
| PDOT (taxonomía analítica) | 2.865 | 36,59 % |
| Necesidades | 2.343 | 29,92 % |

El texto completo disminuyó el predominio de ODS 4 de 2.649 a 1.788. La entropía normalizada ODS aumentó de 0,741194 a 0,793048. En cambio, el eje PDOT `Asentamientos Humanos Movilidad Energía Conectividad` subió de 2.847 a 4.829 y la entropía PDOT cayó de 0,804723 a 0,597346.

La longitud del documento se asoció con el cambio de etiqueta ODS: Q1 27,94 %; Q2 27,89 %; Q3 34,24 %; Q4 39,50 %. Para PDOT, el cambio fue casi uniforme: 37,74 %; 35,90 %; 36,48 %; 36,23 %. No obstante, la proporción de tesis asignada al eje dominante PDOT ascendió del 55,57 % en Q1 al 69,80 % en Q4.

**Estas asociaciones no identifican el mecanismo causal:** la longitud puede estar vinculada a la composición por facultad/carrera, período académico y al formato institucional, aparte del contenido real de las tesis.

## Auditoría por grupos originales sin imputación

`scripts/reviewer_length_faculty_standardization.py` usa exclusivamente cinco nombres de facultades originalmente consignados y un sexto grupo explícito para metadatos faltantes/misceláneos (1.792 casos). No emplea la asignación heurística de 188 tesis a facultad. Regenera los cuatro cuartiles por número real de tokens de checkpoints frozen y calcula, para cada dominio:

- Proporción original y fulltext de la categoría investigada por cuartil.
- Proporción de tesis con top-1 cambiado por cuartil.
- Tendencias Q4−Q1 dentro de cada facultad y del grupo desconocido.
- **Estandarización directa** de las proporciones de cada cuartil, usando los mismos pesos de composición por facultad del corpus total (los seis grupos).
- Celdas con menos de 30 documentos se suprimen. La estimación estandarizada se deja sin calcular cuando faltan celdas suficientes.
- Los resultados son únicamente **agregados**; no hay identificadores de tesis, títulos, puntajes individuales, vectores ni texto completo en el JSON.

Categorías preespecificadas para el contraste: ODS 4; PDOT Asentamientos–Movilidad; necesidad Salud–Nutrición.

### Ejecución CPU

```bash
cd "$HOME/utn_thesis_atlas_revision"
git pull --ff-only origin main
source "$HOME/.venvs/utn-atlas-audit/bin/activate"

python scripts/reviewer_length_faculty_standardization.py \
  --project-root "$HOME/utn_thesis_atlas" \
  --output docs/audits/reviewer_fulltext_length_faculty_standardization.json
```

### Lectura reducida

```bash
python - <<'PY'
import json
from pathlib import Path
d=json.loads(Path("docs/audits/reviewer_fulltext_length_faculty_standardization.json").read_text(encoding="utf-8"))
print("Estado:",d["status"])
for domain,item in d["taxonomies"].items():
    print("\n", domain.upper(),item["target_label"])
    for mode,v in item["endpoint_q4_minus_q1"].items():
        print(mode,":",v)
    for fac in item["by_original_verified_faculty_or_unknown"]:
        print(fac["faculty_group"],"Q1:",fac["q1_fulltext_target_label_share"],
              "Q4:",fac["q4_fulltext_target_label_share"],
              "Δpp:",fac["q4_minus_q1_target_share_percentage_points"])
PY
```

La conclusión a contrastar es si el gradiente de predominio PDOT por longitud persiste al fijar la distribución facultativa. Incluso si persiste, es una asociación residual, no evidencia de anexos o bibliografías como causa. Es necesario comparar límites estructurales de secciones (80 documentos congelados) y clasificaciones humanas (dos evaluadores, 450 casos, muestras 330 calibración/120 prueba aleatoria) antes de adoptar una representación definitiva.

## Regla de interpretación editorial

- **Provisional:** fulltext raw como comparador principal porque conserva el algoritmo histórico y aísla el efecto de introducir más texto.
- **No demostrado:** que fulltext raw, centered o cualquier ajuste obtenga mayor precisión ODS/PDOT.
- **No demostrado:** que la redistribución de ODS 4 elimine falsos positivos.
- **No demostrado:** que la concentración de PDOT se deba a sesgo o esté justificada territorialmente.
- **Prohibido:** inferir impacto de políticas a partir de afinidades coseno.
