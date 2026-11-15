# Estandarización Q1–Q4 de soporte común por facultad: análisis de sensibilidad V2

**Situación observada:** La auditoría V1 sobre 7.830 tesis informó tendencias crudas de longitud para ODS 4, el eje PDOT `Asentamientos Humanos Movilidad Energía Conectividad` y la necesidad `Salud nutrición grupos prioritarios`. El contraste estandarizado para los seis grupos de facultad se devolvió como `null` porque Ciencias de la Salud no tuvo suficientes tesis (mínimo n=30) en Q4. Este es un bloqueo de soporte, no una falla computacional.

**Resultados crudos Q4−Q1 disponibles**: ODS 4, −7,958 puntos porcentuales; eje PDOT dominante, +14,234 pp; necesidad Salud/Nutrición, −17,102 pp. El eje PDOT subió +17,758 pp en Educación y +24,334 pp en Administración, pero disminuyó −2,570 pp en Ingeniería Aplicada y −3,648 pp en Agropecuarias; el grupo sin facultad quedó cercano a cero (+0,986 pp). Estos son resultados de etiquetas no validadas por humanos.

## Análisis adicional implementado

`scripts/reviewer_length_faculty_common_support_v2.py` fija el grupo de referencia a las **facultades originales verificadas + desconocidos** que tienen al menos 30 documentos en AMBOS cuartiles extremos de longitud. No cambia ni los cuartiles ni las asignaciones de fuente, ni relaja el mínimo. Excluye totalmente de la estimación de soporte común a los grupos sin suficientes Q1/Q4 y muestra explícitamente cuáles fueron excluidos, qué proporción de los 7.830 casos retiene el subgrupo de referencia y los pesos renormalizados de los grupos incluidos.

El método produce tres conjuntos de diferencias Q4−Q1 para cada dominio:

1. Tasa cruda para todos los documentos.
2. Tasa cruda restringida a las facultades elegibles.
3. Tasa estandarizada con pesos de la población original **condicionados a pertenecer a las facultades elegibles**, con intervalos percentiles 95 % de 1.000 remuestreos independientes dentro de cada celda facultad × cuartil.

Las métricas son proporción asignada a la categoría investigada en el atlas original, proporción asignada en fulltext y fracción de tesis cuyo top-1 cambia. Todo el procesamiento es de CPU; sin relectura PDF ni codificación E5.

**Limitación indispensable:** el estimador restringido NO representa a todas las seis agrupaciones originales; no debe reemplazar el estimador estandarizado para toda la población —que permanece no identificable con el criterio vigente de celdas—. Los intervalos son descriptivos condicionados en las celdas observadas, no una muestra probabilística del corpus ni una inferencia causal de la longitud.

## Ejecutar en CEDIA

```bash
cd "$HOME/utn_thesis_atlas_revision"
git pull --ff-only origin main
source "$HOME/.venvs/utn-atlas-audit/bin/activate"

python scripts/reviewer_length_faculty_common_support_v2.py \
  --project-root "$HOME/utn_thesis_atlas"
```

El reporte agregado se genera en `docs/audits/reviewer_length_faculty_common_support_v2.json`, **no se sube automáticamente** a GitHub. Debe revisarse antes de cualquier `git add` y ejecutarse `python scripts/git_safety.py`.

Un análisis riguroso del artículo exige además evaluar el sesgo de extracción por sección en los 80 casos congelados y completar la doble codificación humana en las 450 tesis; no inferir precisión, impacto ODS o validez PDOT de una tasa o un intervalo geométrico.
