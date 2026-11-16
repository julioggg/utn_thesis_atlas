# Matriz crítica de cierre de revisión mayor — Sustainability (4 revisores)

**Fecha:** 15 noviembre 2026. **Fuente:** comentarios R1 (9 observaciones), R2 (6 mayores + menores), R3 (observaciones metodológicas/política) y R4 (6 apartados) entregados por el autor. **Alcance de auditoría:** GitHub `julioggg/utn_thesis_atlas` + salidas recientes de CEDIA comunicadas en conversación. No se ha contrastado una nueva versión del manuscrito: **código/análisis preparado ≠ manuscrito corregido**.

> **Actualización de avance, 15-11-2026 (posterior a la matriz original):** ya se ejecutaron en CEDIA (a) precisión/recall/F1 del E5 original contra A y B por separado, (b) cuatro representaciones E5 con la misma muestra de 120/330, (c) bootstrap pareado/McNemar, (d) calibración exploratoria de abstención y (e) baseline TF-IDF con comparación pareada TF-IDF/E5. Véanse las tablas detalladas y salvedades en [TFIDF_E5_PAIRED_RESULTS_EDITORIAL_STATUS_2026_11_15_ES.md](TFIDF_E5_PAIRED_RESULTS_EDITORIAL_STATUS_2026_11_15_ES.md). **Estos análisis de validación comparativa están hechos; NO siguen pendientes de ejecución.** Falta constituir documentalmente la referencia consensuada de 450, auditar el PDOT y los diez needs, informar métricas por clase con soporte, reconciliar el pipeline final y corregir el manuscrito. Las filas inferiores de esta matriz son un **corte histórico**, no el estado operativo más reciente. No se añadieron JSON privados de CEDIA al GitHub público.

## Dictamen sobre adjudicación

**NINGÚN revisor exige explícitamente un tercer evaluador ni 450 adjudicaciones.** R1 exige 300–500 tesis, dos codificadores, acuerdo y precisión/recall por ODS/PDOT; R3 propone dos o tres, kappa y F1 por categoría; R4 evaluación experta independiente y métricas. Ya existen A/B 450 completas, acuerdo 92,22% ODS (κ 0,913088) y 95,33% PDOT (κ 0,938504). Desacuerdos en principal 35 ODS, 21 PDOT; unión =47 tesis. Los 201 casos C se seleccionaron porque había diferencias secundarias/incertidumbre/no-match o principales: NO equivalen a una muestra de validación aleatoria ni es legítimo promediar como 450 casos independientes.

Para medir **rendimiento del modelo**, una adjudicación de las 47 tesis principales es recomendada, aunque no es requerimiento literal. Alternativa transparente en plazo urgente: computar precisión/recall/F1 frente a **A y B separadamente**, mostrar dispersión y desacuerdos, sin denominar `gold standard` a una votación ni usar etiquetas de C como verdad por defecto. La distribución por clases raras y el conjunto aleatorio de 120 requieren CIs y declarar n por categoría.

## Tabla de brechas por riesgo editorial

| Prioridad | Requisito de revisores | Evidencia real disponible | Pendiente antes de entregar |
|---|---|---|---|
| CRÍTICA | R1.1, R3, R4: fiabilidad/validez de ODS y PDOT | 450 A/B, kappa alto, 201 revisiones C condicionales | **Precision, recall, F1 por ODS y PDOT; micro/macro; matriz de confusión; no-match; protocolo de referencia; incertidumbre por clases con poca n** |
| CRÍTICA | R1.1 R2.1 R3.2: top1 siempre asignado | Margen/similitud legacy y fulltext calculados; `reviewer_stage1_stats` | Calibrar umbral/no-match con anotación humana o justificar explícitamente cobertura y reportar curva cobertura-rendimiento; evitar afirmar impacto |
| CRÍTICA | R1.4 R2.4 R4.4: tablas, figuras y sumas | Legacy recuenta N=7830, SDG4=2649; Fig5 generada diferenciada pero fuera del manuscrito | Elegir MÉTODO FINAL y regenerar TODAS las tablas/figuras desde una sola clasificación; corregir Fig3 y Fig5 en Word |
| CRÍTICA | R3.3 R3.5: PDOT/local needs provenance | Fuentes PDOT 2023–27/2024 y versión publicada 2026 localizadas; dos diccionarios `PDOT` y `PDOT_MAP` incompatibles | Determinar cuál generó originales, separar seis ejes ANALÍTICOS de los oficiales, documentar diez necesidades, fuente/fecha/autor de descriptores |
| ALTA | R1.2 R4.3: verdadero texto completo E5 | Reprocesados 7830 textos, 854145 ventanas, 286050084 tokens, checkpoint con hash; legacy truncado | Documentar chunk 384/overlap 48/agregación real, contrastar sesgo anexos y escoger método final. Reescribir título/resumen/método si persiste uso legacy |
| ALTA | R3: comparación con otro método | Modelo E5-base piloto 36 tesis solo geometría, sin F1; `reviewer_keyword_baseline.py` existe | **Ejecutar baseline TF-IDF/keyword y evaluar con mismas etiquetas humanas; recuperar/validar manifiesto de descriptores.** |
| ALTA | R1.3 R2.2: sesgo ODS4 | Original 2649, fulltext 1788; cruces por facultad, centering y longitud hechos | Diagnosticar casos extra-Educación con evidencia humana; reportar prevalencia final y sensibilidad. Ninguna reducción de conteo demuestra falsos positivos eliminados |
| ALTA | R1.5–6 R2.5 R3.5 R4.4: estadísticas | Cinco facultades y 188 imputaciones; residuos, V, rarefacción, ε², permutaciones; scripts stage1 hechos para legacy | Recalcular con etiquetas finales, explicar 1604 sin facultad, efectos/posthoc, celdas esperadas, sensibilidad imputación |
| ALTA | R3.1 R4.3: origen de corpus y licencias | Auditorías corpus, extracción y truncamiento; 80 muestras estructurales, 78 revisadas y 2 pendientes | Tabla harvest→exclusiones→7830, criterios de inclusión, OCR/scans, tipos tesis y proyectos; comprobar registros sospechosos de no-tesis |
| ALTA | R3.3 R4.3: ética y protección de datos | Privacidad en `data/revision_private`; se excluye texto privado de GitHub | Statements ética/aprobación o exención verídica, permisos, privacidad de asesores/estudiantes, conflicto de intereses institucional y rol de IA (si aplica) |
| ALTA | R1.9 R3.7: reproducibilidad | GitHub scripts y auditorías; versiones E5 congeladas | Datos/materiales liberables y acceso restringido a tesis, descriptores públicos autorizados, snapshots, `requirements`, DOI/Zenodo si posible, Data Availability |
| MEDIA | R1.7 R3.5: UMAP/convex hull | Centroides 1024D, kNN balanced, seis puentes candidatos, Rao-Stirling; UMAP seeds | Retirar área de convex hull como evidencia; documentar puentes SOLO si se inspeccionan/etiquetan, o retirar su discusión |
| MEDIA | R1.8 R2.6 R3 R4: afirmaciones no medidas | Scripts detectan puentes candidatos y tendencias sin 2026 | Retirar "hidden capabilities", tutor profiles, claims causal de impacto; sustituir "originality" por atipicidad/dispersión |
| MEDIA | R1.8 R4.4: tendencias 2026 | Script excluye 2026 para crecimiento, mínimos por tema | Modificar resultados/figuras y notas en manuscrito, declarar períodos comparables y denominadores |
| MEDIA | R1.9 R3 R4: k=75, silueta | Alternativa exploratoria KMeans k=50/75/100 y semillas disponible | Recuperar selección del pipeline original de 75 temas y valores silhouette (el experimento alternativo NO es réplica); si no se recupera, reformular |
| MEDIA | R1.6 R3.4: cobertura local | Figura 5 alternativa/índice candidato, **fórmula original no verificada** | Definir exactamente y demostrar valor añadido, o eliminar índice de cobertura y presentar cuota + similitud por separado |
| MEDIA | R3: marco nacional; introducción; contribución | Contexto universitario y PDOT en documentos de auditoría | Añadir Ecuador/educación superior/aseguramiento calidad, tesis y tipos trabajos, novedad metodológica, mapa workflow→framework, límites de generalización |
| MEDIA | R1.9 R2 menores R3 R4: referencias/título/figuras | Duplicados 3 y 18 detectados | Nuevo título caso UTN sin 7830, nomenclatura SDG uniforme, geopark, APA/MDPI, DOI 3/18, referencias recientes y latinoamericanas |
| CRÍTICA EDITORIAL | R4: contestación punto por punto | Este tracker y scripts; ninguna versión Word final verificada | Redactar carta individual con cambios reales, secciones y páginas verificadas, materiales suplementarios, anexo de validación. |

## Ruta de entrega sin tercera revisión obligatoria

**Decisión 1:** Fijar conjunto de referencia humano coherente. O bien acta consensuada para los **47 conflictos principales** y ratificación explícita de coincidencias A/B, o evaluación paralela A y B indicando que no hay referencia adjudicada. En ambos casos separar 120 aleatorios de 330 enriquecidos; per-clase reportar soporte y no tratar ausentes como desempeño verificado.

**Decisión 2:** Con la verdad humana acordada, evaluar los cuatro candidatos `legacy_raw`, `legacy_centered`, `fulltext_raw`, `fulltext_centered`, evitando tratar acuerdo histórico como exactitud. Fijar método antes de recalcular tablas.

**Decisión 3:** Recuperar y citar textos/descripciones exactas; completar al menos baseline léxico y umbral/no-match, publicar sensibilidad de SDG 4 y método PDOT analítico con trazabilidad.

**Decisión 4:** Regenerar resultados y figuras SOLO con decisión principal; sustituir afirmaciones sin soporte por limitaciones explícitas.

**Decisión 5:** Documentar criterios corpus/ética/PDOT nacional, versiones, códigos, fuentes, respuesta punto por punto. **Si faltan resultados críticos, no afirmarlos; explicar limitación específica o solicitar ampliación editorial.**

## Advertencias

- **Código experimental ya ejecutado no implica paper corregido**. La última revisión del manuscrito no fue proporcionada para auditoría textual.
- La muestra estructural 80 fue seleccionada de forma balanceada/intencional; sus tasas no son prevalencia poblacional.
- Bajo vocabulario PDOT vigente, el eje combinado `Asentamientos Humanos Movilidad Energía Conectividad` y `Ejes Transversales` no deben presentarse sin prueba documental como los seis componentes oficiales.
- El editor puede decidir que una respuesta que omite F1 por categoría o cualquier baseline no resuelve la crítica central. No disfrazar falta de validación con kappa.
