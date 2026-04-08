# Stage 3 — Corrección de compresibilidad (Prandtl-Glauert)

## Objetivo

Corregir los coeficientes aerodinámicos de las polares XFOIL (obtenidas a M = 0.2) para reflejar el comportamiento real a los Mach de vuelo de cada condición.

## Corrección aplicada

**Regla de Prandtl-Glauert** (válida para M < 0.8):

```
CL_corr = CL / √(1 − M²)
CD_corr = CD               (conservador: sin corrección de onda)
CL/CD_corr = CL_corr / CD_corr
```

| Condición | M objetivo | Factor √(1−M²) |
|---|---|---|
| Takeoff | 0.30 | 0.954 |
| Climb | 0.70 | 0.714 |
| Cruise | 0.85 | 0.527 |
| Descent | 0.75 | 0.661 |

> La corrección es más significativa en cruise (M = 0.85), donde la resistencia de onda empieza a ser relevante.

## Salidas

```
results/stage_3/{condition}/{section}/
├── corrected_polar.csv       # Columnas completas incluyendo cl_corrected, ld_corrected
├── corrected_cl_alpha.csv    # Solo (alpha, cl_corrected)
├── corrected_efficiency.csv  # Solo (alpha, ld_corrected)
└── corrected_plots.png       # Comparación original vs corregido
```

## Código relevante

- `src/vfp_analysis/compressibility/core/services/compressibility_correction_service.py` — orquestación e I/O
- `src/vfp_analysis/compressibility/adapters/correction_models/prandtl_glauert_model.py` — fórmula de corrección
- `src/vfp_analysis/compressibility/core/domain/compressibility_case.py` — parámetros del caso
