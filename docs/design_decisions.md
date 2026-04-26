# Design Decisions

Engineering and architectural choices that are non-obvious from reading the code.

---

## 1. Solidity as primary blade geometry parameter

**Decision:** `blade_geometry` in `analysis_config.yaml` uses `solidity` (σ) instead
of chord length.

**Why chord is not the right primary input:**

The chord length `c` only appears in the physics as two non-dimensional ratios:

| Ratio | Where used | Formula |
|-------|-----------|---------|
| Solidity σ = c·Z/(2πr) | Weinig cascade factor, Carter deviation | direct input |
| c/r | Snel rotational correction ΔCL ∝ (c/r)² | derived from σ: c/r = σ·2π/Z |

Both ratios depend on σ and the integer Z. Neither depends on the absolute scale of
the fan. An identical aerodynamic result is obtained whether the fan has radius 1 m
or 3 m, as long as σ is the same — which is the correct physical statement for cascade
and rotational corrections.

**Consequence:** the pipeline is now scale-agnostic for Stages 5–7. You can change
fan diameter, number of blades, or operating RPM without touching the blade geometry
section — only the Reynolds numbers and fan radii need updating.

**Recovery when dimensional chord is needed** (e.g. BEM thrust integration):

```python
import math
c = sigma * 2 * math.pi * r / Z   # chord in metres
```

This relationship is documented in `config/domain.py :: BladeGeometry` and in the
`blade_geometry.solidity` comment in `analysis_config.yaml`.

---

## 2. Reynolds numbers specified directly in the YAML

**Decision:** `reynolds` in `analysis_config.yaml` is a lookup table
`{condition: {section: Re}}` rather than being computed from fan geometry at runtime.

**Why:** Reynolds number depends on ISA atmosphere at altitude (ρ, μ), axial velocity
Va, blade section radius r, RPM, and chord. Computing it requires ISA tables and
several intermediate steps. Specifying it explicitly:

- Makes the derivation auditable (comments show ρ, μ, W_rel, c at each condition).
- Allows deliberate overrides (e.g. hot-and-high takeoff, non-standard atmosphere).
- Keeps XFOIL simulation setup independent of fan geometry changes.

The comments in the YAML show the full derivation for cross-checking.

---

## 3. Polar efficiency column standardised to `ld_corrected`

**Decision:** Stage 3 always writes `ld_corrected` as the canonical efficiency column
(Kármán–Tsien L/D with wave drag). Stage 2 writes `ld` (incompressible baseline).

**Why:** Multiple stages (4, 5, 7) need to locate the efficiency column without
knowing which stage's output they are reading. `resolve_efficiency_column()` in
`postprocessing/aerodynamics_utils.py` searches in priority order:
`["ld_corrected", "ld"]`. This means any stage can read any polar file without
branching on its origin.

---

## 4. Configuration split: analysis vs engine

**Decision:** two separate YAML files — `analysis_config.yaml` and
`engine_parameters.yaml`.

**Why:** the two files have different audiences and change rates:

| File | Controls | Changes when |
|------|----------|--------------|
| `analysis_config.yaml` | Fan geometry, XFOIL settings, flight conditions, Re, Ncrit | Fan design changes |
| `engine_parameters.yaml` | SFC, η_fan, BPR, mission profile, mechanism weight | Engine/mission assumptions change |

Stage 7 reads only `engine_parameters.yaml`. Stages 1–5 read only
`analysis_config.yaml`. Stage 6 reads both. This prevents accidental coupling.

---

## 5. PhysicsConstants frozen dataclass

**Decision:** all empirical coefficients (Carter m, Snel a, Weinig bounds, design
zone limits) live in `PhysicsConstants` in `config/domain.py`, not scattered as
module-level constants.

**Why:** a frozen dataclass with `get_settings().physics.*` access:

- Is a single place to look up any empirical value.
- Cannot be mutated at runtime (prevents silent override bugs in tests).
- Is type-checked (IDE autocomplete, mypy).
- Can be overridden in tests by constructing a custom `PipelineSettings`.

---

## 6. Stage communication exclusively through files

**Decision:** no stage imports from another stage's Python module. All inter-stage
data exchange happens through CSV files in `results/`.

**Why:** it enforces that every intermediate result is inspectable, reproducible, and
re-runnable from any checkpoint. It also means each stage can be rerun independently
with `python -m vpf_analysis.stageN.application.run_stageN` without re-executing
upstream stages.

The formal contracts (`pipeline/contracts.py :: StageNResult`) validate that required
output files exist before the next stage starts, catching failures early.

---

## 7. CL_MIN_VIABLE in PhysicsConstants, not in metrics.py

**Decision:** `CL_MIN_VIABLE = 0.50` (minimum viable fan blade CL) lives in
`PhysicsConstants`, not as a module-level constant in `metrics.py`.

**Why:** Stage 4 and Stage 5 both filter polars on a minimum CL threshold. Having
two independent module constants risks them drifting apart silently. `PhysicsConstants`
is the single place for all empirical bounds, which are then accessible via
`get_settings().physics.CL_MIN_VIABLE` everywhere.

Note: `CL_MIN_3D = 0.30` and `CL_MIN_VIABLE = 0.50` are different concepts:
- `CL_MIN_3D`: minimum for a point to count as physically valid in 3D polar.
- `CL_MIN_VIABLE`: minimum for a fan blade to be considered aerodynamically useful
  (higher, filters out deep low-loading operating points in Stage 4 metrics).

---

## 8. SFC reference value consistency

**Decision:** `engine_parameters.yaml :: baseline_sfc = 0.49` matches
`engine_data.py :: GE9X_PARAMS["SFC_ref_cruise"] = 0.49`.

The physics-based GE9X thermodynamic cycle model (`turbofan_cycle.py`) is the
authoritative reference for the engine SFC. The YAML value must match it so that
Stage 7's two SFC calculation paths (Walsh-Fletcher empirical model and GE9X cycle
model) start from the same baseline.

---

## 9. What chord size does (and does not) affect

After the σ-first refactor (decision 1), chord affects the pipeline as follows:

| Effect | Mediated by | Scale-dependent? |
|--------|-------------|-----------------|
| Weinig cascade factor K_weinig | σ only | No |
| Carter deviation δ | σ and θ | No |
| Snel rotational correction ΔCL | (c/r)² = (σ·2π/Z)² | No |
| Reynolds number | Re = ρ·W·c/μ | **Yes** — but Re is hardcoded in YAML |
| BEM reverse thrust dT/dr | n·q·c·C_T | **Yes** — c recovered from σ·2πr/Z |

For the current pipeline scope (Stages 1–7 excluding full BEM), chord size has
**no effect on the computed results** once σ is fixed and Re is specified directly.
The absolute fan scale only matters if you extend the pipeline to full BEM or noise
analysis.
