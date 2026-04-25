# VPF Pipeline — Mapa completo del proyecto

> Documento de referencia para análisis de mejoras. Describe cada fichero, su
> responsabilidad, sus entradas/salidas y sus dependencias internas.
> El pipeline se ejecuta con `python run_analysis.py` y pasa por 7 etapas
> aerodinámica en cascada, desde la selección de perfil hasta el análisis de SFC.

---

## Estructura de directorios

```
vpf/
├── run_analysis.py                     # Punto de entrada principal
├── config/
│   ├── analysis_config.yaml            # Mach, Reynolds, perfil XFOIL
│   └── engine_parameters.yaml         # Motor GE9X, misión, empuje inverso
├── src/vfp_analysis/
│   ├── __init__.py
│   ├── settings.py                     # Constantes globales y rutas
│   ├── config_loader.py               # Lectura de YAMLs de configuración
│   ├── xfoil_runner.py                 # Invocación de XFOIL como subproceso
│   ├── pipeline/
│   │   └── contracts.py               # Dataclasses Stage1Result…Stage7Result
│   ├── core/domain/
│   │   ├── airfoil.py                  # Dataclass Airfoil
│   │   └── blade_section.py           # Dataclass BladeSection
│   ├── shared/
│   │   └── plot_style.py              # Estilo matplotlib compartido
│   ├── postprocessing/
│   │   ├── aerodynamics_utils.py      # Utilidades aerodinámicas compartidas
│   │   ├── cli_tables.py              # Tablas Rich para consola
│   │   └── stage_summary_generator.py # Generador de .txt por etapa
│   ├── validation/
│   │   └── validators.py              # Validadores de rutas y datos
│   ├── adapters/xfoil/
│   │   ├── xfoil_parser.py            # Parser de output de XFOIL
│   │   └── xfoil_runner_adapter.py    # Adaptador puerto→XFOIL real
│   ├── ports/
│   │   └── xfoil_runner_port.py       # Puerto abstracto (interfaz XFOIL)
│   ├── stage1_airfoil_selection/
│   │   ├── airfoil_selection_service.py
│   │   └── scoring.py
│   ├── stage2_xfoil_simulations/
│   │   ├── final_analysis_service.py
│   │   └── pitch_map.py
│   ├── stage3_compressibility_correction/
│   │   ├── correction_service.py
│   │   ├── compressibility_case.py
│   │   ├── correction_result.py
│   │   ├── critical_mach.py
│   │   ├── karman_tsien.py
│   │   └── prandtl_glauert.py
│   ├── stage4_performance_metrics/
│   │   ├── metrics.py
│   │   ├── plots.py
│   │   ├── narrative_figures.py
│   │   └── table_generator.py
│   ├── stage5_pitch_kinematics/
│   │   ├── pitch_kinematics_core.py
│   │   ├── application/run_pitch_kinematics.py
│   │   ├── adapters/filesystem/data_loader.py
│   │   ├── adapters/filesystem/results_writer.py
│   │   └── core/domain/pitch_kinematics_result.py
│   ├── stage6_reverse_thrust/
│   │   ├── reverse_thrust_core.py
│   │   ├── application/run_reverse_thrust.py
│   │   ├── adapters/filesystem/data_loader.py
│   │   ├── adapters/filesystem/results_writer.py
│   │   └── core/domain/reverse_thrust_result.py
│   └── stage7_sfc_analysis/
│       ├── sfc_core.py
│       ├── application/run_sfc_analysis.py
│       ├── core/domain/sfc_parameters.py
│       └── engine/
│           ├── engine_data.py
│           ├── turbofan_cycle.py
│           ├── sfc_model.py
│           └── ge9x_analysis.py
├── tests/
│   ├── conftest.py
│   ├── test_pipeline_contracts.py
│   ├── test_airfoil_selection.py
│   ├── test_airfoil_reader.py
│   ├── test_efficiency.py
│   ├── test_prandtl_glauert.py
│   └── test_reynolds.py
└── docs/
    └── project_map.md                  # Este fichero
```

---

## Punto de entrada

### `run_analysis.py` — 804 líneas

Orquestador principal. Ejecuta los 8 pasos del pipeline en secuencia con Rich
progress bars, paneles de estado y validación de contratos entre etapas.

**Pasos:**
| Paso | Función | Etapa lógica |
|------|---------|--------------|
| 1 | `step_1_airfoil_selection()` | Stage 1 |
| 2 | `step_2_create_directories()` | Setup |
| 3 | `step_3_xfoil_simulations()` | Stage 2 |
| 4 | `step_4_compressibility_corrections()` | Stage 3 |
| 5 | `step_5_metrics_and_figures()` | Stage 4 |
| 6 | `step_6_pitch_kinematics()` | Stage 5 |
| 7 | `step_7_reverse_thrust()` | Stage 6 |
| 8 | `step_8_sfc_analysis()` | Stage 7 |

**Dependencias:** todos los módulos `run_*.py`, `pipeline/contracts.py`,
`settings.py`, Rich, numpy, pandas.

**Puntos de atención:**
- Bloque `_stage_block()` con manejo de excepciones por etapa
- `_print_summary()` delega en `cli_tables.build_summary_table()`
- Cada `step_N` devuelve un `StageNResult` que es validado antes de continuar

---

## Configuración global

### `config/analysis_config.yaml`

Contiene los Mach objetivo y Reynolds por condición de vuelo y sección de pala
(root/mid_span/tip), plus la lista de perfiles NACA candidatos. Referencia
física: geometría GE9X, ISA por altitudes de vuelo.

### `config/engine_parameters.yaml`

Motor GE9X-105B1A. Secciones:
- `baseline_sfc`, `fan_efficiency`, `bypass_ratio` — usados por Stage 7 modelo analítico
- `mission.phases` — duración y fracción de empuje por fase (despegue/climb/cruise/descent)
- `reverse_thrust` — parámetros para Stage 6: fracción N1, velocidad aterrizaje, pesos
- `sfc_multipliers` — variación relativa de SFC por fase

### `src/vfp_analysis/settings.py` — 443 líneas

Constantes y rutas del proyecto. Reemplaza el antiguo `config.py`.

**Contenido:**
- `ROOT_DIR`, `AIRFOIL_DATA_DIR`, `RESULTS_DIR`, `STAGE_DIR_NAMES`
- `get_stage_dir(n)` — retorna `Path` al directorio de resultados de la etapa n
- Dataclasses de configuración: `SimulationSettings`, `CompressibilitySettings`,
  `PitchKinematicsSettings`, `PipelineSettings`
- `get_settings()` — devuelve instancia singleton `PipelineSettings`
- `AIRFOILS` — lista de `AirfoilSpec` con nombre, ruta DAT y descripción
- `XFOIL_EXECUTABLE` — descubrimiento automático del binario XFOIL en Windows/Linux
- `MACH_DEFAULT`, `N_CRIT_DEFAULT`

### `src/vfp_analysis/config_loader.py` — 206 líneas

Lee `analysis_config.yaml` y `engine_parameters.yaml` y expone:
- `get_simulation_conditions()` → lista de `SimulationCondition`
- `get_flight_conditions()` → lista de strings
- `get_mission_profile()` → `MissionProfile`
- `get_compressibility_config()` → dict con Mach por condición/sección

---

## Infraestructura compartida

### `src/vfp_analysis/pipeline/contracts.py` — 179 líneas

Define los contratos entre etapas como dataclasses con método `validate()`.

| Dataclass | Campos clave | Validación |
|-----------|-------------|------------|
| `Stage1Result` | `airfoil_name`, `dat_path`, `score` | dat existe, score > 0 |
| `Stage2Result` | `source_polars`, `polars_dir`, `pitch_map_csv` | dirs existen |
| `Stage3Result` | `n_cases_corrected`, `n_cases_failed`, `success_rate` | success_rate > 0 |
| `Stage4Result` | `metrics` (lista), `tables_dir`, `figures_dir` | lista no vacía |
| `Stage5Result` | `twist_total_deg`, `max_off_design_loss_pct`, `tables_dir` | twist > 0 |
| `Stage6Result` | `mechanism_weight_kg`, `sfc_cruise_penalty_pct` | peso > 0, n_tables ≥ 1 |
| `Stage7Result` | `mean_sfc_reduction_pct`, `ge9x_fuel_saving_pct` | no NaN |

### `src/vfp_analysis/shared/plot_style.py`

Context manager `apply_style()` y diccionarios de colores:
- `COLORS` — Paul Tol colorblind-safe por condición de vuelo
- `SECTION_COLORS` — colores por sección de pala
- `FLIGHT_LABELS`, `SECTION_LABELS` — etiquetas para leyendas
- Aplica rcParams de matplotlib (fontsize, DPI, sin spine top/right)

### `src/vfp_analysis/postprocessing/aerodynamics_utils.py` — 215 líneas

Utilidades compartidas entre plots de Stage 3/4/7:
- `resolve_efficiency_column(df)` — detecta la columna Cl/Cd correcta en un polar
  (busca en orden: `ld_corrected`, `CL_CD_corrected`, `ld_kt`, `ld`, `CL_CD`)
- `find_second_peak_row(df, col)` — encuentra el α_opt evitando el artefacto de
  burbuja de separación laminar (descarta el primer pico y busca el segundo)
- `_smart_annotation()` — posiciona anotaciones en gráficas sin solapamiento

### `src/vfp_analysis/postprocessing/cli_tables.py`

- `build_convergence_table(conv_log)` → Rich `Table` con resultados de convergencia XFOIL
- `build_summary_table(s1…s7, elapsed, results_dir)` → Rich panel resumen final

### `src/vfp_analysis/postprocessing/stage_summary_generator.py`

Genera un fichero `.txt` de resumen por etapa con los resultados clave
extraídos de los CSVs de resultados. Una función `generate_stageN_summary(dir)`
por etapa.

### `src/vfp_analysis/validation/validators.py` — 271 líneas

- `require_dir(path, label)` — lanza `ValueError`/`FileNotFoundError` si dir no existe
- `require_file(path, label)`
- `require_positive(value, label)`
- `require_in_range(value, lo, hi, label)`

### `src/vfp_analysis/xfoil_runner.py` — 251 líneas

Invoca XFOIL como subproceso, escribe el script de entrada, captura el output,
y retorna el polar como `pd.DataFrame`. Gestiona timeouts, reintentos y
codificación de salida en Windows (cp1252).

**Función principal:** `run_xfoil(airfoil_dat, alpha_range, Re, Mach, n_crit, ...)`

### `src/vfp_analysis/adapters/xfoil/`

- `xfoil_parser.py` — parsea el fichero `polar.txt` generado por XFOIL en DataFrame
- `xfoil_runner_adapter.py` — adaptador que implementa `XfoilRunnerPort` usando
  `xfoil_runner.py`

### `src/vfp_analysis/ports/xfoil_runner_port.py`

Clase abstracta `XfoilRunnerPort` con método `run(...)`. Permite sustituir
XFOIL por otro solver en tests o análisis alternativos.

### `src/vfp_analysis/core/domain/`

- `airfoil.py` — dataclass `Airfoil(name, dat_path, description)`
- `blade_section.py` — dataclass `BladeSection(name, radius_m, chord_m, Re, Mach)`
- `simulation_condition.py` — dataclass `SimulationCondition(flight, section, Re, Mach, alpha_range)`

---

## Stage 1 — Selección de perfil

### `stage1_airfoil_selection/airfoil_selection_service.py` — 117 líneas

Orquestador del Stage 1. Para cada perfil en `settings.AIRFOILS`:
1. Ejecuta XFOIL en condición de crucero (Re=3.2e6, M=0.2)
2. Llama a `scoring.score_airfoil(polar_df)` para calcular la puntuación
3. Selecciona el perfil con mayor puntuación
4. Copia el `.dat` al directorio de resultados

**Salida:** `Stage1Result` con el nombre del perfil ganador.

### `stage1_airfoil_selection/scoring.py` — 100 líneas

- `score_airfoil(polar_df)` — pondera Cl/Cd máximo, Cl a bajo ángulo, y robustez
  del polar (pendiente dCl/dα) para obtener un score escalar
- `AirfoilScore` — dataclass con los componentes del score

---

## Stage 2 — Simulaciones XFOIL

### `stage2_xfoil_simulations/final_analysis_service.py` — 247 líneas

Ejecuta XFOIL para las 12 combinaciones (4 condiciones × 3 secciones):
1. Itera sobre condiciones de vuelo y secciones de pala
2. Para cada combinación: construye `SimulationCondition`, invoca `XfoilRunnerAdapter`
3. Guarda `polar.csv` en `results/stage2_xfoil_simulations/{flight}/{section}/`
4. Al final del método `run()`, copia los polars a `polars/` como
   `{flight}_{section}.csv` (inlining del antiguo `polar_organizer.py`)

**Firma:** `FinalAnalysisService(base_results_dir, xfoil_runner).run(flight_conditions, blade_sections, progress_callback)`

### `stage2_xfoil_simulations/pitch_map.py` — 432 líneas

Construye el mapa de ángulo de paso (β) por condición y sección a partir de los
polares XFOIL. Para cada sección y condición de vuelo:
1. Lee el polar
2. Encuentra α_opt mediante `find_second_peak_row()`
3. Calcula el triángulo de velocidades: φ = atan(Va/U), β = α_opt + φ
4. Escribe `blade_pitch_map.csv` con columnas `flight, section, alpha_opt, phi_deg, beta_deg`

**Función principal:** `build_pitch_map(polars_dir, blade_sections, conditions, ...) → pd.DataFrame`

---

## Stage 3 — Correcciones de compresibilidad

### `stage3_compressibility_correction/correction_service.py` — 239 líneas

Para cada uno de los 12 casos (condición × sección):
1. Lee el polar XFOIL de Stage 2
2. Selecciona el método de corrección según el Mach objetivo:
   - M < 0.3 → sin corrección
   - 0.3 ≤ M < 0.7 → Prandtl-Glauert
   - 0.7 ≤ M < M_crit → Kármán-Tsien
   - M ≥ M_crit → marca como supercrítico (sin corrección aplicada)
3. Escribe `corrected_polar.csv` con columnas adicionales `cl_kt`, `cd_corrected`, `ld_kt`

### `stage3_compressibility_correction/prandtl_glauert.py` — 93 líneas

Implementa la corrección Prandtl-Glauert lineal:
`Cl_comp = Cl_incomp / sqrt(1 - M²)`

### `stage3_compressibility_correction/karman_tsien.py` — 156 líneas

Implementa la corrección Kármán-Tsien no lineal. Más precisa que P-G para M > 0.5.
Requiere iterar para encontrar el Cp corregido a partir del Cp incompresible.

### `stage3_compressibility_correction/critical_mach.py`

Estima M_crit mediante la regla de Kármán-Tsien: el M donde el flujo local
alcanza M=1 en el punto de mínimo Cp.

### `stage3_compressibility_correction/compressibility_case.py`

Dataclass `CompressibilityCase(flight, section, mach_target, polar_path)`

### `stage3_compressibility_correction/correction_result.py`

Dataclass `CorrectionResult(case, method_used, success, corrected_df, error_msg)`

---

## Stage 4 — Métricas de rendimiento

### `stage4_performance_metrics/metrics.py` — 428 líneas

Para cada caso (condición × sección):
1. Lee el polar corregido de Stage 3
2. Extrae `alpha_opt`, `Cl/Cd_max` (usando `find_second_peak_row`)
3. Calcula `eff_at_design_alpha` (Cl/Cd al α de crucero fijo)
4. Calcula `epsilon = Cl/Cd_max / Cl/Cd_design` (ratio de mejora VPF vs fijo)
5. Retorna lista de `PerformanceMetric` dataclasses

**Función principal:** `compute_all_metrics(polars_dir, conditions, sections) → List[PerformanceMetric]`

### `stage4_performance_metrics/table_generator.py`

Escribe `summary_table.csv` con todas las métricas en formato tabular:
columnas `flight_condition, blade_section, alpha_opt, max_efficiency, eff_at_design_alpha, epsilon`

### `stage4_performance_metrics/plots.py` — 829 líneas

Todas las figuras de Stage 4. Funciones principales:
- `generate_stage4_figures(metrics, figures_dir)` — polares básicos y eficiencia
- `generate_efficiency_plots(polars_dir, figures_dir)` — Cl/Cd vs α por caso
  con marcador en α_opt (usa `resolve_efficiency_column` + `find_second_peak_row`)
- `generate_efficiency_by_section(polars_dir, figures_dir)` — comparativa de secciones
  por condición de vuelo
- `generate_alpha_opt_vs_condition(metrics, figures_dir)` — α_opt per condición
- `generate_section_polar_comparison(polars_dir, figures_dir)` — overlay de polares
- `generate_cruise_penalty_figure(metrics, figures_dir)` — coste de pitch fijo

### `stage4_performance_metrics/narrative_figures.py` — 195 líneas

Dos figuras narrativas para la TFG:
- `generate_pitch_requirement_figure(pitch_map_csv, output_dir)` — panel doble:
  α_opt por condición (arriba) y Δβ_mech vs cruise (abajo) con banda de actuación
- `generate_fixed_vs_variable_figure(polars_dir, pitch_map_csv, output_dir)` —
  panel único: curvas Cl/Cd vs α para las 4 condiciones con marcadores VPF y
  línea de pitch fijo (diseño a crucero)

---

## Stage 5 — Cinemática de paso

### `stage5_pitch_kinematics/pitch_kinematics_core.py` — 854 líneas

Módulo de funciones puras (sin clases de servicio). Contiene toda la física de
Stage 5:

| Función | Descripción |
|---------|-------------|
| `compute_cascade_analysis(...)` | Análisis de cascada 2D: pérdidas de perfil, incidencia óptima, coeficientes de deflexión |
| `compute_rotational_corrections(...)` | Correcciones 3D por rotación (Coriolis, centrifugal pumping) |
| `compute_optimal_incidences(...)` | Incidencia óptima por sección y condición combinando cascade + correcciones 3D |
| `compute_pitch_adjustments(...)` | Δα relativo a condición de referencia (cruise) |
| `compute_blade_twist(...)` | Distribución de torsión radial de la pala |
| `compute_stage_loading(...)` | Coeficientes de carga Ψ y flujo Φ para diagrama φ-ψ (Dixon & Hall) |
| `compute_kinematics(...)` | Triángulos de velocidades: U, Va, W_rel, φ, β_metal por sección |

### `stage5_pitch_kinematics/application/run_pitch_kinematics.py` — 1320 líneas

Orquestador de Stage 5. Lee los polars de Stage 3, invoca las funciones de
`pitch_kinematics_core`, y escribe todos los CSVs y figuras del Stage 5.

**Outputs principales:**
- `tables/blade_twist_design.csv` — β_metal, twist acumulado por sección
- `tables/kinematics_analysis.csv` — triángulos de velocidades completos
- `tables/optimal_incidence.csv` — i_opt por sección y condición
- `tables/stage_loading.csv` — Ψ, Φ, eficiencia de etapa
- `figures/phi_psi_diagram.png` — diagrama de diseño de etapa
- `figures/velocity_triangles.png` — triángulos de velocidades
- `figures/blade_twist_profile.png` — distribución radial de torsión

### `stage5_pitch_kinematics/adapters/filesystem/data_loader.py`

Lee CSVs de Stage 3 (`corrected_polar.csv` por condición/sección) y los
carga como DataFrames para su uso en `run_pitch_kinematics.py`.

### `stage5_pitch_kinematics/adapters/filesystem/results_writer.py`

Escribe todos los CSVs y figuras de Stage 5 a disco.

### `stage5_pitch_kinematics/core/domain/pitch_kinematics_result.py` — 63 líneas

Dataclasses de resultados:
- `KinematicsSection` — triángulo de velocidades por sección
- `OptimalIncidenceResult` — i_opt + correcciones 3D
- `BladeSection` — geometría radial
- `StageLoadingResult` — Ψ, Φ, η_stage

---

## Stage 6 — Empuje inverso (teórico)

### `stage6_reverse_thrust/application/run_reverse_thrust.py` — 129 líneas

Análisis teórico del empuje inverso VPF. Sólo ejecuta el cálculo de peso del
mecanismo (sin BEM). Escribe el resumen con contexto bibliográfico explicando
por qué el análisis aerodinámico completo requeriría polares extendidos hasta
α ≈ -20°, fuera del rango XFOIL.

**Outputs:** `tables/mechanism_weight.csv`, `figures/mechanism_weight_comparison.png`,
`reverse_thrust_summary.txt`

### `stage6_reverse_thrust/reverse_thrust_core.py` — 313 líneas

Funciones puras (algunas no se usan en la ejecución actual, conservadas para
referencia futura):
- `compute_reverse_kinematics(...)` — triángulos de velocidades en modo inverso
- `compute_reverse_sweep(...)` — barrido BEM completo (requiere polares extendidos)
- `select_optimal_point(...)` — selección del punto óptimo del barrido
- `compute_mechanism_weight(...)` — **única función actualmente llamada**: calcula
  peso del actuador VPF vs reversor en cascada convencional y su impacto en SFC

### `stage6_reverse_thrust/adapters/filesystem/results_writer.py`

`ReverseResultsWriter` simplificado: sólo `write_mechanism_weight()` y
`write_figures()` (una figura de barras comparativa).

### `stage6_reverse_thrust/adapters/filesystem/data_loader.py`

`ReverseDataLoader`: carga blade twist de Stage 5 y polares de Stage 3 para
despegue. Actualmente no se usa (la orquestación teórica no necesita estos datos).

### `stage6_reverse_thrust/core/domain/reverse_thrust_result.py` — 101 líneas

Dataclasses de resultados del Stage 6:
- `MechanismWeightResult` — peso VPF, peso cascada, ahorro, impactos en SFC
- `ReverseKinematicsSection` — triángulo de velocidades por sección (reservado)
- `ReverseSweepPoint` — punto del barrido BEM (reservado)
- `ReverseOptimalResult` — punto óptimo del barrido (reservado)

---

## Stage 7 — Análisis de SFC

### `stage7_sfc_analysis/sfc_core.py` — 823 líneas

Motor de cálculo principal del análisis de SFC (modelo analítico original).

**Funciones principales:**
- `compute_bypass_sensitivity_factor(BPR)` → k = BPR/(1+BPR)
- `compute_propulsion_efficiency(v0, vj)` → η_prop = 2/(1 + Vj/V0)
- `compute_fan_efficiency_improvement(epsilon_values, η_fan_base, τ)` → Δη_fan
  donde ε = Cl/Cd_vpf / Cl/Cd_fixed y τ ∈ [0,1] es el coeficiente de transferencia
- `compute_sfc_analysis(metrics_df, engine_baseline, config_path, ...)` →
  `List[SfcAnalysisResult]` con reducción de SFC por condición
- `compute_sfc_sensitivity(...)` → barrido de τ para análisis de sensibilidad
- `compute_mission_fuel_burn(sfc_results, mission_profile)` → ahorro en kg combustible,
  CO₂ evitado, ahorro en USD

### `stage7_sfc_analysis/application/run_sfc_analysis.py` — 725 líneas

Orquestador de Stage 7. Pasos:
1. Carga `summary_table.csv` de Stage 4
2. Carga `engine_parameters.yaml`
3. `compute_sfc_analysis()` — modelo analítico
4. `compute_sfc_sensitivity()` — barrido τ
5. `compute_mission_fuel_burn()` — integración por fases de misión
6. Genera figuras (7 PNG)
7. Escribe tablas (4 CSV)
8. Escribe `sfc_analysis_summary.txt`
9. **Nuevo:** `run_ge9x_analysis()` — modelo termodinámico GE9X

**Outputs principales:**
- `tables/sfc_analysis.csv` — reducción SFC por condición
- `tables/sfc_section_breakdown.csv` — ε y Δη por sección
- `tables/sfc_sensitivity.csv` — barrido τ
- `tables/mission_fuel_burn.csv` — ahorro por fase
- `tables/ge9x_sfc_improvement.csv` — mejora GE9X (modelo nuevo)
- `tables/ge9x_sfc_parametric.csv` — barrido Cl/Cd ∈ [80, 150]
- `tables/ge9x_sfc_improvement.tex` — tabla LaTeX lista para publicar

### `stage7_sfc_analysis/core/domain/sfc_parameters.py` — 193 líneas

Dataclasses y constantes:
- `EngineBaseline(baseline_sfc, fan_efficiency, bypass_ratio)`
- `SfcSectionResult` — ε, Δη_fan, Δη por sección
- `SfcAnalysisResult` — reducción SFC por condición de vuelo
- `SfcSensitivityPoint` — punto del barrido τ
- `MissionFuelBurnResult` — ahorro por fase de misión
- `MissionSummary` — totales de misión
- Constantes de caps: `EPSILON_CAP`, `ETA_FAN_DELTA_CAP`, `ETA_FAN_ABS_CAP`, etc.

### `stage7_sfc_analysis/engine/engine_data.py` — 63 líneas

- `GE9X_PARAMS` — diccionario con los parámetros públicos del GE9X-105B1A
  (BPR=10, OPR=60, T4=1450 K crucero / 1800 K despegue, eficiencias, LHV)
- `_REFERENCE_ENGINES` — lista de motores similares (GE90, Trent XWB, PW1100G)
  para interpolación
- `estimate_GE9X_from_similar(engines)` — interpolación ponderada por OPR
- `sfc_lbh_to_si(x)`, `sfc_si_to_lbh(x)` — conversión de unidades

### `stage7_sfc_analysis/engine/turbofan_cycle.py` — 141 líneas

Ciclo termodinámico de dos flujos (cold + hot stream) basado en los parámetros
de `engine_data.py`. Implementa los 10 pasos del ciclo:

```
Admisión → Fan → Compresor → Combustión → HPT → LPT → Tobera caliente → Tobera fría → F_sp → SFC
```

**Función principal:** `compute_turbofan_sfc(params, phase, FPR) → dict`

**Validación:** SFC en crucero GE9X = 0.483 lb/lbf·h vs referencia pública 0.49 (delta -1.5%)

### `stage7_sfc_analysis/engine/sfc_model.py` — 61 líneas

Modelo de mejora de SFC por aumento de Cl/Cd:

**Hipótesis:** `F_required ∝ 1/(Cl/Cd)`. A mayor Cl/Cd, menor empuje requerido,
el motor opera a throttle parcial con ligera degradación de SFC pero menor
consumo másico neto.

**Función:** `compute_sfc_improvement(ClCd_ref, ClCd_new, SFC_design, k_throttle=0.08) → dict`

Parámetro `k_throttle` según Walsh & Fletcher (2004): degradación de SFC a
potencia parcial para turbofanes de alto BPR.

### `stage7_sfc_analysis/engine/ge9x_analysis.py` — 247 líneas

Análisis paramétrico completo GE9X:
1. Valida el ciclo termodinámico (debe convergir a ≈0.49 lb/lbf·h)
2. Carga `blade_pitch_map.csv` (Stage 2) y polares mid-span (Stage 2)
3. Extrae Cl/Cd en α_opt para cada condición de vuelo
4. Ejecuta barrido Cl/Cd ∈ [80, 150] con `compute_sfc_improvement()`
5. Genera tablas y figuras, incluyendo análisis de sensibilidad a `k_throttle`
6. Escribe tabla LaTeX `ge9x_sfc_improvement.tex`

**Resultado clave:** takeoff Cl/Cd ≈ 126 vs referencia fija ≈ 102 → **ahorro
de combustible ≈ 18%** al pitch optimizado (con k_throttle=0.08)

---

## Tests

### `tests/test_pipeline_contracts.py`

22 tests unitarios para los contratos `Stage4Result`…`Stage7Result`.
Verifica que `validate()` lanza `ValueError` ante inputs inválidos y pasa ante
inputs correctos. Usa `tmp_path` de pytest para crear directorios temporales.

### `tests/test_airfoil_selection.py`

Tests de la función de scoring: verifica que un polar sintético con Cl/Cd
elevado recibe mayor puntuación que uno degradado.

### `tests/test_efficiency.py`

Tests de `find_second_peak_row()` y `resolve_efficiency_column()`.
Verifica que el segundo pico se detecta correctamente en polares con burbuja
de separación laminar.

### `tests/test_prandtl_glauert.py`

Tests de la corrección Prandtl-Glauert: verifica amplificación en M=0.6,
ausencia de cambio en M=0, y que M≥1 lanza excepción.

### `tests/test_reynolds.py`

Tests de Reynolds: verifica que los valores cargados desde YAML están en el
rango físico esperado (1e5 – 2e7) para cada combinación condición/sección.

### `tests/test_airfoil_reader.py`

Tests del parser de ficheros `.dat` de perfiles NACA.

### `tests/conftest.py`

Fixtures compartidos: directorio de datos de test, polares sintéticos,
condiciones de vuelo de prueba.

---

## Flujo de datos entre etapas

```
config/analysis_config.yaml
config/engine_parameters.yaml
         │
         ▼
    Stage 1 ──── airfoil.dat ──────────────────────────────────────────────┐
         │                                                                  │
         ▼                                                                  │
    Stage 2 ──── stage2/polars/{cond}_{sec}.csv ──────────────────────────►│
         │        stage2/pitch_map/blade_pitch_map.csv ───────────────────►Stage 4 (narrativa)
         │                                                                  Stage 7 (GE9X)
         ▼
    Stage 3 ──── stage3/{cond}/{sec}/corrected_polar.csv ────────────────►Stage 5
         │                                                                  Stage 6 (no usado)
         ▼
    Stage 4 ──── stage4/tables/summary_table.csv ───────────────────────►Stage 7
         │        stage4/figures/*.png
         │
         ▼
    Stage 5 ──── stage5/tables/blade_twist_design.csv ──────────────────►Stage 6 (no usado)
         │        stage5/tables/kinematics_analysis.csv
         │
         ▼
    Stage 6 ──── stage6/tables/mechanism_weight.csv ────────────────────►Stage 7 (log)
         │
         ▼
    Stage 7 ──── stage7/tables/sfc_analysis.csv
                  stage7/tables/ge9x_sfc_improvement.tex
                  stage7/figures/*.png
```

---

## Parámetros físicos clave del modelo

| Parámetro | Valor | Fuente |
|-----------|-------|--------|
| Motor de referencia | GE9X-105B1A | Boeing 777X |
| BPR | 10.0 | GE Aviation spec |
| OPR | 60.0 | GE Aviation spec |
| SFC crucero | 0.49 lb/lbf·h | Dato público |
| Diámetro fan | 3.40 m | GE Aviation spec |
| Palas | 16 wide-chord composite | GE Aviation spec |
| r_root / r_mid / r_tip | 0.53 / 1.00 / 1.70 m | Geometría GE9X |
| Cuerda root/mid/tip | 0.36 / 0.46 / 0.46 m | Estimación |
| N1 diseño | ~2200 RPM | Derivado de U_mid=230 m/s |
| Mach relativo crucero (mid) | 0.93 | FL350, Va=150 m/s |
| τ (transferencia 2D→3D) | 0.50 | Ajuste calibrado |
| k_throttle | 0.08 | Walsh & Fletcher (2004) |

---

## Dependencias externas

```
numpy        — álgebra vectorial en todos los stages
pandas       — manejo de CSVs y DataFrames
matplotlib   — todas las figuras
scipy        — interpolación y optimización numérica (Stage 5, Stage 7)
rich         — consola con progress bars y tablas (run_analysis.py)
pyyaml       — lectura de YAMLs de configuración
XFOIL        — binario externo, invocado como subproceso
```

---

*Generado el 2026-04-25. Para actualizar: leer los ficheros fuente con `Read` y
revisar los cambios en `git log --oneline -20`.*
