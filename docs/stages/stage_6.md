# Stage 6 — Análisis VPF: ángulos óptimos y ajuste de paso

## Objetivo

Calcular el ángulo de ataque óptimo (α_opt) para cada condición de vuelo y sección, y cuantificar el ajuste de paso aerodinámico necesario respecto a la condición de crucero (referencia).

## Metodología

1. Para cada uno de los 12 casos, leer la polar corregida (Stage 3) y aplicar `find_second_peak_row()` → obtener α_opt y (CL/CD)_max.
2. Calcular el ajuste de paso aerodinámico relativo al crucero:

```
Δα_aero = α_opt(condición) − α_opt(crucero)
```

Este delta representa cuánto habría que rotar la pala para mantener la eficiencia óptima en cada fase de vuelo.

## Salidas

```
results/stage_6/
├── figures/
│   ├── vpf_alpha_opt_by_section.png
│   ├── vpf_pitch_adjustment_absolute.png
│   └── vpf_pitch_adjustment_relative.png
└── tables/
    ├── vpf_optimal_pitch.csv      # α_opt y (CL/CD)_max por caso
    └── vpf_pitch_adjustment.csv  # Δα_aero por condición y sección
```

## Código relevante

- `src/vfp_analysis/vpf_analysis/core/services/optimal_incidence_service.py`
- `src/vfp_analysis/vpf_analysis/core/services/pitch_adjustment_service.py`
- `src/vfp_analysis/vpf_analysis/application/run_vpf_analysis.py`
