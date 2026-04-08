# Stage 8 — Análisis de consumo específico (SFC)

## Objetivo

Cuantificar la mejora de consumo específico de combustible (SFC) que aporta el VPF, transformando la ganancia de eficiencia aerodinámica 2D en una mejora de eficiencia del fan 3D y finalmente en reducción de SFC.

## Modelo de transferencia de eficiencia

La ganancia 2D (CL/CD) no se traslada directamente al fan 3D por pérdidas de vórtice de tip, flujos secundarios y pérdidas de onda. Se aplica un coeficiente conservador:

```
η_fan_nuevo = η_fan_base · [1 + 0.65 · ((CL/CD)_VPF / (CL/CD)_base − 1)]
```

### Relación SFC–eficiencia

```
SFC ∝ 1 / η_overall   →   SFC_nuevo ≈ SFC_base · (η_base / η_nuevo)
```

### Parámetros de motor (baseline)

| Parámetro | Valor |
|---|---|
| SFC de crucero | 0.55 lb/(lbf·hr) |
| Eficiencia del fan | 88 % |
| Bypass ratio | 10.0 |
| Coef. transferencia | 0.65 |

## Multiplicadores de SFC por condición

| Condición | Multiplicador |
|---|---|
| Takeoff | 1.15 |
| Climb | 1.05 |
| Cruise | 1.00 (referencia) |
| Descent | 0.95 |

## Resultados esperados

- **Takeoff**: reducción de SFC ≈ 4–5 %
- **Climb**: reducción de SFC ≈ 3–4 %
- **Cruise**: mejora mínima (punto de diseño)
- **Descent**: mejora moderada ≈ 2 %

## Salidas

```
results/stage_8/
├── figures/
│   ├── sfc_vs_condition.png            # SFC base vs VPF por condición
│   ├── sfc_reduction_percent.png       # Porcentaje de mejora
│   ├── fan_efficiency_improvement.png  # Eficiencia del fan antes/después
│   └── efficiency_vs_sfc.png          # Scatter CL/CD vs SFC
└── tables/
    └── sfc_analysis.csv
```

## Código relevante

- `src/vfp_analysis/sfc_analysis/core/services/sfc_analysis_service.py`
- `src/vfp_analysis/sfc_analysis/core/services/propulsion_model_service.py`
- `src/vfp_analysis/sfc_analysis/application/run_sfc_analysis.py`
- `config/engine_parameters.yaml`
