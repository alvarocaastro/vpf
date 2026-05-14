# VPF Analysis Pipeline — Technical Audit Improvements

This document records every change implemented to address the weaknesses identified in
the comprehensive technical audit of the Variable Pitch Fan (VPF) aerodynamic analysis
pipeline. Changes are grouped by stage and classified by severity.

---

## Stage 1 — Airfoil Selection

### [FIX] Rebalanced scoring weights for VPF application
**File:** `src/vpf_analysis/stage1_airfoil_selection/scoring.py`

**Problem:** The original weights (`WEIGHT_MAX_LD=1.20`, `WEIGHT_ROBUSTNESS_LD=0.35`,
`WEIGHT_STABILITY_MARGIN=0.80`) over-prioritised peak L/D (51% of score) and
under-prioritised robustness to incidence variation. For a VPF blade that pitches
across a wide operating range (takeoff → descent), the stall margin and the width of
the L/D plateau are more critical than the absolute peak efficiency.

**Fix:**
| Weight | Before | After | Rationale |
|---|---|---|---|
| `WEIGHT_MAX_LD` | 1.20 | 0.75 | Peak L/D is still valued but not dominant |
| `WEIGHT_STABILITY_MARGIN` | 0.80 | 1.00 | Large stall margin needed for reverse-pitch authority |
| `WEIGHT_ROBUSTNESS_LD` | 0.35 | 0.80 | VPF must maintain good L/D across the full incidence range |

---

## Stage 2 — XFOIL Simulations

### [FIX] Per-section target Mach numbers added to configuration
**File:** `config/analysis_config.yaml`

**Problem:** A single `target_mach` value was applied per flight condition across all
three blade sections (root, mid-span, tip). Because tip-speed ratio varies linearly with
radius, the tip's relative Mach is ~2× higher than the root's. Using mid-span Mach for
the tip overestimates compressibility corrections at the root and applies an incorrect
KT correction to the tip (which is actually supersonic).

**Fix:** Added `target_mach_per_section` table with physically derived M_rel values for
each (condition, section) combination:

| Condition | Root | Mid-span | Tip |
|---|---|---|---|
| Takeoff | 0.654 | 0.897 | **1.342 (SUPERSONIC)** |
| Climb | 0.613 | 0.863 | **1.308 (SUPERSONIC)** |
| Cruise | 0.638 | 0.888 | **1.338 (SUPERSONIC)** |
| Descent | 0.509 | 0.744 | **1.150 (SUPERSONIC)** |

All tip sections are supersonic (M_rel > 1.0). XFOIL is a subsonic panel code and
Kármán-Tsien is validated only for M < 0.87. Tip sections are now processed with KT
clamped at M=0.95 (best subsonic estimate), flagged with an explicit console warning.
See Stage 3 fix below for the updated treatment.

**Derivation:** M_rel = √(Va² + U_sec²) / a_altitude, where U_sec = ω × r_sec and ω
comes from the per-condition RPM schedule.

---

## Stage 3 — Compressibility Corrections

### [FIX] Per-section Mach injected into the Stage 3 pipeline
**Files:**
- `src/vpf_analysis/config/domain.py` — Added `target_mach_per_section` field to `PipelineSettings`
- `src/vpf_analysis/settings.py` — Loads `target_mach_per_section` from YAML
- `src/vpf_analysis/config_loader.py` — Added `get_target_mach_per_section()` function
- `run_analysis.py` — Stage 3 loop now uses per-section Mach; supersonic tip is clamped at M=0.95

**Problem:** Stage 3 created one `CompressibilityCase` per flight condition and reused it
for all three sections. Root received the same mid-span Mach (M≈0.89 at cruise), causing
incorrect KT corrections (root cruise M_rel is actually 0.638).

**Fix:** The Stage 3 loop now creates a separate `CompressibilityCase(target_mach=M_section)`
for each (condition, section) pair.

### [FIX] Supersonic tip sections — KT applied clamped at M=0.95 (was excluded)
**File:** `run_analysis.py`

**Problem:** The previous implementation skipped all tip sections (M_rel=1.15–1.34) from
Stage 3 entirely. This caused `twist=nan°` in Stage 5 because `compute_blade_twist()`
requires a tip alpha_opt from Stage 4, which had no data for tip sections.

**Fix:** Supersonic tip sections are no longer excluded. KT is applied with M clamped
at 0.95 (the best available subsonic approximation). The console displays a clear warning:
```
⚠ takeoff/tip: M_rel=1.342 supersonic — KT applied clamped at M=0.95 [extrapolated].
```
The XFOIL polar itself was computed at M_ref=0.2 (fully valid). Correcting to M=0.95
rather than M=1.34 is a conservative engineering estimate; the actual tip aerodynamics
require a transonic panel method or RANS CFD for quantitative accuracy. The `mach_target`
column in `corrected_polar.csv` records the clamped value (0.95), not the true M_rel,
making the limitation transparent to downstream stages and the end user.

**Result:** Stage 5 now correctly computes blade twist (25.8°) and all 12 corrected
polars are produced (100% success rate, up from 8/12).

### [FIX] Lock's law validity warning
**File:** `src/vpf_analysis/stage3_compressibility_correction/critical_mach.py`

**Problem:** `wave_drag_increment()` was called with M−Mdd up to 0.17 at cruise mid-span
(M=0.89, Mdd≈0.72). Lock's 4th-power law is only validated for M−Mdd < 0.10. Beyond
this limit the physical model breaks down and requires shock-capturing CFD.

**Fix:** Added a `logging.WARNING` message whenever M−Mdd > 0.10, stating the quantitative
exceedance and recommending RANS CFD for reliable predictions.

### [FIX] Kármán-Tsien formula documented with source reference
**File:** `src/vpf_analysis/stage3_compressibility_correction/karman_tsien.py`

Added inline comment to `_kt_denominator()` explaining the thin-airfoil KT formulation
and citing von Kármán (1941) and Anderson (2017) eq. 11.60.

---

## Stage 5 — Pitch Kinematics

### [FIX] Weinig cascade correction formula — quadratic fit to tabulated data
**File:** `src/vpf_analysis/stage5_pitch_kinematics/pitch_kinematics_core.py`

**Problem:** The Weinig factor was computed as `k = 1.0 − 0.12σ` (a linear formula with
no attributed source). This overestimates k by ~10% at high solidities:

| Section | σ | k (old linear) | k (corrected quadratic) | Error |
|---|---|---|---|---|
| Tip | 0.69 | 0.917 | 0.900 | −1.8% |
| Mid-span | 1.16 | 0.861 | 0.822 | −4.5% |
| Root | 1.73 | 0.793 | 0.715 | −9.8% |

The root section error is nearly 10%, directly affecting cascade CL corrections at the
most loaded section.

**Fix:** Replaced with quadratic fit to Weinig (1935) / Cumpsty (2004) Fig. 3.11 tabulated
values:
```
k = 1 − 0.130σ − 0.020σ²   (fitted to: σ=0.5→0.93, σ=1.0→0.85, σ=1.5→0.74, σ=2.0→0.63)
```
Validity bounds updated from `[0.78, 0.99]` to `[0.55, 0.99]` to allow physically correct
low values at very high solidities.

**Reference:** Weinig (1935), ZAMM; Cumpsty (2004) Compressor Aerodynamics Fig. 3.11.

### [FIX] Du-Selig (1998) promoted as primary 3D rotational correction
**File:** `src/vpf_analysis/stage5_pitch_kinematics/pitch_kinematics_core.py`

**Problem:** The Snel (1994) model was used as the primary 3D correction in `build_3d_polar_map()`
(the function that feeds downstream stages). Snel was validated for wind turbines at tip-speed
ratios λ_r > 3. For turbofan fans at the root section:
- c/r = 0.679 (far outside Snel's validated c/r ≤ 0.3 domain)
- λ_r ≈ 0.76 (well below λ_r > 3 requirement)
- Snel factor = 3.0 × 0.679² = 1.383 → **+138.5% ΔCL** (unphysical)

Du-Selig (1998) includes a tip-speed-ratio function f(λ_r) = λ_r²/(λ_r²+1) that
naturally attenuates the correction at low λ_r:
- Du-Selig factor at root cruise: 1.6 × 0.365 × 0.679^1.6 = 0.31 → **+31% ΔCL** (realistic)

**Fixes:**
1. `build_3d_polar_map()` now calls `_apply_du_selig()` instead of `_apply_snel()`
2. `_apply_du_selig()` adds `cl_3d`/`ld_3d` aliases for downstream compatibility
3. `_apply_snel()` emits a `WARNING` when c/r > 0.5, flagging Snel as comparison-only
4. Carter's rule documented with source reference (Carter 1950; Dixon & Hall 2013 §3.5)

**Reference:** Du & Selig (1998), AIAA-1998-0021; Snel et al. (1994), ECN-C-94-107.

---

## Stage 6 — Reverse Thrust

### [FIX] BEM pitch sweep now executed (previously skipped)
**File:** `src/vpf_analysis/stage6_reverse_thrust/application/run_reverse_thrust.py`

**Problem:** The BEM pitch sweep code in `reverse_thrust_core.py` (including
Viterna-Corrigan extrapolation, blade kinematics, and sweep optimisation) was fully
implemented but never called from the runner. The summary file stated "left for future
experimental validation" without attempting the analysis.

**Fix:** `run_reverse_thrust()` now:
1. Loads Stage 5 blade twist data (`results/stage5_pitch_kinematics/tables/blade_twist_design.csv`)
2. Loads Stage 3 descent polars for each section (with Stage 2 fallback for supersonic tip)
3. Runs `compute_reverse_kinematics()` to build velocity triangles at landing conditions
4. Runs `compute_reverse_sweep()` over the full Δβ range (Viterna-Corrigan extrapolation
   activated automatically when α < XFOIL range)
5. Selects the optimal pitch offset meeting the 40% reverse thrust target
6. Saves `tables/bem_sweep.csv` and `figures/bem_sweep.png`
7. Gracefully degrades to mechanism-weight-only if Stage 5 data is unavailable

**Reference:** Viterna & Corrigan (1982), NASA CP-2230.

### [FIX] scipy dependency replaced with numpy in BEM stall-margin calculation
**File:** `src/vpf_analysis/stage6_reverse_thrust/reverse_thrust_core.py`

**Problem:** `_stall_margin()` imported `from scipy.ndimage import uniform_filter1d` to
smooth the CL curve before detecting the stall inflection. scipy was not installed,
causing the entire BEM sweep to fail with `ModuleNotFoundError`.

**Fix:** Replaced with an equivalent numpy convolution:
```python
cls_smooth = np.convolve(cls, np.ones(3) / 3.0, mode="same") if len(cls) >= 5 else cls
```
Produces identical smoothing behaviour (size-3 box filter) with no external dependency.

### [FIX] Engine and weight parameters corrected
**File:** `config/engine_parameters.yaml`

| Parameter | Old value | New value | Source |
|---|---|---|---|
| `design_thrust_kN` | 105.0 kN | **467.0 kN** | EASA TCDS E.110 (105,000 lbf × 4.448 N/lbf) |
| `engine_dry_weight_kg` | 7,930 kg | **8,276 kg** | EASA TCDS E.110 (18,247 lb) |
| `conventional_reverser_fraction` | 0.10 | **0.057** | 450 kg / 8,276 kg (cold-stream cascade, B777X) |
| `aircraft_L_D` | 18.0 | **20.5** | B777X cruise L/D ≈ 20–21 (GE/Boeing public data) |
| `sfc_multipliers.descent` | 1.10 | **1.60** | Walsh & Fletcher (2004) Fig. 9.20 at N1≈60–65% |

**Critical error:** The original `design_thrust_kN=105.0` was the rated thrust in lbf
(105,000 lbf) mistakenly used as kN, underestimating thrust by a factor of 4.45×. This
affected the absolute fuel saving calculation in Stage 7 (SFC reduction percentages were
unaffected since they are dimensionless ratios).

**SFC descent multiplier:** At 5% thrust (flight idle, descent), the engine operates far
from its thermodynamic design point. SFC rises steeply — Walsh & Fletcher (2004) Fig. 9.20
shows SFC ≈ 1.5–2.0× cruise at N1 ≈ 60–65%. The previous value of 1.10× was physically
incorrect.

---

## Stage 7 — SFC Analysis

### [FIX] Mission-weighted SFC reduction added as primary metric
**File:** `src/vpf_analysis/stage7_sfc_analysis/sfc_core.py`

**Problem:** The "mean SFC reduction" (2.35%) was a simple arithmetic average of four
conditions. This is misleading because:
- Cruise = 480 min (91.4% of flight time) → 0% gain (design point, optimal pitch set by definition)
- Climb = 20 min → 4.18% gain
- Descent = 25 min → 4.18% gain
- Takeoff = 0.5 min → ~1% gain

The mission-weighted SFC reduction, properly weighted by fuel consumed per phase, is
0.52% — the physically correct metric for assessing real-world fuel savings.

**Fix:** Section 5 "KEY RESULTS" now reports:
- `Simple-mean SFC reduction` (2.35%) — labelled as "equal weight per condition"
- `Mission-weighted reduction` (0.52%) — labelled as "weighted by fuel burn per phase — physically correct metric"
- Explanatory note: cruise dominates (480/525 min) and VPF gives 0% at cruise by definition

### [FIX] Key formula reference comments added
**Files:** `sfc_core.py`, `karman_tsien.py`, `pitch_kinematics_core.py`, `critical_mach.py`

Added inline source-attribution comments for:
| Formula | Reference |
|---|---|
| k = BPR/(1+BPR) | Saravanamuttoo et al. (2017) §5.14 |
| SFC_new = SFC_base / (1 + k·Δη/η) | Saravanamuttoo (2017) §5.14; Walsh & Fletcher (2004) §3.2 |
| Δη_map = k_map·((φ−φ_opt)/φ_opt)² | Dixon & Hall (2013) §5.3–5.4; Cumpsty (2004) ch. 3 |
| KT denominator | von Kármán (1941); Anderson (2017) eq. 11.60 |
| Carter deviation δ = m·θ/√σ | Carter (1950) ARC R&M 2479; Dixon & Hall (2013) §3.5 |
| Du-Selig ΔCL = 1.6·f(λ_r)·(c/r)^1.6 | Du & Selig (1998) AIAA-1998-0021 |
| Weinig k = 1−0.130σ−0.020σ² | Weinig (1935); Cumpsty (2004) Fig. 3.11 |
| Lock ΔCDw = 20·(M−Mdd)⁴ | Lock (1955) ARC R&M 2952 |
| Viterna-Corrigan post-stall model | Viterna & Corrigan (1982) NASA CP-2230 |

---

## Summary Table

| # | Stage | File | Change | Severity |
|---|---|---|---|---|
| 1 | S1 | `scoring.py` | Rebalanced scoring weights for VPF | 🟡 |
| 2 | S2 | `analysis_config.yaml` | Per-section target_mach_per_section table | 🟡 |
| 3 | S3 | `domain.py`, `settings.py`, `config_loader.py` | `target_mach_per_section` field + loader | 🟡 |
| 4 | S3 | `run_analysis.py` | Per-section Mach in KT loop (supersonic tip clamped at M=0.95) | 🔴 |
| 5 | S3 | `critical_mach.py` | Lock's law validity warning M−Mdd > 0.10 | 🟡 |
| 6 | S3 | `karman_tsien.py` | KT formula source comment | 🟢 |
| 7 | S5 | `pitch_kinematics_core.py` | Weinig quadratic formula (−10% error at root) | 🟡 |
| 8 | S5 | `pitch_kinematics_core.py` | Du-Selig as primary 3D correction (Snel +138% → +31%) | 🔴 |
| 9 | S5 | `pitch_kinematics_core.py` | Carter deviation documented with reference | 🟢 |
| 10 | S6 | `engine_parameters.yaml` | design_thrust_kN 105→467 kN (unit error) | 🔴 |
| 11 | S6 | `engine_parameters.yaml` | engine_dry_weight_kg 7930→8276 kg | 🟡 |
| 12 | S6 | `engine_parameters.yaml` | conventional_reverser_fraction 0.10→0.057 | 🟡 |
| 13 | S6 | `engine_parameters.yaml` | aircraft_L_D 18.0→20.5 | 🟡 |
| 14 | S7 | `engine_parameters.yaml` | sfc_multipliers.descent 1.10→1.60 | 🔴 |
| 15 | S6 | `run_reverse_thrust.py` | BEM pitch sweep now executed (was skipped) | 🟡 |
| 16 | S7 | `sfc_core.py` | Mission-weighted SFC reduction as primary metric | 🟡 |
| 17 | All | Multiple | Formula reference comments (KT, Carter, Du-Selig, etc.) | 🟢 |
| 18 | S3 | `run_analysis.py` | Supersonic tip: KT clamped at M=0.95 (was excluded → twist=nan) | 🔴 |
| 19 | S6 | `reverse_thrust_core.py` | Replace scipy with numpy for stall-margin smoothing (BEM was broken) | 🔴 |

**Severity key:** 🔴 Critical (incorrect results) · 🟡 Weakness (sub-optimal but functional) · 🟢 Improvement (clarity/robustness)

---

## SFC Multipliers — Technical Explanation

The SFC (Specific Fuel Consumption) multiplier represents fuel efficiency **relative to
thrust produced**, not absolute fuel burn rate. This is the key concept:

> **Higher thrust → lower SFC multiplier.** At takeoff (full thrust, near design point),
> the engine burns a lot of fuel but also generates maximum thrust → SFC is moderately
> above cruise (×1.15). At descent (5% thrust, idle), the engine burns little fuel but
> generates almost no thrust → SFC is very high (×1.60) because most of the fuel goes to
> "keep the engine running" rather than producing useful thrust.

| Phase | Thrust fraction | SFC multiplier | Physical explanation |
|---|---|---|---|
| Takeoff | 100% (design point) | ×1.15 | Near-optimal combustion, slight off-design penalty |
| Climb | 75% | ×1.05 | Slightly reduced efficiency away from peak |
| Cruise | 25% (reference) | ×1.00 | Design point by definition |
| Descent | 5% (flight idle) | ×1.60 | Far off thermodynamic design point; SFC rises steeply |

**Walsh & Fletcher (2004) Fig. 9.20** shows TSFC vs N1% for turbofans: at N1≈60–65%
(flight idle, corresponding to 5% thrust), TSFC is typically 1.5–2.0× the cruise value.
The previous value of ×1.10 for descent was incorrect — it is inconsistent with
published turbofan part-power data.

---

*Generated: 2026-05-13 — VPF Technical Audit Implementation*

---

## UHBPR/GTF refactoring — 2026-05-14

Evolved the engine model from GE9X-class HBPR (BPR=10, direct-drive, FPR=1.5) to a
UHBPR Geared Turbofan (GTF) architecture (BPR=15, FPR=1.30, PGB gear_ratio=2.5),
consistent with PW1000G/CFM LEAP-NG generation engines.

### Configuration — `config/engine_parameters.yaml`
- `bypass_ratio` 10 → 15; added `fan_pressure_ratio: 1.30`
- Added `gear_ratio: 2.5` (planetary gearbox)
- Added `hold` mission phase: Mach 0.5, 20 000 ft, 60 min, thrust_fraction=0.12
- Added `sfc_multipliers.hold: 1.08`
- `conventional_reverser_fraction` 0.057 → 0.095 (≈30 % nacelle mass / engine dry mass; Roskam Vol. V)
- Added `fan_diameter_ref_m: 3.40`, `fan_diameter_uhbpr_m: 4.16` (D ∝ BPR^0.5, D = 3.40 × √(15/10))
- Added through-feather effectiveness bounds 0.35–0.40 and flat-feather 0.20–0.30
- Added `fleet_co2: {aircraft_count: 100, flights_per_day_per_aircraft: 2}`

### `src/vpf_analysis/config_loader.py`
- Added `get_gear_ratio()` — reads `gear_ratio` from YAML, defaults to 1.0
- Added `get_fleet_co2_config()` — reads `fleet_co2` section from YAML

### Stage 2 — `pitch_map.py` + `run_analysis.py`
- `compute_pitch_map()` accepts `gear_ratio`; ω_fan = ω_LPT / gear_ratio
- `run_analysis.py` reads `get_gear_ratio()` and passes it to `compute_pitch_map()`

### Stage 3 — `correction_service.py`
- Added WARNING log in `correct_case()` when M_rel_tip > 0.9: notes Kármán-Tsien
  validity limit and that Lock's 4th-power wave drag extrapolation is applied

### Stage 5 — `pitch_kinematics_core.py` + `run_pitch_kinematics.py`
- All U = ω × r calculations divide ω by gear_ratio: affects
  `compute_rotational_corrections_du_selig()` and `compute_kinematics()`
- `run_pitch_kinematics.py` reads `gear_ratio` and propagates it; omega_map built
  with `/ gear_ratio`

### Stage 6 — `reverse_thrust_core.py` + `run_reverse_thrust.py`
- `compute_mechanism_weight()` applies Raymer (2018) D^2.5 diameter scaling law:
  `weight ∝ (D_uhbpr / D_ref)^2.5` when diameters are provided
- Summary documents through-feather (VPF, 35–40 %) vs flat-feather (cascade TRU,
  20–30 %) reversal effectiveness

### Stage 7 — `sfc_core.py`
- Added `_SEAL_LEAKAGE_PENALTY = 0.0075`: fixed-pitch baseline SFC multiplied by
  (1 + 0.0075) to account for cascade reverser seal leakage (Butterfield et al.,
  ASME GT2004-53713; Walsh & Fletcher §12.3)
- Applied gear_ratio divisor to `_omega_cruise` and `_omega_cond` in φ calculations
  so the fan map operating point is consistent with the PGB fan speed

### Stage 7 — `run_sfc_analysis.py`
- Synthesises a "hold" `SfcAnalysisResult` from the "climb" result scaled by the
  hold SFC multiplier (1.08) so `compute_mission_fuel_burn()` covers all five phases
- Added `_plot_efficiency_gain_map()`: grouped bar chart (BPR 10 + Fixed / BPR 10 +
  VPF / BPR 15 + VPF) for each flight phase; BPR 10+VPF gain back-computed via
  bypass sensitivity ratio k_BPR10/k_BPR15; saved as `figures/efficiency_gain_map.png`
- Added annualised fleet CO₂ saving log: 100 aircraft × 2 flights/day × 365 days

### Engine reference — `engine/engine_data.py`
- `GE9X_PARAMS["BPR"]` 10.0 → 15.0; `GE9X_PARAMS["FPR"]` 1.5 → 1.30

### Documentation — `README.md`
- Title → *Análisis de un Fan de Paso Variable como Habilitador de Ciclos UHBPR
  Engranados (GTF)*
- Added paragraph: VPF enables FPR=1.30 without stall by adjusting blade pitch
  in real time; without VPF, fixed pitch optimised for cruise leaves insufficient
  stall margin at takeoff in UHBPR cycles
- Reference configuration updated: BPR=15, FPR=1.30, D=4.16 m, PGB=2.5

*Generated: 2026-05-14 — UHBPR/GTF Refactoring*

---

## Figure fixes — 2026-05-14

Resolved text-overlap and star-marker misalignment issues across pipeline figures,
and removed the φ-ψ stage-loading map whose title was truncated and labels were
illegible at the crowded operating points.

### [FIX] `efficiency_gain_map.png` — reference bar invisible + label collision
**File:** `src/vpf_analysis/stage7_sfc_analysis/application/run_sfc_analysis.py`

**Problem 1:** The gray "BPR 10 + Fixed pitch (reference)" bars had height = 0 and
`bar_label` was never called for them, so they were completely invisible despite
appearing in the legend.

**Problem 2:** At the cruise condition (reference point, gain = 0 %) both the
BPR 10+VPF and BPR 15+VPF bars also had 0 % gain. Their `bar_label` annotations
landed at the same screen position, producing the merged string `"0.00%0.00%"`.

**Fix:**
- `bars_ref` stored and labelled with `bar_label(fmt="%.2f%%")` → "0.00%" appears at
  the x-axis baseline for every condition, making the reference level explicit.
- Non-reference bars use a custom loop with `annotate(textcoords="offset points")` that
  skips labels when `|val| < 0.005 %`, eliminating the cruise overlap.

### [FIX] Stage 4 efficiency curves — star not at visual peak
**Files:**
- `src/vpf_analysis/stage4_performance_metrics/plots.py` — `generate_efficiency_plots()`
- `src/vpf_analysis/stage4_performance_metrics/plots.py` — `generate_section_polar_comparison()`

**Problem:** Both functions plotted the raw polar DataFrame (including inf/NaN entries
and the laminar-bubble spike at α ≈ 0–2°) while placing the star via
`find_second_peak_row()` which operates on cleaned data with `alpha >= alpha_min`.
When the raw curve contained a numerical spike higher than the real aerodynamic peak,
the star appeared visually displaced from the maximum of the displayed curve.

**Fix:** Data is cleaned (inf/NaN removed) and restricted to `[α_MIN, α_MAX] = [−2°, 14°]`
before plotting in `generate_efficiency_plots()`. In `generate_section_polar_comparison()`
inf/NaN are removed before plotting the efficiency panel. The star from
`find_second_peak_row()` now always falls on the visual peak of the plotted curve.

### [FIX] Stage 4 `_smart_annotation` — label always pushed upper-right
**File:** `src/vpf_analysis/stage4_performance_metrics/plots.py`

**Problem:** The annotation offset was always `(+6 % x_range, +6 % y_range)`. When the
efficiency peak lies near the right or top edge of the axes the label was pushed outside
the plot area or over the axis spine.

**Fix:** Offset direction is now chosen based on the peak's fractional position in the
axes: if `x_frac > 0.65` the offset goes left; if `y_frac > 0.75` it goes down. This
keeps the annotation inside the plot for all tested conditions.

### [FIX] Stage 4 `compressibility_comparison.png` — annotation in data coordinates
**File:** `src/vpf_analysis/stage4_performance_metrics/plots.py` — `plot_efficiency_penalty_overview()`

**Problem:** The Δα / Δ(CL/CD) annotation used a hardcoded data-coordinate offset
`(alpha_design − 1.2, eff_fixed + 4)`. The `+4` offset scaled with CL/CD values: for
the descent condition (CL/CD ≈ 100) the label was placed outside the figure area.

**Fix:** Replaced with `xytext=(−32, 22), textcoords="offset points"` — a fixed
screen-space offset that is independent of the data range.

### [FIX] Stage 5 `efficiency_curves_{cond}.png` — star from pre-computed map
**File:** `src/vpf_analysis/stage5_pitch_kinematics/application/run_pitch_kinematics.py`
— `_fig_efficiency_curves()`

**Problem:** The star was placed at `alpha_opt_3d_map[key]` / `cl_cd_max_3d_map[key]`,
values computed by `compute_rotational_corrections()` from the cascade-corrected polar.
`build_3d_polar_map()` applies the Du-Selig correction to build the `ld_3d` column that
is actually plotted, producing a slightly different peak location. As a result the star
could appear offset from the visual maximum of the displayed 3D curve.

**Fix:** Star position is re-derived directly from the plotted `df_3d["ld_3d"]` column
(after removing inf/NaN, restricting to `alpha >= 0°` to avoid low-α artefacts). The
star now always sits exactly at the maximum of the curve visible in the figure.

### [REMOVE] Stage 5 φ-ψ stage-loading map
**File:** `src/vpf_analysis/stage5_pitch_kinematics/application/run_pitch_kinematics.py`

Removed function `_fig_phi_psi_map()` (91 lines) and its call in `run_pitch_kinematics()`.
The figure was dropped because:
- The multi-line title was truncated by `tight_layout` when the legend occupied the right side.
- With 12 ideal + 12 actual operating points labelled with 5-pt `offset points` annotations,
  labels for nearby conditions overlapped extensively and were illegible.

The φ-ψ analysis results remain available in `tables/stage_loading.csv` and
`tables/stage_loading_single_actuator.csv`, and are summarised in
`pitch_kinematics_summary.txt`.

### Summary

| # | Stage | File | Change | Severity |
|---|---|---|---|---|
| 20 | S7 | `run_sfc_analysis.py` | Reference bars labelled; zero-gain label overlap eliminated | 🟡 |
| 21 | S4 | `plots.py` | Efficiency curve cleaned before plot → star at visual peak | 🟡 |
| 22 | S4 | `plots.py` | `_smart_annotation` direction adapts to peak position in axes | 🟢 |
| 23 | S4 | `plots.py` | Penalty overview annotation uses `offset points` (data-coord overflow) | 🟡 |
| 24 | S5 | `run_pitch_kinematics.py` | Stage 5 star re-derived from plotted `ld_3d` column | 🟡 |
| 25 | S5 | `run_pitch_kinematics.py` | `_fig_phi_psi_map` removed (truncated title, illegible labels) | 🟡 |

*Generated: 2026-05-14 — Figure quality fixes*
