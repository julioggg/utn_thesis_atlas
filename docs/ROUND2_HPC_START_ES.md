# Sustainability — segunda ronda editorial: inicio en CEDIA

Este protocolo trabaja en el **clon de revisión** y deja intacto el proyecto original. No sube PDFs, texto extraído, IDs de estudiantes, etiquetas por tesis, matrices de embeddings, rutas internas, registros individuales ni logs privados. El repositorio de GitHub es **público**.

## Paso 1. Actualizar e inventariar (sin GPU)

Dentro del entorno Singularity de CEDIA, donde ya está disponible Python:

```bash
cd "$HOME/utn_thesis_atlas_revision"
git status --short
git pull --ff-only origin main
python scripts/round2_readiness.py --project-root "$HOME/utn_thesis_atlas"
cat docs/audits/round2_readiness.json
```

Si `git status --short` muestra cambios propios, no fuerces el pull: guarda primero tus cambios. Si la ruta original difiere, reemplaza `$HOME/utn_thesis_atlas` por la ruta verdadera (no publiques esa ruta).

**Importante:** este informe solo revisa PRESENCIA en rutas esperadas, no calidad ni contenido de los resultados. Una ausencia no demuestra que el análisis nunca se ejecutó. El informe no sobrescribe salidas preexistentes.

## Paso 2. Revisar antes de publicar

Comprueba manualmente `docs/audits/round2_readiness.json` (contiene únicamente estados booleanos, no rutas privadas). Si es apropiado publicarlo:

```bash
git add docs/audits/round2_readiness.json
python scripts/git_safety.py
git diff --cached -- docs/audits/round2_readiness.json
git commit -m "Add reviewed round-two HPC readiness status"
git push origin main
```

No ejecutes `git add .`, ni subas la carpeta `data/`, capturas de logs ni informes sin inspeccionar. Si no tienes permisos de push, entrega únicamente el estado mostrado en pantalla.

## Paso 3. Auditar los vacíos en orden científico

1. **Corpus:** reconciliar número inicial, duplicados, errores de extracción y elegibilidad final de 7.830.
2. **Validación:** confirmar código, protocolo y resultados A/B, muestra aleatoria de 120, enriquecida de 330 y adjudicaciones.
3. **Fiabilidad top-1:** comparar certeza y abstención de forma separada de los resultados confirmatorios; nunca calibrar umbrales con los mismos 120 usados para evaluación.
4. **Tópicos:** verificar k=75, semillas, ARI y sensibilidad a k alternativos. El script `reviewer_stage3_stability.py` es exploratorio, no recrea necesariamente el pipeline original.
5. **Territorio:** documentar los diez descriptores locales con fuentes oficiales y distinguir los seis grupos analíticos del PDOT oficial.
6. **Facultad:** comparar los 6.038 confirmados con los 188 imputados; describir sesgo posible de los 1.604 no resueltos.

No lances automáticamente la suite completa ni recálculos de embeddings de 286 millones de tokens; primero examinaremos qué existe y qué falta realmente.

## Paso 4. Compartir resultados agregados

El archivo `round2_readiness.json` puede publicarse tras revisión. Los otros informes de `docs/audits/` deben evaluarse uno por uno en cuanto a exactitud, identificación indirecta y condiciones de licencia. No hay aprobación automática para `git add -f` ni para modificar `.gitignore`.

Guarda localmente los logs privados de errores. Si un comando falla, comunica el nombre del script, código de salida y mensaje resumido sin rutas, identificadores ni credenciales.

## Matriz de respuesta a revisores

| Solicitud | Evidencia imprescindible |
| --- | --- |
| R2, top-1 sin umbral | Score máximo, margen, curvas de cobertura-precisión, evaluación independiente |
| R4, originalidad | Tabla crítica de métodos y contribución verificable |
| R4, selección del corpus | Flujo de registros y exclusiones auditables |
| R4, 450 codificados | Diseño muestral, manual de codificación, expertise, adjudicación |
| R4, 75 tópicos | Parámetros, semillas, estabilidad y ejemplos revisados |
| R4, LP01–LP10 | Definiciones y fuente primaria correspondiente |
| R4, error de clasificación | Sensibilidad de distribuciones, intervalos y límites de clases escasas |
| R4, facultades faltantes | Sensibilidad a registros imputados/no resueltos |
| R4, implementación | Responsables, indicadores, revisión humana, gestión de datos |

Toda afirmación que dependa de nuevo cómputo debe mantenerse pendiente hasta contar con salidas reales validadas.
