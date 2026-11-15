# Paquetes Excel listos para codificación humana ciega (450 tesis) y revisión estructural (80 tesis)

**Finalidad:** entregar a dos evaluadores humanos independientes la evidencia científica real de cada tesis y un formulario con instrucciones, sin mostrar resultados de E5 ni estratos de muestreo. El coordinador también recibe la auditoría estructural independiente de 80 tesis. **Estos paquetes contienen material privado del repositorio institucional; nunca subir a GitHub.**

## A. Plantillas generales disponibles en ChatGPT

- `Plantilla_validacion_humana_450_ODS_PDOT.xlsx`: formulario editable con 450 filas TH-0001...TH-0450 (sin los identificadores privados ni textos, que solo están en CEDIA); guías y catálogos ODS/PDOT; control.
- `Plantilla_revision_estructural_80_tesis.xlsx`: formulario para los 80 casos de fronteras de sección.

Las plantillas independientes no sustituyen los paquetes completos: para entregar **todas las fuentes reales** de las tesis, generar en CEDIA los ZIP que se describen a continuación.

## B. Generar paquetes reales en CEDIA con un único comando

```bash
cd "$HOME/utn_thesis_atlas_revision"
git pull --ff-only origin main
source "$HOME/.venvs/utn-atlas-audit/bin/activate"

python scripts/export_blinded_validation_workbooks.py \
  --project-root "$HOME/utn_thesis_atlas"
```

Se leen los siguientes archivos exclusivamente privados:

- `data/revision_private/validation/sample_master_private.csv` (450 filas congeladas, 120 aleatorias + 330 enriquecidas).
- `data/revision_private/validation/coder_A_private.csv`, `coder_B_private.csv` (dos órdenes independientes, sin predicciones).
- `data/revision_private/section_boundary_review_v1/section_boundary_review_private.csv` (80 casos, sin superposición con los 450).
- `$HOME/utn_thesis_atlas/data/processed/04_clean_corpus.parquet`, columnas reales `handle_id`, `full_text` y título/resumen si las contiene.

El generador no necesita GPU ni recodifica tesis. Valida que los 450 identificadores coincidan con el muestreo congelado y busca los textos de los 530 documentos en el corpus original.

**Salida privada:**

```text
data/revision_private/validation_excel_packages/
 ├─ Evaluador_A_450_tesis_PRIVADO.zip
 ├─ Evaluador_B_450_tesis_PRIVADO.zip
 └─ Revision_estructural_80_tesis_PRIVADO.zip
```

Cada ZIP de los evaluadores contiene un archivo `.xlsx` y una carpeta `Evidencias/` con **450 documentos de texto completo**, nombrados por ID ciego. El Excel dispone de pestañas `INSTRUCCIONES`, `ANOTACION`, `FUENTES`, `CAT_ODS` y `CAT_PDOT`, sin predicciones ni facultad. El paquete estructural contiene 80 TXT y un Excel con `REVISION_80`.

**ATENCIÓN:** estos ZIP no están cifrados. Deben transferirse a cada evaluador por un canal institucional con acceso controlado, después de verificar permisos de uso de las tesis y política de protección de datos. Extraer cada ZIP entero antes de abrir las rutas relativas de `Evidencias/`.

## C. Qué debe completar el evaluador

En `ANOTACION`, los campos de entrada son los originales del protocolo:

| Columna | Campo | Instrucción |
|---|---|---|
| C | `sdg_primary` | `ODS 1` a `ODS 17`, o vacío si no existe correspondencia |
| D | `sdg_secondary` | Otro ODS realmente sustentado, opcional |
| E | `sdg_no_match` | `yes` si no hay ningún ODS defendible; `no` en caso contrario |
| F | `pdot_primary` | `PDOT 1` a `PDOT 6`, o vacío si no corresponde |
| G | `pdot_secondary` | Otro PDOT sustentado, opcional |
| H | `pdot_no_match` | `yes` si no existe eje defendible; `no` en caso contrario |
| I | `uncertain` | `yes` o `no` según evidencia o dudas |
| J | `brief_evidence` | Justificación propia con sección, objetivo y hallazgo |
| K | `coder_notes` | Observaciones de OCR, dudas y posibles conflictos |

Los campos A-B son identificadores congelados. El evaluador lee el TXT completo, no solo los extractos mostrados en `FUENTES`.

En `REVISION_80`, se llenan exclusivamente cinco campos humanos: veracidad del encabezado de referencias, corrección de su posición, valor científico del texto posterior, aprobación justificada del recorte y notas. Nunca aprobar automáticamente el recorte con evidencia ambigua.

## D. Libro de códigos y bloqueo metodológico

Los nombres y la numeración ODS siguen el marco oficial de los 17 Objetivos: https://sdgs.un.org/goals

Los seis rótulos PDOT son la **taxonomía analítica del atlas original**, no una transcripción comprobada de los seis componentes oficiales del PDOT provincial 2023–2027. La Prefectura publica los documentos: https://www.imbabura.gob.ec/index.php/pdot-aprobado-2023-2027

**Antes de distribuir los libros**, el coordinador debe elaborar, aprobar y congelar un libro de códigos PDOT independiente y respaldado en el documento provincial; no copiar sin justificación los descriptores utilizados para entrenar/evaluar el modelo, porque esto puede contaminar la independencia del juicio humano. Debe permitir ninguna coincidencia y justificar las fusiones analíticas de categorías. Las diez necesidades territoriales NO están incluidas en esta etapa de anotación y requieren protocolo de validación separado si van a presentarse como etiquetas validadas.

## E. Importar las respuestas luego de terminadas

Los scripts de importación usan únicamente la biblioteca estándar Python para leer el XLSX, comprueban los IDs/handles originales y **no reemplazan respuestas previas distintas**. Primero revisar sin aplicar:

```bash
python scripts/import_blinded_validation_excel.py \
  --coder A --workbook /RUTA/SEGURA/Evaluador_A_450_tesis.xlsx

python scripts/import_blinded_validation_excel.py \
  --coder B --workbook /RUTA/SEGURA/Evaluador_B_450_tesis.xlsx

python scripts/import_section_boundary_excel.py \
  --workbook /RUTA/SEGURA/Revision_estructural_80_tesis.xlsx
```

Tras revisar el número de celdas importadas, ejecutar los mismos comandos con `--apply`, que conserva una copia privada anterior del CSV correspondiente. Se hace **una sola importación definitiva** por evaluador o se reconcilia manualmente si existe una copia anterior. A continuación:

```bash
python scripts/audit_annotation_progress.py
python scripts/audit_section_boundary_review.py
```

Los informes de progreso son agregados. **No informar kappa, exactitud, precisión, recall, F1 ni permitir calibración de umbrales hasta que la doble codificación independiente esté terminada y adjudicada.** Reservar los 330 casos enriquecidos para calibración; los 120 aleatorios permiten evaluación independiente y estimaciones poblacionales con incertidumbre.
