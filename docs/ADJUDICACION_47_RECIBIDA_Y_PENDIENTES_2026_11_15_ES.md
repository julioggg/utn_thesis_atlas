# Auditoría del Excel de 47 conflictos principales ODS/PDOT y ruta de cierre

**Fecha de recepción:** 15 de noviembre de 2026.

## Qué se recibió realmente

Se revisó directamente el archivo `Adjudicacion_47_Tesis_ODS_PDOT_COMPLETA.xlsx` que el investigador adjuntó a la conversación. Su huella SHA-256 es:

`30e5044b6ea9cf3a9c17b4daff682367ffc8136698a20fadfe0737b7e1730ca5`

El archivo tiene 9 hojas y contiene 47 registros únicos. La comparación con la plantilla previa confirmó que las columnas A:J originales permanecen idénticas. Los controles de respuestas por ODS/PDOT dieron 0 errores lógicos, 0 fórmulas erróneas y 47 marcas `LISTO`. El original es un XLSX válido, sin macros.

### Conteo de los conflictos A/B

| Tipo | Casos |
|---|---:|
| Solo ODS principal | 26 |
| Solo PDOT principal | 12 |
| Ambas taxonomías | 9 |
| **Total tesis distintas** | **47** |
| Conflictos ODS (incluidas ambas) | 35 |
| Conflictos PDOT (incluidas ambas) | 21 |

La propuesta técnica incluye 5 casos con `sdg_no_match=yes` y 2 con `pdot_no_match=yes`, sin contradicciones estructurales. Son cifras **del subgrupo seleccionado de 47 conflictos**, NO estimaciones de prevalencia para las 7.830 tesis.

## ¿La adjudicación es ya definitiva?

**NO.** En los 47 registros el campo de responsable dice literalmente `Adjudicación técnica asistida por IA; firma de comité pendiente`. La hoja `CONTROL_TECNICO` declara como `PENDIENTE`:

1. aprobación humana documentada;
2. libro de códigos PDOT contrastado con documentación territorial;
3. protocolo/acta de adjudicación firmado.

El estado `LISTO` solo significa campos rellenados de manera formal, **no ratificación por expertos**. La hoja dice que se consultaron TXT originales, pero tal revisión no fue verificada independientemente con los documentos completos en esta auditoría. El archivo identifica dos colecciones que parecen ser volúmenes colectivos (memorias de evento y revista) y no tesis individuales; requiere controlar la unidad de análisis.

El coordinador ha comunicado que los revisores A/B/C afirman haber tomado decisiones humanas y utilizado IA solo para formato/redacción. Esa comunicación se documenta sin eliminar las atribuciones originales de asistencia IA presentes en los archivos. Las 47 propuestas nuevas de esta hoja requieren **firma propia**: no puede suponerse que la declaración anterior sobre A/B/C avale automáticamente nuevas decisiones.

## Requisitos mínimos para producir una referencia adjudicada

1. Comité humano: revisar casos conflictivos contra los documentos y **confirmar o corregir** las 47 propuestas. Registrar revisor(es), fecha real, fundamento y observaciones concretas. Conservar la versión recibida y los cambios, no editar ni suprimir su origen de IA.
2. Las otras **403 coincidencias A=B** necesitan una regla de ratificación documentada y aprobada; no implican automáticamente una verdad sin sesgos. Revisar aleatoriamente una muestra de control si es viable.
3. Solucionar los dos casos pendientes de estructura de referencias por otra vía; no autorizar recortes de bibliografías/anexos mediante esta hoja temática.
4. Verificar los **17 descriptores ODS, seis etiquetas PDOT analíticas y diez necesidades**: versión, formulación exacta, fuentes y linaje del código original. La taxonomía analítica PDOT no debe presentarse como seis ejes oficiales idénticos.
5. Congelar las 450 etiquetas de referencia una vez verificadas y documentadas, incluyendo la opción `NONE`/sin correspondencia. Distinguir 120 aleatorios y 330 enriquecidos, y declarar el soporte por clase.
6. Calcular precisión, recall y F1 **por categoría** del clasificador original y de la(s) representación(es) fulltext, con curva cobertura–rendimiento para abstención; no inferir F1 a partir del kappa humano.
7. Ejecutar un baseline keyword/TF-IDF y una sensibilidad de descriptores; ambos estaban bloqueados a la última auditoría por manifiesto incompleto.
8. Usar predicciones finales coherentes para rehacer figuras, tablas, estadísticas e interpretación ODS 4; documentar construcción del corpus, OCR, eticidad y acceso a datos, selección de k, limitaciones y política ecuatoriana.
9. Reescribir el manuscrito y contestar **punto por punto a los cuatro revisores** con los resultados efectivamente obtenidos, páginas/secciones correctas, bibliografía sin DOI duplicado, y limitaciones explícitas.

## Publicación segura del expediente

El repositorio `julioggg/utn_thesis_atlas` es **PÚBLICO**. Por diseño, el XLSX original contiene identificadores/handles, extractos institucionales y justificaciones individuales y **no se copió a GitHub público**. Su constancia auditable (hash, metadatos, conteos y advertencias) está en:

`docs/audits/reviewer_47_adjudication_private_workbook_audit_2026_11_15.json`

El archivo íntegro deberá conservarse en la carpeta privada de CEDIA y, si se necesita repositorio remoto, en un repositorio **privado con acceso controlado**. No crear un branch de un repositorio público pensando que protegerá los datos: las ramas públicas siguen siendo públicas.

## Estado resumido ante los revisores

No existe exigencia editorial literal de **tercer evaluador** ni adjudicación de las 450. R1 exige dos anotadores y precision/recall por ODS/PDOT; R3 admite dos o tres y solicita F1; R4 validación experta y desempeño. Las 450 anotaciones A/B y su kappa ya se obtuvieron, por lo que rehacer una tercera revisión completa no aporta valor inmediato. **Sí falta evaluar el modelo contra anotaciones humanas**, de manera no engañosa. En caso de plazo inmediato, es factible reportar métricas separadas frente a A/B, con incertidumbre, aclarando que no constituyen referencia consensuada.

Las demás brechas se detallan en `docs/SUSTAINABILITY_FOUR_REVIEWERS_FINAL_GAP_MATRIX_2026_11_15_ES.md`.

**No publicar automáticamente métricas de exactitud, no usar las 47 propuestas sin firma como gold standard, no subir los TXT completos ni el XLSX a GitHub público.**
