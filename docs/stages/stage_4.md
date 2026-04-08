# Stage 4 — Extracción de métricas y tablas

## Objetivo

Extraer los indicadores de rendimiento aerodinámic clave de las polares corregidas y exportarlos como tablas CSV listas para LaTeX/thesis.

## Métricas calculadas por caso

| Métrica | Descripción |
|---|---|
| `max_efficiency` | (CL/CD)_max en el segundo pico |
| `alpha_opt` | Ángulo de ataque en el segundo pico |
| `cl_max` | CL máximo (ángulo de pérdida) |
| `cl_at_opt` | CL en α_opt |
| `cd_at_opt` | CD en α_opt |

### Segundo pico de eficiencia

XFOIL predice un primer pico de CL/CD a α muy bajo (< 3°) asociado a la burbuja de separación laminar, que no es representativo de la operación real en turbomaquinaria. Se toma el **segundo pico** (α ≥ 3°) como punto operativo.

## Tablas exportadas

```
results/stage_4/tables/
├── summary_table.csv         # Todas las métricas por condición y sección
└── clcd_max_by_section.csv   # CL, CD y CL/CD en el punto óptimo
```

## Código relevante

- `src/vfp_analysis/postprocessing/metrics.py` — cálculo de métricas
- `src/vfp_analysis/postprocessing/table_generator.py` — exportación CSV
- `src/vfp_analysis/postprocessing/aerodynamics_utils.py` — `find_second_peak_row()`
