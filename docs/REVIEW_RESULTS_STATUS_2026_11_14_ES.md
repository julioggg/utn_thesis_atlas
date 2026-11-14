# Estado empírico de la revisión mayor — 14 noviembre de 2026

## Fuentes reproducibles

- `docs/audits/fulltext_e5_large_full_corpus_v1.json` y `fulltext_vs_legacy_7830_comparison.json`, commit `14d303b`.
- `docs/audits/reviewer_stage1_statistics.json`, `reviewer_stage2_geometry_trends.json`, `reviewer_stage3_stability.json`, `reviewer_figure_reconciliation.json`, `reviewer_alternate_encoder_pilot.json`, `descriptor_source_inventory.json`, `descriptor_template_status.json`, `reviewer_suite_run_status.json`, commit `1b013ba`.
- Anisotropía ejecutada y revisada localmente: `docs/audits/reviewer_fulltext_anisotropy.json`, pendiente de commit público al momento de redactar esta nota.

## Hallazgos directamente sustentados

1. **Embeddings completos:** 7.830 textos, 286.050.084 tokens, 854.145 ventanas, 490 checkpoints, 1024D, E5-large versión congelada. Los vectores originales y nuevos tienen norma 1, sin discrepancias de alineación.
2. **Geometría:** entre 100.000 pares de tesis distintas, coseno mediano original 0,840759; fulltext 0,928560. Coseno mediano de la misma tesis en ambas versiones 0,942280. Rangos Spearman entre pares 0,431283; vecindario top-10 coincide 33,75 % (256 documentos ancla). Norma del vector medio: 0,916447 original y 0,963530 fulltext.
3. **Anisotropía:** tras media-centra y normalización, coseno mediano entre tesis distintas pasa a -0,011834 en original y -0,035800 en fulltext. Rango Spearman *entre espacios centrados* 0,676802 y coincidencia top-10 entre versiones 37,4219 %. Estas mejoras son geométricas, **no validación semántica ni F1**.
4. **Facultades:** de 7.830 registros, 6.038 poseen originalmente una de cinco facultades reales; se imputaron otras 188 mediante una regla conservadora por carrera y quedan 1.604 sin facultad confiable. La asociación con etiquetas ODS *predichas por el modelo legacy* (N=6.226) dio χ²=11.747,9187, V de Cramér=0,686825, p_perm=0,002 (499 permutaciones). 17 de 85 celdas esperadas quedan por debajo de cinco y dos por debajo de uno. El p de permutaciones se encuentra en su resolución mínima `1/(499+1)`; no llamarlo un p «exacto».
5. **ODS 4:** 2.649 asignaciones originales en 7.830 tesis; de ellas, 1.901 corresponden a registros de cinco facultades verificadas o imputadas. Facultad Educación registra 1.394/1.588 asignaciones a ODS 4. Fuera de Educación, las etiquetas ODS 4 NO constituyen por sí solas falsos positivos demostrados.
6. **Incertidumbre de top1:** 5.357/7.830 (68,42 %) tienen diferencia ODS top1-top2 inferior a 0,01; para PDOT, 6.197/7.830 (79,14 %). Esos márgenes NO son probabilidades. Un umbral ilustrativo 0,80 unido a margen 0,01 dejaría 2.193/7.830 clasificaciones ODS y 1.145/7.830 PDOT; no adoptar tales umbrales sin calibración experta.
7. **Diversidad ODS rarefactada:** entropía Shannon normalizada (300 tesis por grupo, 300 réplicas Monte Carlo): Administración 0,759917, Agro-Ambiente 0,682100, Ingeniería Aplicada 0,530449, Salud 0,230785, Educación 0,214267. Estos son resultados del atlas legacy, no del clasificador revisado.
8. **Atipicidad semántica:** Kruskal–Wallis H=317,0607, ε²=0,050323; p_perm=0,004 con 249 permutaciones. La variable es distancia coseno al centroide de la facultad, **no originalidad científica**.
9. **k-NN e interdisciplinariedad:** mezcla de vecinos de otra facultad con muestreo balanceado de 400 por facultad: 6,03 % para k=5; 9,05 % para k=15; 12,09 % para k=30. Aleatorio balanceado esperado ≈80,04 %, sin que esto permita inferir colaboración real. Se detectaron seis IDs de temas puente candidatos entre facultades; sus nombres y documentos requieren revisión humana.
10. **Estabilidad de temas:** MiniBatchKMeans exploratorio sobre N=1.500 vectores legacy y semillas 42,123,456, ARI medio k=50: 0,463515; k=75: 0,411604; k=100: 0,412566. No reproduce el algoritmo original de 75 temas ni prueba que k=50 sea la solución final.
11. **UMAP:** trustworthiness 0,940379/0,943039 entre semillas y recall de vecindario 2D ≈0,695022. No usar áreas de polígonos UMAP como medida de interdisciplinariedad.
12. **Tendencias:** períodos de análisis 2021–2022 y 2024–2025 excluyen 2026 por incompleto. Los IDs de temas con crecimiento relativo son solo candidatos; no llamarles «emergentes» sin estabilidad temática y caracterización científica.
13. **Segundo modelo:** E5-large vs E5-base, mismos 36 textos y 3708 ventanas por modelo; correlación entre geometrías 0,964316 y solapamiento top-10 de 0,883333. No es validación de etiquetas.
14. **Figuras y asesores:** reconstrucción desde 07 confirma 2.649 ODS 4 (no 2.668); 7.541 registros con asesor no vacío y 1.091 valores distintos sin normalizar. Figura 5 tiene ahora fuente diferenciada en la carpeta privada; debe ser reemplazada en el manuscrito final.

## Pendientes que siguen siendo bloqueos sustantivos

- **No hay** evaluación humana completada en la muestra congelada de 450 tesis; faltan dos evaluadores, adjudicación, kappa, F1 y métricas por categoría.
- **No están verificados** los textos originales de 17 descriptores ODS, 6 ejes PDOT y diez necesidades, ni versión/source del PDOT. En CEDIA la auditoría AST encontró cuatro objetos literales candidatos en tres archivos; revisar el JSON **privado**, no inventar descriptores.
- TF-IDF y sensibilidad/paráfrasis de descriptores están bloqueados hasta verificar el manifiesto. La matriz fulltext final no tiene aún nuevas predicciones temáticas.
- La muestra estructural de 80 tesis sigue sin inspección manual; no recortar automáticamente las bibliografías/anexos.
- La base de resultados de estadística, centroides, KMeans y figuras sigue siendo el **atlas original** con input truncado, no la clasificación definitiva. Se debe ejecutar sensibilidad sobre fulltext y reconstrucción final después de fijar categorías y umbrales.
- Falta reescritura del artículo, ética/permiso institucional, referencias, contexto regulatorio ecuatoriano y una respuesta editorial individual y verificable para los cuatro revisores.

## Experimento computacional adicional para resolver incertidumbres de facultad

`scripts/reviewer_fulltext_faculty_sensitivity.py` contrasta cuatro matrices (original/fulltext, sin centrar/centradas) en dos selecciones: (1) 6.038 filas originalmente etiquetadas en las cinco facultades y (2) 6.226 filas al incluir 188 imputaciones conservadoras por carrera. Al calcular mezcla k-NN, distancia entre centroides y distribuciones, mantiene semillas y tamaños de muestra iguales entre las cuatro representaciones dentro de cada selección, publicando únicamente agregados.

```bash
cd "$HOME/utn_thesis_atlas_revision"
git pull --ff-only origin main
source "$HOME/.venvs/utn-atlas-audit/bin/activate"

python scripts/reviewer_fulltext_faculty_sensitivity.py \
  --project-root "$HOME/utn_thesis_atlas" \
  --per-faculty 350 \
  --output docs/audits/reviewer_fulltext_faculty_sensitivity.json

cat docs/audits/reviewer_fulltext_faculty_sensitivity.json
```

Este experimento prueba la **sensibilidad de la geometría por facultad**, no sensibilidad de precisión de asignaciones ODS/PDOT. No reutilizar los antiguos umbrales absolutos en representaciones centradas.

## Interpretación científica importante

La revisión metodológica es mucho más reproducible, pero una gran V de Cramér entre facultades y ODS predichos puede surgir de pistas disciplinares triviales y de los propios textos: **no es una validación independiente de alineación ni impacto**. El efecto de normalizar el espacio E5 debe presentarse como sensibilidad, no como mejora demostrada hasta contrastarlo con etiquetas humanas.
