# Stage 2 — Simulaciones XFOIL

## Objetivo

Ejecutar XFOIL para el perfil seleccionado (NACA 65-410) en una matriz completa de 12 casos: 4 condiciones de vuelo × 3 secciones de pala. Cada caso produce una polar completa (CL, CD, CM, CL/CD vs α).

## Matriz de simulaciones

| Condición | M objetivo | Ncrit | Root Re | Mid Re | Tip Re |
|---|---|---|---|---|---|
| Takeoff | 0.30 | 5.0 | 2.5 × 10⁶ | 4.5 × 10⁶ | 7.0 × 10⁶ |
| Climb | 0.70 | 6.0 | 2.2 × 10⁶ | 4.0 × 10⁶ | 6.2 × 10⁶ |
| Cruise | 0.85 | 7.0 | 1.8 × 10⁶ | 3.2 × 10⁶ | 5.0 × 10⁶ |
| Descent | 0.75 | 6.0 | 2.0 × 10⁶ | 3.6 × 10⁶ | 5.6 × 10⁶ |

> Todas las simulaciones XFOIL se ejecutan a M = 0.2 (incompresible). La corrección de compresibilidad se aplica en Stage 3.

Rango α: −5° a 23°, paso 0.15° → ~190 puntos por caso.

## Salidas

```
results/stage_2/final_analysis/{condition}/{section}/
├── polar.dat      # Salida bruta de XFOIL
└── polar.csv      # Columnas: alpha, cl, cd, cm, ld, re, ncrit

results/stage_2/polars/{condition}_{section}.csv   # Layout plano organizado
```

## Código relevante

- `src/vfp_analysis/core/services/final_analysis_service.py` — lógica de simulación
- `src/vfp_analysis/adapters/xfoil/xfoil_runner_adapter.py` — invocación de XFOIL
- `src/vfp_analysis/xfoil_runner.py` — gestión del subproceso XFOIL
- `src/vfp_analysis/postprocessing/polar_organizer.py` — reorganización de archivos
