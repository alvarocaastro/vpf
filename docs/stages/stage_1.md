# Stage 1 — Selección automática de perfil aerodinámico

## Objetivo

Comparar cuatro perfiles candidatos de la familia NACA 6-series y seleccionar el más adecuado para la pala del fan mediante una función de puntuación multicritério.

## Perfiles candidatos

| Perfil | Familia | Espesor | Curvatura |
|---|---|---|---|
| NACA 65-210 | 65-series | 10 % | 2 % |
| NACA 65-410 | 65-series | 10 % | 4 % |
| NACA 63-215 | 63-series | 15 % | 2 % |
| NACA 0012 | Simétrico | 12 % | 0 % |

## Condición de simulación (referencia)

- Reynolds: 3.0 × 10⁶
- Mach: 0.2 (incompresible, base XFOIL)
- Ncrit: 7.0
- Rango α: −5° a 20°, paso 0.15°

## Función de puntuación

```
S = 1.0 · (CL/CD)_max + 5.0 · α_stall − 5000 · C̄_D
```

- `(CL/CD)_max`: eficiencia aerodinámica máxima
- `α_stall`: ángulo en el máximo de CL (margen de entrada en pérdida)
- `C̄_D`: resistencia media (penaliza perfiles con alta resistencia de base)

## Resultado

**Perfil seleccionado: NACA 65-410** — mejor equilibrio entre eficiencia, margen de pérdida y resistencia de base.

## Salidas

```
results/stage_1/airfoil_selection/
├── polars_comparison.csv    # Polares de los 4 candidatos
├── scores.csv               # Puntuaciones por criterio
└── selected_airfoil.dat     # Nombre del perfil seleccionado
```

## Código relevante

- `src/vfp_analysis/core/services/airfoil_selection_service.py` — orquestación
- `src/vfp_analysis/core/domain/scoring.py` — función de puntuación
- `data/airfoils/` — archivos `.dat` de geometría
