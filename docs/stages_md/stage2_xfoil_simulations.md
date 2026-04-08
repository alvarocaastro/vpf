# Stage 2: Simulaciones aerodinámicas con XFOIL

## Propósito

Generar las polares aerodinámicas del perfil seleccionado para una matriz de 12 casos: 4 condiciones de vuelo por 3 secciones radiales de pala.

## Entradas

- Perfil seleccionado en Stage 1
- Configuración en `config/analysis_config.yaml`
  - condiciones: `takeoff`, `climb`, `cruise`, `descent`
  - secciones: `root`, `mid_span`, `tip`
  - rango de ataque: `alpha = [-5°, 23°]` con paso `0.15°`
  - `M = 0.2` como referencia incompresible para XFOIL

## Matriz de casos

| Condición | Ncrit | Root Re | Mid-span Re | Tip Re |
|---|---:|---:|---:|---:|
| Takeoff | 5.0 | 2.5e6 | 4.5e6 | 7.0e6 |
| Climb | 6.0 | 2.2e6 | 4.0e6 | 6.2e6 |
| Cruise | 7.0 | 1.8e6 | 3.2e6 | 5.0e6 |
| Descent | 6.0 | 2.0e6 | 3.6e6 | 5.6e6 |

## Metodología

1. Para cada combinación `condición × sección`, se construye una `SimulationCondition`.
2. Se ejecuta XFOIL sobre el perfil elegido.
3. Se guardan:
   - salida cruda `polar.dat`
   - salida tabular `polar.csv`
   - curvas auxiliares `cl_alpha`, `cd_alpha` y `efficiency`
4. Se reorganizan las polares en un layout plano adicional dentro de `results/stage2_xfoil_simulations/polars/`.

## Salidas

```text
results/stage2_xfoil_simulations/
├── final_analysis/{condition}/{section}/
│   ├── polar.dat
│   ├── polar.csv
│   ├── polar_plot.png
│   ├── cl_alpha.csv
│   ├── cl_alpha_plot.png
│   ├── cd_alpha.csv
│   ├── cd_alpha_plot.png
│   └── efficiency_plot.png
├── polars/
│   └── {condition}_{section}.csv
└── finalresults_stage2.txt
```

## Código relevante

- `src/vfp_analysis/stage2_xfoil_simulations/final_analysis_service.py`
- `src/vfp_analysis/adapters/xfoil/xfoil_runner_adapter.py`
- `src/vfp_analysis/xfoil_runner.py`
- `src/vfp_analysis/stage2_xfoil_simulations/polar_organizer.py`

## Observaciones

- Todas las simulaciones de esta etapa son incompresibles en `M = 0.2`.
- Los efectos de Mach real se corrigen después en Stage 3.
