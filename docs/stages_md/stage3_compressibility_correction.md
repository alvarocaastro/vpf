# Stage 3: Corrección de compresibilidad

## Propósito

Corregir las polares generadas por XFOIL para aproximar el comportamiento en los Mach de vuelo definidos para cada fase.

## Entradas

- Polares de `results/stage2_xfoil_simulations/final_analysis/`
- Mach objetivo por condición en `config/analysis_config.yaml`
  - takeoff: `0.30`
  - climb: `0.70`
  - cruise: `0.85`
  - descent: `0.75`

## Modelo aplicado

Se usa la corrección de Prandtl-Glauert, implementada en:

- `src/vfp_analysis/stage3_compressibility_correction/adapters/correction_models/prandtl_glauert_model.py`

De forma simplificada:

```text
CL_corr = CL / sqrt(1 - M^2)
CD_corr = CD
LD_corr = CL_corr / CD_corr
```

## Metodología

1. Se recorre cada polar de Stage 2.
2. Se construye un `CompressibilityCase` con Mach de referencia y Mach objetivo.
3. Se aplica la corrección a cada caso.
4. Se guardan tablas resumidas y una figura comparando resultados base y corregidos.

## Salidas

```text
results/stage3_compressibility_correction/{condition}/{section}/
├── corrected_polar.csv
├── corrected_cl_alpha.csv
├── corrected_efficiency.csv
└── corrected_plots.png

results/stage3_compressibility_correction/finalresults_stage3.txt
```

## Código relevante

- `src/vfp_analysis/stage3_compressibility_correction/core/services/compressibility_correction_service.py`
- `src/vfp_analysis/stage3_compressibility_correction/adapters/correction_models/prandtl_glauert_model.py`
- `src/vfp_analysis/stage3_compressibility_correction/core/domain/compressibility_case.py`

## Observaciones

- El modelo es deliberadamente conservador: aumenta `CL`, pero no introduce una corrección explícita de resistencia de onda.
- En el proyecto actual, esta etapa alimenta especialmente Stage 6, donde se priorizan los datos corregidos si están disponibles.
