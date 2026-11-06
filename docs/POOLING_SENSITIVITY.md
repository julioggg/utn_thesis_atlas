# CEDIA: estudio exploratorio de agregación E5

**Estado actual:** las 450 tesis de validación están seleccionadas y sus dos formularios han superado la auditoría de integridad; ambas evaluaciones siguen sin anotaciones. Los archivos privados no deben subirse al repositorio público.

## Objetivo y precaución científica

En el piloto anterior de 12 tesis, la mediana de similitud entre tesis distintas aumentó de 0,844 a 0,931 al sustituir el embedding original truncado por un promedio ponderado de los fragmentos completos. Esto podría reflejar componentes genéricos compartidos, pero **NO demuestra una pérdida de exactitud**, ni demuestra que alguna estrategia alternativa sea superior.

El script study_pooling_sensitivity.py realiza una prueba de sensibilidad **sobre los mismos 12 textos originales**, codificando cada ventana una sola vez y calculando cuatro representaciones:

- all_weighted: promedio de todos los fragmentos normalizados ponderado por tokens nuevos cubiertos.
- middle_80pct: descarta las posiciones extremas 10% + 10% como indicador exploratorio de sensibilidad al inicio/final de tesis.
- first_25pct: usa exclusivamente el primer 25% de ventanas como control de contenido parcial, NO es representación completa.
- equal_three_regions: promedio de tres representaciones normalizadas, correspondientes a inicio, centro y final, con igual peso regional.

El estudio calcula similitud documental, distribución de similitudes entre tesis distintas y preservación del orden de pares respecto del embedding anterior. **Estas métricas diagnostican geometría y estabilidad**, no validez temática ni calidad de clasificación ODS/PDOT.

El programa aborta si la selección de tesis ya no coincide con el experimento de 12 documentos, si falla la alineación entre etapas 04/05/06/07 o si la representación all_weighted deja de reproducir el experimento previo dentro del coseno 0,999. No altera ningún archivo original y exporta solamente resultados agregados.

## Ejecución (una MIG; GPU ya configurada)

    cd "$HOME/utn_thesis_atlas_revision"
    git pull --ff-only origin main
    source "$HOME/.venvs/utn-atlas-audit/bin/activate"

    python scripts/study_pooling_sensitivity.py \
      --project-root "$HOME/utn_thesis_atlas" \
      --documents 12 \
      --batch-size 1 \
      --chunk-tokens 384 \
      --overlap 48 \
      --max-chunks 400 \
      --output docs/audits/pooling_sensitivity_v1.json

Solo si la salida es correcta:

    cat docs/audits/pooling_sensitivity_v1.json
    git add docs/audits/pooling_sensitivity_v1.json
    python scripts/git_safety.py
    git diff --cached --stat
    git commit -m "Compare E5 document pooling sensitivity on 12 theses"
    git push origin main

## Interpretación y siguiente fase

No elegir la estrategia que produzca menor coseno entre documentos sin validación. Separación artificial del espacio semántico no equivale a mejor etiqueta. Cuando las dos personas terminen y se adjudique la muestra de validación, comparar de forma predefinida precisión, recall, F1 macro, cobertura de abstención y errores por clase, particularmente ODS 4 y clases raras. Si es necesario, evaluar limpieza de bibliografías y anexos **antes** de ejecutar un proceso completo de más de 854.000 fragmentos.
