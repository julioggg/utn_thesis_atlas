# Cierre exploratorio de la comparación TF-IDF vs. E5 — revisión de Sustainability

**Fecha del análisis:** 15 de noviembre de 2026 (ejecución CEDIA comunicada por el investigador; archivos privados conservados en CEDIA).  
**Naturaleza:** resumen científico agregado, **no prueba confirmatoria ni versión del manuscrito**.

## Diseño y procedencia

- Corpus fuente: 7.830 registros. Dos codificadores humanos A/B: 450 casos iguales para todos los modelos, 120 aleatorios y 330 de enriquecimiento deliberado. Nunca tratar 450 agrupados como muestreo aleatorio representativo.
- Baseline: TF-IDF palabra 1–2-gramas, descriptores históricos de ODS y PDOT, texto `analysis_text` histórico; se excluyeron los 120 textos aleatorios del ajuste del vocabulario/IDF.
- Candidatos de contraste: E5 original con ventana limitada y E5 con procesamiento de texto completo más centrado vectorial, usando descriptores históricos reconstruidos por comparación con las salidas originales.
- Comparaciones emparejadas tesis-por-tesis, exact McNemar sin ajuste múltiple e IC bootstrap pareado (95 %, 5.000 repeticiones), **cada evaluador separado**.
- El conjunto aleatorio ya se utilizó para inspeccionar E5 y sus variantes antes de ejecutar el benchmark TF-IDF. **Los resultados son exploratorios retrospectivos, no validación prospectiva independiente de una variante elegida tras medirla**.
- El hecho de que A/B alcanzaran acuerdo ODS 92,22 % (κ=0,913088) y PDOT 95,33 % (κ=0,938504) NO implica que E5 tenga igual exactitud. Las 47 propuestas de adjudicación tienen atribución genérica al comité; la evidencia formal firmada y la política de aceptación para los otros 403 casos aún no han sido comprobadas en el repositorio.

## Exactitud en la muestra aleatoria (N=120)

| Dominio | Evaluador | TF-IDF | E5 original | E5 fulltext centrado | Diferencia E5 centrado − TF-IDF |
|---|---|---:|---:|---:|---:|
| ODS | A | 0,533333 | 0,500000 | 0,616667 | +8,333 pp |
| ODS | B | 0,516667 | 0,533333 | 0,641667 | +12,500 pp |
| PDOT | A | 0,500000 | 0,433333 | 0,541667 | +4,167 pp |
| PDOT | B | 0,491667 | 0,433333 | 0,541667 | +5,000 pp |

## Comparaciones emparejadas: E5 centrado − TF-IDF

| Dominio/referencia | Mejora pp | IC bootstrap pareado 95 %, pp | Gana/ pierde tesis frente a TF-IDF | McNemar exacto p sin corregir |
|---|---:|---:|---:|---:|
| ODS A | +8,333 | [-1,667; 18,333] | 25 / 15 | 0,1538599 |
| ODS B | +12,500 | [2,500; 22,500] | 27 / 12 | 0,0237027 |
| PDOT A | +4,167 | [-5,833; 14,167] | 21 / 16 | 0,5113758 |
| PDOT B | +5,000 | [-4,167; 15,000] | 21 / 15 | 0,4050322 |

**Las ocho comparaciones** (E5 original y fulltext centrado frente a TF-IDF para ambos dominios y evaluadores) constituyen una familia de contrastes exploratorios. El p mínimo comunicado (0,0237027) **no sobrevive** a Bonferroni para ocho contrastes (umbral 0,00625). No afirmar superioridad general ni concluir equivalencia por ausencia de significación.

## E5 original − TF-IDF: contraste emparejado

| Dominio/referencia | Diferencia pp | IC bootstrap 95 %, pp | Ganados/perdidos | McNemar p sin corregir |
|---|---:|---:|---:|---:|
| ODS A | -3,333 | [-14,167; 7,500] | 20 / 24 | 0,6515878 |
| ODS B | +1,667 | [-9,167; 12,500] | 23 / 21 | 0,8803958 |
| PDOT A | -6,667 | [-18,333; 5,000] | 21 / 29 | 0,3222363 |
| PDOT B | -5,833 | [-17,500; 5,833] | 21 / 28 | 0,3916029 |

## Macro F1 (120 tesis, promedio de clases presentes o predichas)

| Dominio/referencia | TF-IDF | E5 fulltext centrado |
|---|---:|---:|
| ODS A | 0,392683 | 0,370100 |
| ODS B | 0,379207 | 0,413300 |
| PDOT A | 0,412382 | 0,437500 |
| PDOT B | 0,403962 | 0,439200 |

**Interpretación:** E5 fulltext centrado presenta una mayor exactitud puntual que TF-IDF en los cuatro contrastes, pero no domina en todas las métricas y las comparaciones no confirman superioridad general. El baseline léxico es competitivo y, en PDOT, supera descriptivamente al E5 histórico. Las métricas por clases, sus soportes y confusiones están solo en ficheros privados de CEDIA.

## Calibración de abstención (análisis también completado)

Sobre 330 tesis dirigidas se probaron umbrales de coseno/margen y se aplicaron a 120 aleatorias, pero **esta prueba es retrospectiva** porque ya se habían analizado modelos sobre esos casos. Para fulltext centrado:

| Dominio/referencia | Cobertura | Accuracy con umbral | Macro-F1 | NONE reales/predichos |
|---|---:|---:|---:|---:|
| ODS A | 1,000 | 0,6167 | 0,3701 | 1/0 |
| ODS B | 0,767 | 0,5833 | 0,4559 | 2/28 |
| PDOT A | 1,000 | 0,5417 | 0,4375 | 0/0 |
| PDOT B | 1,000 | 0,5417 | 0,4392 | 0/0 |

**No adoptar automáticamente el umbral.** El macro-F1 ODS B aumenta, pero con 28 abstenciones ante solo dos verdaderos NONE y caída de exactitud respecto a top-1 sin umbral. En PDOT la muestra aleatoria no contiene NONE humanos, por tanto no estima sensibilidad de esa categoría.

## Evidencia en CEDIA (no incluida en GitHub público)

- `docs/audits/reviewer_four_e5_variant_dual_coder_metrics_v2.json`
- `docs/audits/reviewer_four_e5_paired_random_uncertainty.json`
- `docs/audits/reviewer_four_e5_abstention_calibration_v1.json`
- `docs/audits/reviewer_historical_tfidf_human_metrics_v1.json`
- `docs/audits/reviewer_tfidf_vs_e5_paired_random_v1.json`
- Matrices privadas: `data/revision_private/reviewer_fulltext_reclassification/`, `data/revision_private/reviewer_historical_tfidf_human_metrics_v1/`; CSV por clase en rutas privadas de validación.

Estos archivos de resultados reales **no se añadieron** a GitHub mediante este resumen. Los números de este informe proceden de salidas pegadas por el investigador y requieren comprobar consistencia con los JSON finales antes de copiarlos al manuscrito.

## Trabajos verdaderamente pendientes

1. **Referente humano de 450:** vincular el acta real firmada y responsable(s) al Excel SHA-256 `ab94f261295cdfde523f819ff9dbd92a388b577357a5e6bf6099e752d65f72dd`; documentar aprobación de 47 y aceptación explícita de la regla 403 coincidencias A=B; conservar `CONTROL_TECNICO` antiguo como rastro histórico. No fingir actas o firmas.
2. **Libro PDOT y diez necesidades:** distinguir diccionario usado históricamente de las seis categorías oficiales provinciales de 2024/2026; fuente/fecha/autor; cerrar discusión de ejes combinados; aprobar descriptores y limitaciones.
3. **Validez por clase:** exportar al manuscrito las 17 filas ODS y seis PDOT con support y precision/recall/F1, preferentemente contra consenso firmado, y advertir clases con muestra pequeña.
4. **Método de análisis definitivo:** elegir por justificación metodológica, no por mayor score del test ya examinado; mantener la comparación múltiple y análisis de sensibilidad.
5. **Figuras y datos:** coherencia 7.830, ODS4 histórico 2.649, cinco facultades reales, 1.604 sin facultad, métricas y tablas derivadas exclusivamente del pipeline de referencia elegido; revisar salidas/figuras contra Word final.
6. **Métodos/metadatos:** flujo de colección, OCR y corpus, 80 casos fronteras de sección (2 pendientes), k=75 y silhouette, estadística de tablas pequeñas, efecto de tamaño, limitaciones causales, ética, privacidad, datos/código, contexto ecuatoriano.
7. **R1–R4:** respuesta punto por punto con ubicación real en el manuscrito revisado; no dar por resuelta la revisión solo porque el código se ejecutó.

No subir hojas privadas, handles, textos, anotaciones o actas a GitHub público.
