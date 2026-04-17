"""
mechanism_weight_service.py
---------------------------
Estimates the weight of the VPF pitch-change mechanism and its cruise SFC
penalty compared to a baseline with no reverser and to a conventional
cascade-type thrust reverser.

Weight fractions (both as % of engine dry weight)
--------------------------------------------------
VPF mechanism (actuator ring + pitch links + blade-root reinforcement):
  ~3–5% — default 4%  (lighter than cascade reverser because no duct structure
  or blocker doors; only the hub actuator and blade attachment hardware).

Conventional cascade reverser (cascades + blocker doors + nacelle structural
reinforcement + actuation):
  ~8–12% — default 10%  (Ref: Farokhi §9.6; Saravanamuttoo Table 8.3).

SFC penalty at cruise (first-order Breguet approximation)
---------------------------------------------------------
Extra weight W_extra requires extra lift → extra drag → more thrust:
  ΔT = W_extra × g / (L/D)
  ΔSFC_pct ≈ ΔT / T_cruise_total × 100

where T_cruise_total = 2 × design_thrust × cruise_thrust_fraction.

This is conservative because it attributes the full mechanism weight to fuel
burn over the entire mission, ignoring that at top-of-descent the aircraft is
lighter. A full Breguet integration would give a slightly lower number.

Net result vs conventional reverser: the VPF mechanism saves ~950 kg (for a
twin-engine aircraft with GE9X engines), translating to ~0.66% SFC improvement.
"""

from __future__ import annotations

from vfp_analysis.stage6_reverse_thrust.core.domain.reverse_thrust_result import (
    MechanismWeightResult,
)

_G = 9.81  # m/s²


def compute_mechanism_weight(
    engine_dry_weight_kg: float,
    mechanism_weight_fraction: float,
    conventional_reverser_fraction: float,
    design_thrust_kN: float,
    cruise_thrust_fraction: float,
    aircraft_L_D: float,
    n_engines: int = 2,
) -> MechanismWeightResult:
    """Compute VPF mechanism weight and its cruise SFC impact.

    Parameters
    ----------
    engine_dry_weight_kg:
        Dry weight of one engine [kg].
    mechanism_weight_fraction:
        VPF mechanism weight as fraction of engine dry weight (e.g. 0.04 = 4%).
    conventional_reverser_fraction:
        Cascade reverser weight fraction for comparison (e.g. 0.10).
    design_thrust_kN:
        Sea-level static thrust per engine [kN].
    cruise_thrust_fraction:
        Thrust at cruise as fraction of design (from mission profile).
    aircraft_L_D:
        Cruise lift-to-drag ratio.
    n_engines:
        Number of engines (default 2).

    Returns
    -------
    MechanismWeightResult
    """
    mechanism_weight_kg     = n_engines * engine_dry_weight_kg * mechanism_weight_fraction
    conventional_weight_kg  = n_engines * engine_dry_weight_kg * conventional_reverser_fraction
    weight_saving_kg        = conventional_weight_kg - mechanism_weight_kg

    # Total cruise thrust (both engines)
    t_cruise_total_N = n_engines * design_thrust_kN * 1000.0 * cruise_thrust_fraction

    # SFC penalty vs no reverser at all
    delta_t_mechanism_N = mechanism_weight_kg * _G / aircraft_L_D
    sfc_penalty_pct = (delta_t_mechanism_N / t_cruise_total_N) * 100.0

    # SFC benefit vs conventional reverser (weight saving → less drag)
    delta_t_saving_N = weight_saving_kg * _G / aircraft_L_D
    sfc_benefit_pct  = (delta_t_saving_N / t_cruise_total_N) * 100.0

    return MechanismWeightResult(
        mechanism_weight_kg=mechanism_weight_kg,
        conventional_reverser_weight_kg=conventional_weight_kg,
        weight_saving_vs_conventional_kg=weight_saving_kg,
        sfc_cruise_penalty_pct=sfc_penalty_pct,
        sfc_benefit_vs_conventional_pct=sfc_benefit_pct,
    )
