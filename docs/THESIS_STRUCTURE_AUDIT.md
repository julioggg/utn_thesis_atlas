# Auditoría estructural del texto completo: etapas de tesis, no eliminación automática

## Contexto

El piloto de las 12 tesis reprodujo el embedding completo ponderado (coseno de reproducción = 1,000). Al comparar cuatro estrategias de agregación, la similitud mediana entre tesis diferentes quedó alta para todos los métodos: 0,931 para promedio completo, 0,926 para la aproximación del 80 % central, 0,918 para el primer 25 % y 0,931 para tres regiones equilibradas. Esas métricas describen la geometría de los vectores; NO prueban precisión de las etiquetas ODS o PDOT.

El siguiente paso razonable es auditar **qué partes de los textos completos** se incorporan. Los PDF pueden contener portadas, tablas de contenidos, bibliografía y anexos que añaden referencias temáticas sin describir directamente las contribuciones de cada tesis.

## Herramienta propuesta

El script `scripts/audit_thesis_structure.py` recorre en CPU los textos `full_text` de `04_clean_corpus.parquet`, sin modificar el corpus. Busca encabezados independientes de:

- Resumen / abstract
- Introducción / introduction
- Metodología / methods
- Resultados / results
- Conclusiones / conclusions
- Bibliografía / referencias / bibliography / references
- Anexos / appendices

Se contabilizan únicamente *candidatos* de encabezados. En particular, un encabezado de bibliografía cuenta como candidato tardío solo cuando aparece después del 55 % del texto extraído. Las coincidencias tempranas, como las de un índice de contenidos, se distinguen. El análisis NO decide que las secciones halladas sean correctas y NO borra texto.

El informe `docs/audits/thesis_structure_census.json` incluye **solo cantidades agregadas y distribuciones de posiciones**; no contiene tesis, fragmentos, nombres, títulos ni identificadores.

## Comandos en CEDIA (solo CPU)

```bash
cd "$HOME/utn_thesis_atlas_revision"
git pull --ff-only origin main
source "$HOME/.venvs/utn-atlas-audit/bin/activate"

python scripts/audit_thesis_structure.py \
  --project-root "$HOME/utn_thesis_atlas" \
  --late-fraction 0.55 \
  --output docs/audits/thesis_structure_census.json

cat docs/audits/thesis_structure_census.json
```

**Solo después de revisar la salida** y confirmar que el informe es agregativo:

```bash
git add docs/audits/thesis_structure_census.json
python scripts/git_safety.py
git diff --cached --stat
git commit -m "Audit thesis section structure and late bibliography candidates"
git push origin main
```

## Limitaciones y decisiones posteriores

Un encabezado detectado no demuestra que todo el contenido posterior sea bibliografía, y un PDF sin coincidencias no necesariamente carece de secciones. No se debe eliminar automáticamente una parte de ninguna tesis sobre la base de esta heurística.

Si hay suficientes encabezados tardíos detectables, evaluar **manualmente, en CEDIA**, una muestra de límites de sección antes de preparar métodos `content-only`, `abstract+objectives+results`, y `fulltext`. Cada método debe conservar evidencia de cobertura, trazabilidad e información perdida.

La muestra humana de 450 tesis ya está congelada pero sigue sin anotaciones. La selección del método final depende de una evaluación contra etiquetas humanas independientes; una métrica geométrica no es una métrica de validez ODS/PDOT.
