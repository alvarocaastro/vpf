# Variable Pitch Fan — Aerodynamic Analysis Pipeline

Pipeline en Python para el análisis aerodinámico completo de un fan de paso variable (VPF).
Cubre desde la selección del perfil NACA hasta la estimación de reducción de consumo específico de combustible (SFC), pasando por simulaciones XFOIL, correcciones de compresibilidad 3D, cinemática de pala con efectos de cascada y carga de etapa.

---

## Motor de referencia

Todos los parámetros geométricos y de operación replican un **GE9X (Boeing 777X)**: BPR≈10, fan de 3.40 m, 16 palas composite de cuerda ancha, RPM de diseño 2200.

## Condiciones de vuelo y secciones de pala

| Condición | M_rel @ mid-span | Va [m/s] | Ncrit |
|-----------|------------------|----------|-------|
| Takeoff   | 0.85             | 180      | 4.0   |
| Climb     | 0.85             | 155      | 4.0   |
| Cruise    | 0.93             | 150      | 4.0   |
| Descent   | 0.80             | 125      | 4.0   |

Va corresponde a la velocidad axial en la cara del fan (≠ velocidad de la aeronave). M_rel se evalúa en mid-span sobre la velocidad relativa W (Va + U), que es el Mach físicamente relevante para las correcciones de compresibilidad 2D.

| Sección   | Radio [m] | U [m/s] @ 2200 rpm | c [m] | σ    |
|-----------|-----------|--------------------|-------|------|
| Root      | 0.53      | 122.1              | 0.36  | 1.73 |
| Mid-span  | 1.00      | 230.4              | 0.46  | 1.17 |
| Tip       | 1.70      | 391.7              | 0.46  | 0.69 |

---

## Arquitectura del pipeline

```
run_analysis.py
│
├── Stage 1 — Selección de perfil
│   └── XFOIL @ Re_cruise, M_cruise → ranking CL/CD → NACA 65-410
│
├── Stage 2 — Simulaciones XFOIL finales
│   └── 12 polares (4 condiciones × 3 secciones)
│       retry automático (hasta 3 intentos), detección de convergencia
│
├── Stage 3 — Correcciones de compresibilidad
│   ├── Prandtl–Glauert: CL_PG = CL / √(1 − M²)
│   ├── Karman–Tsien:    CL_KT = CL / [β + (M²/2β)·CL/2]
│   └── Korn (onda):     M_dd estimado → penalización CD para M > M_dd
│
├── Stage 4 — Métricas de rendimiento
│   └── CL/CD_max, α_opt, CL_max, margen de stall, Δα VPF vs paso fijo
│
├── Stage 5 — Cinemática de pitch (análisis 3D de fan)
│   ├── [A] Corrección de cascada: Weinig (K_weinig) + Carter (δ_carter)
│   ├── [B] Corrección rotacional 3D: Snel (ΔCL ∝ (c/r)²·CL_2D), Du-Selig comparativo
│   ├── [C] Twist de diseño + compromiso off-design con actuador único
│   ├── [D] Carga de etapa dual: escenario ideal (α_opt_3D) vs escenario real (α_actual)
│   └── Triángulos de velocidad: Va → φ → β_mech, Δβ por condición
│
├── Stage 6 — Empuje inverso (reverse thrust)
│   ├── Barrido de pitch negativo: Δβ ∈ [−25°, −5°] a N1 = 65%
│   ├── Empuje reverso por sección y total; criterio de stall margin
│   └── Peso del mecanismo VPF vs inversor de cascada convencional
│
└── Stage 7 — Análisis de SFC y misión
    ├── ε(r, cond) = (CL/CD)_vpf / (CL/CD)_fixed_ref
    ├── Δη_fan = τ · (ε̄ − 1) · η_fan,base
    ├── SFC_new = SFC_base / (1 + Δη/η_base)
    └── Integración de misión: fuel burn por fase, sensibilidad a τ
```

---

## Estructura de directorios

```
vpf/
├── config/
│   ├── analysis_config.yaml      # geometría del fan, condiciones, Re, Ncrit
│   └── engine_parameters.yaml    # η_fan base, SFC baseline, τ, misión, reverse thrust
├── data/
│   └── airfoils/                 # archivos .dat de perfiles NACA
├── results/
│   ├── stage1_airfoil_selection/
│   ├── stage2_xfoil_simulations/
│   ├── stage3_compressibility_correction/
│   ├── stage4_performance_metrics/
│   ├── stage5_pitch_kinematics/
│   │   ├── figures/              # 20 figuras
│   │   └── tables/               # 10 tablas CSV
│   ├── stage6_reverse_thrust/
│   │   ├── figures/              # 4 figuras
│   │   └── tables/               # 4 tablas CSV
│   └── stage7_sfc_analysis/
│       ├── figures/              # 7 figuras
│       └── tables/               # 4 tablas CSV
├── src/vfp_analysis/
│   ├── settings.py               # PhysicsConstants, XfoilSettings, PipelineSettings
│   ├── config_loader.py          # lectura de YAML → estructuras tipadas
│   ├── validation/
│   │   └── validators.py         # file/dir/polar/physical range checks
│   ├── pipeline/
│   │   └── contracts.py          # StageNResult con validate()
│   ├── adapters/xfoil/           # XfoilRunnerAdapter, parser, port
│   ├── postprocessing/
│   │   ├── aerodynamics_utils.py
│   │   ├── publication_figures.py
│   │   └── stage_summary_generator.py
│   ├── shared/
│   │   └── plot_style.py         # apply_style() — Paul Tol colors
│   ├── stage1_airfoil_selection/
│   ├── stage2_xfoil_simulations/
│   ├── stage3_compressibility_correction/
│   ├── stage4_performance_metrics/
│   ├── stage5_pitch_kinematics/
│   │   ├── application/
│   │   │   └── run_pitch_kinematics.py
│   │   └── core/services/
│   │       ├── cascade_correction_service.py
│   │       ├── rotational_correction_service.py   # Snel + Du-Selig
│   │       ├── blade_twist_service.py              # twist + off-design α
│   │       ├── stage_loading_service.py            # φ, ψ, W_spec (agnóstico de α)
│   │       ├── optimal_incidence_service.py
│   │       ├── pitch_adjustment_service.py
│   │       └── kinematics_service.py
│   ├── stage6_reverse_thrust/
│   │   ├── application/run_reverse_thrust.py
│   │   └── core/services/
│   │       ├── reverse_kinematics_service.py
│   │       ├── reverse_thrust_service.py
│   │       └── mechanism_weight_service.py
│   └── stage7_sfc_analysis/
│       ├── application/run_sfc_analysis.py
│       └── core/services/
│           ├── propulsion_model_service.py
│           ├── sfc_analysis_service.py
│           ├── mission_analysis_service.py
│           └── summary_generator_service.py
├── tests/
└── run_analysis.py
```

---

## Requisitos e instalación

**Python 3.10+** y **XFOIL** instalado y accesible en el `PATH`.

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

Si XFOIL no está en el `PATH`:

```powershell
# Windows PowerShell
$env:XFOIL_EXE = "C:\ruta\a\xfoil.exe"
```

```bash
# Linux/macOS
export XFOIL_EXE="/opt/xfoil/xfoil"
```

---

## Configuración

### `config/analysis_config.yaml`

Geometría del fan (clase GE9X), condiciones de vuelo, Re por (fase, sección), Ncrit y ajustes de XFOIL.

```yaml
fan_geometry:
  rpm: 2200
  radius:      { root: 0.53, mid_span: 1.00, tip: 1.70 }   # [m]
  axial_velocity:
    takeoff: 180.0
    climb:   155.0
    cruise:  150.0
    descent: 125.0

blade_geometry:
  num_blades: 16
  chord:      { root: 0.36, mid_span: 0.46, tip: 0.46 }   # [m]
  theta_camber_deg: 8.0       # NACA 65-410

target_mach:                   # M_rel en mid-span (W/a)
  takeoff: 0.85
  climb:   0.85
  cruise:  0.93
  descent: 0.80

ncrit:                         # Tu ~0.5–1% en fan → Ncrit ≈ 4
  takeoff: 4.0
  climb:   4.0
  cruise:  4.0
  descent: 4.0

reynolds:                      # derivados de ρ·W·c/μ por condición ISA
  cruise:   { root: 1.8e6, mid_span: 3.2e6, tip: 5.0e6 }
  takeoff:  { root: 5.3e6, mid_span: 9.1e6, tip: 13.5e6 }
  climb:    { root: 3.4e6, mid_span: 6.0e6, tip: 9.1e6 }
  descent:  { root: 3.4e6, mid_span: 6.5e6, tip: 10.2e6 }

alpha:  { min: -5.0, max: 23.0, step: 0.15 }

airfoil_geometry:
  thickness_ratio: 0.10
  korn_kappa:      0.87        # NACA 6-series

xfoil:
  iter: 200
  timeout_final_s: 180.0
  max_retries: 3
```

### `config/engine_parameters.yaml`

```yaml
baseline_sfc:   0.50            # lb/(lbf·h) — GE9X
fan_efficiency: 0.90
bypass_ratio:  10.0
profile_efficiency_transfer: 0.50   # τ — fracción de ganancia 2D que llega al fan

sfc_multipliers:
  takeoff: 1.15
  climb:   1.05
  cruise:  1.00
  descent: 1.10

mission:
  phases:
    takeoff: { duration_min:   0.5, thrust_fraction: 1.00 }
    climb:   { duration_min:  20.0, thrust_fraction: 0.75 }
    cruise:  { duration_min: 480.0, thrust_fraction: 0.25 }
    descent: { duration_min:  25.0, thrust_fraction: 0.05 }
  design_thrust_kN: 105.0
  fuel_price_usd_per_kg: 0.90

reverse_thrust:
  n1_fraction: 0.65
  va_landing_m_s: 60.0
  delta_beta_min_deg: -25.0
  delta_beta_max_deg:  -5.0
  delta_beta_steps:    41
  target_thrust_fraction: 0.40
  engine_dry_weight_kg: 7930.0
  mechanism_weight_fraction:       0.04    # VPF actuator
  conventional_reverser_fraction:  0.10    # cascada convencional
  aircraft_L_D: 18.0
```

### `src/vfp_analysis/settings.py` — constantes físicas centralizadas

```python
from vfp_analysis.settings import get_settings

s = get_settings()
s.physics.CARTER_M_NACA6     # 0.23  — coeficiente de desviación de Carter (NACA 6-series)
s.physics.SNEL_A             # 3.0   — factor empírico de corrección rotacional (Snel 1994)
s.physics.ALPHA_MIN_OPT_DEG  # 3.0   — ángulo mínimo para búsqueda del óptimo
s.physics.CL_MIN_VIABLE      # 0.70  — CL mínimo para operación viable de pala de fan
s.xfoil.MAX_RETRIES          # 3     — reintentos automáticos por polar
s.xfoil.TIMEOUT_FINAL_S      # 180   — timeout Stage 2 [s]
```

---

## Ejecución

### Pipeline completo

```bash
python run_analysis.py
```

Al finalizar se imprime un resumen con las métricas clave de cada stage y los archivos generados.

### Pipelines individuales

```bash
python -m vfp_analysis.stage5_pitch_kinematics.application.run_pitch_kinematics
python -m vfp_analysis.stage6_reverse_thrust.application.run_reverse_thrust
python -m vfp_analysis.stage7_sfc_analysis.application.run_sfc_analysis
```

### Tests

```bash
pytest
pytest tests/test_metrics.py -v
pytest -k "cascade" -v
```

---

## Detalle técnico por stage

### Stage 1 — Selección de perfil

Ejecuta XFOIL a condición de crucero (M=0.85, Re_cruise) para cada perfil candidato definido en `analysis_config.yaml`. Selecciona el perfil con mayor CL/CD en el segundo pico (α ≥ `ALPHA_MIN_OPT_DEG`). Genera ranking y polar del ganador.

**Salida:** `stage1_airfoil_selection/selection/` — polar del perfil seleccionado, ranking CSV.

---

### Stage 2 — Simulaciones XFOIL finales

12 polares (4 condiciones × 3 secciones) usando el perfil seleccionado. Cada polar se ejecuta con retry automático:

```
for attempt in 0..MAX_RETRIES:
    run XFOIL → captura stdout
    check convergence (regex "Convergence failed")
    if success: break
    sleep(RETRY_WAIT_S)
```

Si XFOIL falla tras todos los intentos, se registra un aviso y el pipeline continúa con las polares disponibles. El parser detecta y registra problemas de calidad: `LOW_CL_MAX`, `NON_PHYSICAL_CD`, `HIGH_CD_MIN`, `NARROW_ALPHA_RANGE`, `NO_STALL_DETECTED`.

**Salida:** `stage2_xfoil_simulations/polars/` — 12 archivos `polar.dat` + `polar.csv`.

---

### Stage 3 — Correcciones de compresibilidad

Aplica tres niveles de corrección sobre los polares 2D de Stage 2:

| Corrección | Ecuación | Aplica a |
|------------|----------|----------|
| Prandtl–Glauert | `CL_PG = CL / √(1−M²)` | CL, CD, CM (M < 0.7) |
| Karman–Tsien | `CL_KT = CL_PG / [β + (M²/2β)·CL_PG/2]` | CL (M hasta ~0.8) |
| Korn (wave drag) | `M_dd ≈ κ/cos(Λ) − (t/c)/cos²(Λ) − CL/(10cos³(Λ))` | CD (M > M_dd) |

La corrección de onda de Korn añade CD_wave proporcional a `(M − M_dd)⁴` para capturar el onset de onda transónica.

**Salida:** `stage3_compressibility_correction/` — polares corregidos con columnas `cl_kt`, `cd_corrected`, `ld_kt`.

---

### Stage 4 — Métricas de rendimiento

Calcula para cada uno de los 12 casos:

- `CL/CD_max` (segundo pico, α ≥ α_min, CL ≥ CL_MIN_VIABLE)
- `α_opt` — ángulo en el máximo de eficiencia
- `CL_max` — sustentación máxima
- `stall_margin` — `α_stall − α_opt`
- `cm_at_opt` — momento de cabeceo en el punto óptimo
- `alpha_design`, `delta_alpha`, `eff_gain_pct` — beneficio del VPF vs paso fijo (referencia crucero)

**Salida:** `stage4_performance_metrics/tables/metrics_summary.csv`

---

### Stage 5 — Cinemática de pitch (análisis 3D de fan)

El módulo más completo. Opera en cuatro sub-análisis:

#### A — Corrección de cascada (Weinig + Carter)

El fan opera con palas en cascada, no como perfiles aislados. La solidez σ = c/s (s = 2πr/Z) determina la magnitud del efecto.

```
s(r)        = 2πr / Z
σ(r)        = c(r) / s(r)

K_weinig(σ) = (π/2·σ) / arctan(π·σ/2)   — factor de pendiente de CL
CL_cascade  = CL_2D · K_weinig

δ_carter(r) = m · θ / √σ(r)   — desviación de salida [°]
  m = 0.23  (NACA 6-series, a/c = 0.5)   [Carter 1950, NACA TN-2273]
```

Efecto en nuestra geometría: root (σ ≈ 1.7) → K_weinig ≈ 0.76; tip (σ ≈ 0.35) → K_weinig ≈ 0.97.

#### B — Correcciones rotacionales 3D (Snel)

La rotación crea fuerzas de Coriolis y gradientes centrífugos que incrementan CL y retrasan el stall, con efecto proporcional a (c/r)².

```
ΔCL_rot(r) = a · (c/r)² · CL_2D      a = 3.0  [Snel et al. 1994]
CL_3D      = CL_cascade + ΔCL_rot
CD_3D      ≈ CD_cascade               (corrección de drag < 2%, despreciable)
```

Magnitudes: root ≈ +8% CL, mid ≈ +1.7%, tip ≈ +0.5%.

#### C — Twist de diseño y compromiso off-design

Con un único actuador que gira toda la pala, solo una sección puede estar en su α_opt individual en cada condición. El análisis cuantifica la penalización:

```
φ_flow(r)   = arctan(Va / U(r))
β_metal(r)  = α_opt_3D_cruise(r) + φ_flow(r)   — ángulo mecánico de diseño
twist_total = β_metal(root) − β_metal(tip)       [°]

# Off-design:
α_actual(r, cond)       = β_metal(r) + Δβ_hub(cond) − φ_flow(r, cond)
Δα_compromise(r, cond)  = α_actual − α_opt_3D(r, cond)
loss_pct(r, cond)       = 1 − (CL/CD)[α_actual] / (CL/CD)_max_3D
```

#### D — Carga de etapa (Euler, φ, ψ) — escenario ideal vs real

```
φ(r)    = Va / U(r)                   — coeficiente de caudal
V_θ(r)  = U − Va / tan(β_mech_3D)    — velocidad tangencial impartida
ψ(r)    = V_θ / U                     — coeficiente de trabajo
W_spec  = U · V_θ   [J/kg]           — trabajo específico (ec. de Euler)
```

El análisis publica **dos tablas** para hacer explícito el trade-off del VPF:

- `stage_loading.csv` — escenario **ideal** (pitch libre por condición, α = α_opt_3D).
- `stage_loading_single_actuator.csv` — escenario **real** (un β_metal + un Δβ_hub por fase, α = α_actual).

Crucero y mid-span coinciden en ambos (hub_section optimizado, Δβ_hub=0 en la referencia). En root/tip fuera de crucero, el actuador único fuerza α por encima de α_opt → ψ mayor a costa de L/D.

**Nota sobre la zona de diseño Dixon & Hall** (φ ∈ [0.35, 0.55], ψ ∈ [0.25, 0.50]): está dimensionada para un fan de **paso fijo** que entrega PR≈1.7 (ψ_tip≈0.37) exigiendo α ≈ 6–10° con L/D≈7. El VPF opera en α_opt ≈ 1–3° con L/D ≈ 11–19: sacrifica ψ (menor turning por etapa) a cambio de eficiencia aerodinámica superior por sección. Los puntos VPF cayendo fuera de la zona no son un fallo — son la manifestación del valor del paso variable. El flag `in_design_zone` es informativo, no prescriptivo. La lectura física se detalla en el bloque [E] de `pitch_kinematics_summary.txt`.

**Salidas Stage 5:**

| Tabla CSV | Contenido |
|-----------|-----------|
| `cascade_corrections.csv` | σ, s, K_weinig, δ_carter, CL_2D vs CL_cascade |
| `rotational_corrections.csv` | c/r, ΔCL_snel, α_opt_2D vs α_opt_3D, CL/CD_2D vs CL/CD_3D |
| `rotational_corrections_du_selig.csv` | Modelo Du-Selig comparativo con Snel |
| `optimal_incidence.csv` | α_opt_3D por condición y sección |
| `pitch_adjustment.csv` | Δα_3D, Δβ_mech_3D |
| `blade_twist_design.csv` | β_metal(r), φ_flow(r), twist_from_tip |
| `off_design_incidence.csv` | α_actual, Δα_compromise, efficiency_loss_pct |
| `kinematics_analysis.csv` | Triángulos de velocidad Va/U/W/β por caso |
| `stage_loading.csv` | φ, ψ, W_spec, in_design_zone — **escenario ideal** |
| `stage_loading_single_actuator.csv` | Mismo layout — **escenario real (actuador único)** |

---

### Stage 6 — Empuje inverso (reverse thrust)

El VPF alcanza empuje inverso rotando el pitch de la pala a ángulos negativos **manteniendo la dirección de giro del fan**: no se necesitan puertas bloqueadoras ni cascadas de tobera como en un inversor convencional.

**Condiciones de operación durante el ground roll:**

- `N1_fraction = 0.65` (fan al 65% de su RPM de diseño)
- `Va_landing = 60 m/s` (promediado a lo largo del recorrido; reversers engaged ≈ 75 m/s)
- ρ = 1.225 kg/m³ (sea level)

**Barrido de pitch y criterio de optimización:**

```
Δβ ∈ [−25°, −5°], 41 puntos
Thrust_rev(r, Δβ) = ρ · Va · Ω · r · c · Z · (CL sin β − CD cos β)
Target: |Thrust_rev| ≥ 0.40 · Thrust_takeoff_forward, stall_margin ≥ 0
```

Los polares 3D de Stage 5 se re-evalúan a α negativo mediante extrapolación simétrica (el NACA 65-410 es no simétrico, pero la curva CL(α) mantiene pendiente lineal hasta el stall inverso). El servicio busca el Δβ óptimo que maximiza reverso manteniendo margen de stall positivo en las tres secciones.

**Comparación de peso del mecanismo:**

```
W_VPF,actuator  = 0.04 · W_dry_engine              — anillo + links + raíz reforzada
W_cascade_conv  = 0.10 · W_dry_engine              — cascadas + puertas + refuerzo de góndola
Δ fuel burn por ahorro de peso ≈ Δw / (L/D) · mission_range
```

**Salidas:** `stage6_reverse_thrust/` — 4 tablas (`reverse_thrust_sweep`, `reverse_thrust_optimal`, `reverse_kinematics`, `mechanism_weight`) y 4 figuras (`thrust_vs_pitch_sweep`, `efficiency_and_stall_margin`, `spanwise_thrust_at_optimum`, `mechanism_weight_comparison`).

---

### Stage 7 — Análisis de SFC y misión

Modelo de transferencia de eficiencia de perfil 2D a fan completo:

```
ε(r, cond)    = (CL/CD)_vpf(r, cond) / (CL/CD)_fixed_ref(r, cond)   — ratio de mejora
ε̄(cond)       = media radial ponderada de ε
Δη_fan(cond)  = τ · (ε̄ − 1) · η_fan,base             — ganancia amortiguada 2D→3D
η_fan,new     = η_fan,base + Δη_fan
SFC_new       = SFC_base / (1 + Δη_fan / η_fan,base)
ΔSFC [%]      = (SFC_base − SFC_new) / SFC_base · 100
```

`τ` (profile_efficiency_transfer ≈ 0.5) amortigua la ganancia 2D ideal para reflejar pérdidas 3D (tip clearance, secondary flows, shocks) no capturadas en el análisis de sección aislada.

**Referencia fixed-pitch:** se asume pitch óptimo para crucero (ε_cruise ≡ 1). En takeoff/climb/descent, ε refleja la ganancia genuina del VPF que reconfigura α a cada fase.

**Integración de misión:** se agregan fuel burn y coste por fase usando `thrust_fraction` y `duration_min` de `mission.phases`, y se calcula la sensibilidad a τ ∈ [0.3, 0.7].

**Salidas:** `stage7_sfc_analysis/` — 4 tablas (`sfc_analysis`, `sfc_section_breakdown`, `sfc_sensitivity`, `mission_fuel_burn`) y 7 figuras (`sfc_combined`, `fan_efficiency_improvement`, `fixed_vs_vpf_efficiency`, `epsilon_spanwise`, `sfc_sensitivity_tau`, `efficiency_mechanism_breakdown`, `mission_fuel_burn`). Stage 7 **no consume ψ** de Stage 5 — usa ε (ratios L/D) y φ, por lo que los valores bajos de ψ del VPF no propagan al SFC.

---

## Reglas de dependencia entre módulos

```
settings.py          ← todo el código (constantes físicas únicas)
config_loader.py     ← run_analysis.py, stages, services
validation/          ← adapters, postprocessing, run_analysis.py
pipeline/contracts.py← run_analysis.py (validación de contratos entre stages)
stage5/.../services/ ← run_pitch_kinematics.py (orquestador)
postprocessing/      ← run_analysis.py (figuras y resúmenes)
```

Ningún stage importa directamente de otro stage. La comunicación es exclusivamente a través de archivos en `results/` y los contratos `StageNResult`.

---

## Salidas del pipeline

| Stage | Tablas | Figuras | Texto |
|-------|--------|---------|-------|
| 1 | ranking.csv, best_airfoil.csv | polar_best.png | selection_summary.txt |
| 2 | polar.csv × 12 | efficiency, cl_alpha_stall, polar × 12 | — |
| 3 | corrected_polar.csv × 12 | comparison_2d_3d × 12 | — |
| 4 | metrics_summary.csv | metrics_heatmap, efficiency_gain | — |
| 5 | 10 CSV (ver tabla Stage 5) | 20 figuras | pitch_kinematics_summary.txt, finalresults_stage5.txt |
| 6 | 4 CSV (reverse_thrust_*) | 4 figuras | reverse_thrust_summary.txt |
| 7 | 4 CSV (sfc_*, mission_*) | 7 figuras | sfc_analysis_summary.txt, finalresults_stage7.txt |

---

## Constantes físicas y referencias

| Símbolo | Valor | Descripción | Referencia |
|---------|-------|-------------|------------|
| m (Carter) | 0.23 | Coef. de desviación de cascada (NACA 6-series, a/c=0.5) | Carter (1950), NACA TN-2273 |
| a (Snel) | 3.0 | Factor empírico de corrección rotacional (flujo adherido) | Snel et al. (1994) |
| α_min_opt | 3.0° | Ángulo mínimo para búsqueda del segundo pico CL/CD | Calibrado con XFOIL NACA 6-series |
| CL_min_viable | 0.70 | CL mínimo para operación de pala de fan | Rango típico fan: CL ∈ [0.7, 1.2] |
| CL_max_fan | 0.96 | Límite de eficiencia de fan (cap physical) | Cumpsty (2004) |
| φ_design | [0.35, 0.55] | Coef. de caudal en zona de diseño | Dixon & Hall (2013), cap. 5 |
| ψ_design | [0.25, 0.50] | Coef. de trabajo en zona de diseño | Dixon & Hall (2013), cap. 5 |

**Bibliografía principal:**
- Dixon & Hall (2013): *Fluid Mechanics and Thermodynamics of Turbomachinery*, 7ª ed.
- Cumpsty (2004): *Compressor Aerodynamics*
- Saravanamuttoo et al. (2017): *Gas Turbine Theory*, 6ª ed.
- Carter (1950): *The Low Speed Performance of Related Aerofoils in Cascade*, NACA TN-2273
- Snel, Houwink & Bosschers (1994): *Sectional Prediction of Lift Coefficients on Rotating Wind Turbine Blades*
- Du & Selig (1998): *A 3-D Stall-Delay Model for Horizontal Axis Wind Turbine Performance Prediction*, AIAA 98-0021
- Drela (1989): XFOIL — MIT, http://web.mit.edu/drela/Public/web/xfoil/
- ESDU 05017: *Profile Losses and Deviation in Axial Compressor and Fan Blade Rows*
