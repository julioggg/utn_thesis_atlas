# V2: longitud y facultad — hallazgos confirmados de estandarización de soporte común

**Fecha del análisis:** 14 de noviembre de 2026 (CEDIA).  
**Estado:** comparación descriptiva completa; sin evaluación humana ni inferencia causal.  
**Fuente original:** `07_alignment_pdot_ods_needs.parquet`; embeddings E5-large originales y 7.830 fulltext; controles sobre 490 checkpoints.  
**Script:** `scripts/reviewer_length_faculty_common_support_v2.py`.

## Universo de inferencia y control de soporte

- Corpus: **7.830 tesis**.
- Grupos estrictos: cinco facultades originalmente identificadas y un grupo residual de metadatos no verificados.
- Para cada grupo, exigencia de **n>=30 en Q1 y Q4** (cuartiles globales de tokens de texto completo).
- Cinco grupos elegibles, **7.127 tesis (91,0 %)**. **Excluidos del estimando restringido: 703 registros de Facultad de Ciencias de la Salud**, por falta de soporte en Q4.
- Los pesos del estimador ajustado son frecuencias de facultad entre las 7.127 tesis elegibles, constantes para ambos cuartiles. **No es una estimación estandarizada de las 7.830 tesis.**
- Intervalos de remuestreo percentil 95 % generados con 1.000 repeticiones dentro de cada celda; representan variabilidad condicional a los grupos observados. No representan una muestra aleatoria de la población nacional.

## Comparación de Q4 menos Q1 (puntos porcentuales)

| Categoría/indicador | Diferencia cruda de los 7.830 | Diferencia estandarizada sobre soporte común | Intervalo condicional 95 % |
|---|---:|---:|---|
| Proporción ODS 4 de texto completo | −7,958 | +1,362 | [−1,172; +3,941] |
| Proporción PDOT Asentamientos–Movilidad de texto completo | +14,234 | +7,659 | [+4,303; +10,764] |
| Proporción necesidad Salud–Nutrición de texto completo | −17,102 | −2,778 | [−5,339; −0,181] |
| Tasa de cambios originales→fulltext ODS | +11,563 | +5,055 | [+1,783; +8,479] |
| Tasa de cambios originales→fulltext PDOT | −1,514 | −2,461 | [−6,044; +0,900] |
| Tasa de cambios originales→fulltext necesidades | +8,189 | +3,075 | [−0,124; +6,370] |

**Importante:** las columnas de crudo y ajustado difieren en población *y* método. Para cuantificar separadamente composición y exclusión debe compararse también `crude_eligible_faculties_only`, ya calculado y guardado en el JSON privado local de auditoría agregada `docs/audits/reviewer_length_faculty_common_support_v2.json` de CEDIA.

## Interpretación crítica

1. **ODS 4:** el gradiente crudo negativo deja de observarse después de restringir y ajustar por facultad; intervalo de soporte común incluye cero. No concluir que las tesis largas tienen más o menos relación real con educación.
2. **PDOT:** el incremento de asignaciones a Asentamientos–Movilidad persiste (+7,659 pp), pero es menor que en el corpus bruto. La señal no es uniforme: Educación +17,758 pp y Administración +24,334 pp entre Q4−Q1 dentro de facultad; Aplicadas −2,570 pp, Agropecuarias −3,648 pp, grupo no verificado +0,986 pp. Es una señal para auditar amplitud del descriptor y contenido extraído, no prueba de sesgo ni impacto territorial.
3. **Necesidades Salud–Nutrición:** el gradiente crudo negativo se atenúa considerablemente. Intervalo apenas excluye cero; no extrapolar a Salud, excluida de la población ajustada.
4. **Cambios de top-1 ODS:** crecen +5,055 pp tras ajuste por facultad restringida; un cambio de etiqueta no es una corrección validada de clasificación.

## Próximos pasos ya bloqueantes para el manuscrito

- **80 tesis de control de fronteras de secciones:** auditoría `scripts/audit_section_boundary_review.py`. La última instantánea pública mostraba 0/80 evaluadas. No recortar bibliografías/anexos sin evidencia manual y un procedimiento de extracción validado.
- **450 tesis para dos evaluadores:** 120 de muestra aleatoria y 330 de enriquecimiento dirigido; última instantánea pública 0/450 por evaluador. Requiere dos codificadores verdaderamente independientes, codebook con fuente documental verificable, adjudicación, luego precisión/recall/F1, kappa y calibración del mecanismo de abstención.
- Las **seis etiquetas PDOT** del pipeline son analíticas y no se pueden presentar como transcripción literal del PDOT institucional sin trazabilidad; las diez necesidades también requieren fuente.
- Conservar las clasificaciones individuales, handles, textos extraídos y matrices solo en `data/revision_private` de CEDIA.

## Comprobación complementaria sin ejecutar E5

```bash
cd "$HOME/utn_thesis_atlas_revision"
python - <<'PY'
import json
from pathlib import Path
d=json.loads(Path("docs/audits/reviewer_length_faculty_common_support_v2.json").read_text())
for k,x in d["taxonomies"].items():
    print("\n",k.upper())
    for mode in ("crude_all_faculties","crude_eligible_faculties_only","direct_standardization_on_common_support"):
        print(mode)
        for metric in ("fulltext_target_share","original_vs_fulltext_flip_share"):
            rec=x[mode][metric]
            print(metric, rec["q4_minus_q1_percentage_points"], "pp",
                  rec.get("within_cell_bootstrap_95pct_ci_pp"))
PY
```

Ajuste retrospectivo condicionado a un censo institucional; no equivale a una estimación causal, validación predictiva ni efecto de política.
