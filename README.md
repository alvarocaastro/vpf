# Variable Pitch Fan Aerodynamic Analysis

Pipeline en Python para analizar el rendimiento aerodinámico de un fan de paso variable a partir de perfiles NACA, simulaciones XFOIL, correcciones de compresibilidad, métricas de operación óptima, análisis cinemático y estimación del impacto en consumo específico de combustible.

## Qué hace el proyecto

El flujo completo:

1. selecciona automáticamente un perfil aerodinámico candidato
2. ejecuta 12 simulaciones XFOIL para distintas condiciones y secciones
3. corrige compresibilidad con Prandtl-Glauert
4. extrae métricas y tablas resumen
5. genera figuras para memoria o TFG
6. calcula el punto óptimo de operación con VPF
7. traduce ese ajuste a pitch mecánico mediante cinemática
8. estima la reducción potencial de SFC

## Resultado principal de la ejecución actual

- perfil seleccionado: `NACA 65-410`
- rango de `alpha_opt`: `5.35°` a `7.30°`
- mejor caso de reducción de SFC: `takeoff`, con `4.96 %`
- mejora media simple de SFC en las cuatro condiciones analizadas: `2.46 %`

## Requisitos

- Python 3.10 o superior recomendado
- XFOIL instalado y accesible
- Dependencias de `requirements.txt`

## Instalación

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Si XFOIL no está en el `PATH`, puedes indicar su ubicación con una variable de entorno:

```powershell
$env:XFOIL_EXE="C:\ruta\a\xfoil.exe"
```

El proyecto también intenta localizar el ejecutable en algunas rutas típicas definidas en `src/vfp_analysis/config.py`.

## Ejecución

Para lanzar el pipeline completo:

```bash
python run_analysis.py
```

Los parámetros principales del estudio se configuran en:

- `config/analysis_config.yaml`
- `config/engine_parameters.yaml`

## Estructura del repositorio

```text
.
├── config/          # parámetros de simulación y motor
├── data/            # perfiles aerodinámicos y datos base
├── docs/            # documentación del proyecto y stages
├── results/         # salidas generadas por el pipeline
├── src/             # código fuente
├── tests/           # tests unitarios
└── run_analysis.py  # entrypoint principal
```

## Stages documentados

La documentación detallada de cada etapa está en `docs/stages_md/`:

- `docs/stages_md/stage1_airfoil_selection.md`
- `docs/stages_md/stage2_xfoil_simulations.md`
- `docs/stages_md/stage3_compressibility_correction.md`
- `docs/stages_md/stage4_performance_metrics.md`
- `docs/stages_md/stage5_publication_figures.md`
- `docs/stages_md/stage6_vpf_analysis.md`
- `docs/stages_md/stage7_kinematics_analysis.md`
- `docs/stages_md/stage8_sfc_analysis.md`

## Carpetas de resultados

El pipeline usa estas carpetas explícitas en `results/`:

- `stage1_airfoil_selection`
- `stage2_xfoil_simulations`
- `stage3_compressibility_correction`
- `stage4_performance_metrics`
- `stage5_publication_figures`
- `stage6_vpf_analysis`
- `stage7_kinematics_analysis`
- `stage8_sfc_analysis`

## Notas sobre la numeración

- El repositorio documenta 8 stages lógicos, pero `run_analysis.py` separa internamente algunos pasos adicionales.
- Cada stage escribe ahora en una carpeta explícita dentro de `results/`, con formato `stageX_funcion`.

## Tests

Para ejecutar la batería de tests:

```bash
pytest
```

## Código principal

- `run_analysis.py`
- `src/vfp_analysis/core/`
- `src/vfp_analysis/stage1_airfoil_selection/`
- `src/vfp_analysis/stage2_xfoil_simulations/`
- `src/vfp_analysis/stage3_compressibility_correction/`
- `src/vfp_analysis/stage4_performance_metrics/`
- `src/vfp_analysis/stage5_publication_figures/`
- `src/vfp_analysis/stage6_vpf_analysis/`
- `src/vfp_analysis/stage7_kinematics_analysis/`
- `src/vfp_analysis/stage8_sfc_analysis/`

## Estado actual

La base del pipeline está operativa y ya tiene resultados generados en `results/`. La documentación de `docs/stages_md/` y las carpetas de salida usan ahora la misma nomenclatura explícita por stage.
