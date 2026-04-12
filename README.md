# Variable Pitch Fan — Aerodynamic Analysis Pipeline

Pipeline en Python para el análisis aerodinámico completo de un fan de paso variable (VPF).
Cubre desde la selección del perfil NACA hasta la estimación de reducción de consumo específico de combustible (SFC), pasando por simulaciones XFOIL, correcciones de compresibilidad 3D, cinemática de pala con efectos de cascada y carga de etapa.

---

## Condiciones de vuelo y secciones de pala

| Condición | Número de Mach | Va [m/s] | Ncrit |
|-----------|----------------|-----------|-------|
| Cruise    | 0.85           | 250       | 5     |
| Takeoff   | ~0.53          | 180       | 9     |
| Climb     | ~0.65          | 220       | 7     |
| Descent   | ~0.59          | 200       | 7     |

| Sección   | Radio [m] | U [m/s] @ 4500 rpm | c [m] | σ    |
|-----------|-----------|--------------------|-------|------|
| Root      | 0.20      | 94.25              | 0.12  | ~1.7 |
| Mid-span  | 0.42      | 197.92             | 0.10  | ~0.8 |
| Tip       | 0.65      | 306.31             | 0.08  | ~0.4 |

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
│   ├── [B] Corrección rotacional 3D: Snel (ΔCL ∝ (c/r)²·CL_2D)
│   ├── [C] Twist de diseño + compromiso off-design (pérdida span-wise)
│   ├── [D] Carga de etapa: Euler, φ, ψ, W_spec
│   └── Triángulos de velocidad: Va → φ → β_mech, Δβ por condición
│
└── Stage 6 — Análisis de SFC
    └── η_fan,new = η_fan,base × (1 + τ·(ε−1))
        SFC_new  = SFC_base / (1 + Δη/η_base)
```

---

## Estructura de directorios

```
vpf/
├── config/
│   ├── analysis_config.yaml      # geometría del fan, condiciones, perfiles candidatos
│   └── engine_parameters.yaml    # η_fan base, SFC baseline, τ, sfc_multipliers
├── data/
│   └── airfoils/                 # archivos .dat de perfiles NACA
├── results/
│   ├── stage1_airfoil_selection/
│   ├── stage2_xfoil_simulations/
│   ├── stage3_compressibility_correction/
│   ├── stage4_performance_metrics/
│   ├── stage5_pitch_kinematics/
│   │   ├── figures/              # 14 figuras
│   │   └── tables/               # 7 tablas CSV
│   ├── stage6_sfc_analysis/
│   └── publication_figures/
├── src/vfp_analysis/
│   ├── settings.py               # PhysicsConstants, XfoilSettings, PipelineSettings
│   ├── config_loader.py          # lectura de YAML → estructuras tipadas
│   ├── validation/
│   │   └── validators.py         # file/dir/polar/physical range checks
│   ├── pipeline/
│   │   └── contracts.py          # Stage1Result … Stage6Result con validate()
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
│   │       ├── rotational_correction_service.py
│   │       ├── blade_twist_service.py
│   │       ├── stage_loading_service.py
│   │       ├── optimal_incidence_service.py
│   │       ├── pitch_adjustment_service.py
│   │       └── kinematics_service.py
│   └── stage6_sfc_analysis/
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

Parámetros geométricos y de simulación. Fuente de verdad única para el fan.

```yaml
fan:
  rpm: 4500
  r_root: 0.20      # [m]
  r_mid:  0.42
  r_tip:  0.65

blade_geometry:
  Z_blades:       18
  c_root:         0.12   # chord [m]
  c_mid:          0.10
  c_tip:          0.08
  theta_camber_deg: 8.0  # NACA 65-410

flight_conditions:
  cruise:  { mach: 0.85, Va: 250, ncrit: 5 }
  takeoff: { Va: 180,    ncrit: 9 }
  climb:   { Va: 220,    ncrit: 7 }
  descent: { Va: 200,    ncrit: 7 }

xfoil:
  alpha_start: -2.0
  alpha_end:   16.0
  alpha_step:   0.5
```

### `config/engine_parameters.yaml`

```yaml
fan_efficiency: 0.88          # η_fan base
baseline_sfc:   0.0185        # [kg/(N·h)]
profile_efficiency_transfer: 0.35   # τ — transferencia 2D→fan completo

sfc_multipliers:
  cruise:  1.00
  takeoff: 0.95
  climb:   0.97
  descent: 1.02
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

### Pipeline individual (Stage 5)

```bash
python -m vfp_analysis.stage5_pitch_kinematics.application.run_pitch_kinematics
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

#### D — Carga de etapa (Euler, φ, ψ)

```
φ(r)    = Va / U(r)                   — coeficiente de caudal
V_θ(r)  = U − Va / tan(β_mech_3D)    — velocidad tangencial impartida
ψ(r)    = V_θ / U                     — coeficiente de trabajo
W_spec  = U · V_θ   [J/kg]           — trabajo específico (ec. de Euler)
```

Zona de diseño fan alto bypass: φ ∈ [0.35, 0.55], ψ ∈ [0.25, 0.50]  [Dixon & Hall, cap. 5].

**Salidas Stage 5:**

| Tabla CSV | Contenido |
|-----------|-----------|
| `cascade_corrections.csv` | σ, s, K_weinig, δ_carter, CL_2D vs CL_cascade |
| `rotational_corrections.csv` | c/r, ΔCL_snel, α_opt_2D vs α_opt_3D, CL/CD_2D vs CL/CD_3D |
| `optimal_incidence.csv` | α_opt_3D por condición y sección |
| `pitch_adjustment.csv` | Δα_3D, Δβ_mech_3D |
| `blade_twist_design.csv` | β_metal(r), φ_flow(r), twist_from_tip |
| `off_design_incidence.csv` | α_actual, Δα_compromise, efficiency_loss_pct |
| `stage_loading.csv` | φ, ψ, W_spec, in_design_zone |

---

### Stage 6 — Análisis de SFC

Modelo de transferencia de eficiencia de perfil a fan completo:

```
ε             = CL_CD_vpf / CL_CD_cruise        — ratio de mejora
Δη_profile    = (ε − 1) · τ                     — ganancia de perfil amortiguada
η_fan,new     = η_fan,base · (1 + Δη_profile)   — nueva eficiencia de fan
SFC_new       = SFC_base / (1 + Δη_fan / η_fan,base)
ΔSFC [%]      = (SFC_base − SFC_new) / SFC_base · 100
```

`τ` (profile_efficiency_transfer) es el factor de atenuación 2D→3D, configurado en `engine_parameters.yaml`.

**Salida:** `stage6_sfc_analysis/tables/sfc_results.csv`

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
| 2 | polar.csv × 12 | efficiency_plot.png × 12, cl_alpha_stall.png × 12, polar_plot.png × 12 | — |
| 3 | corrected_polar.csv × 12 | comparison_2d_3d.png × 12 | — |
| 4 | metrics_summary.csv | metrics_heatmap.png, efficiency_gain.png | — |
| 5 | 7 CSV (ver tabla Stage 5) | 14 figuras | stage5_summary.txt |
| 6 | sfc_results.csv | sfc_reduction.png | sfc_summary.txt |

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
- Drela (1989): XFOIL — MIT, http://web.mit.edu/drela/Public/web/xfoil/
- ESDU 05017: *Profile Losses and Deviation in Axial Compressor and Fan Blade Rows*
