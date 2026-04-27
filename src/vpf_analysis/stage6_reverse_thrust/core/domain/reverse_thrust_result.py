"""
reverse_thrust_result.py
------------------------
Domain dataclasses for Stage 6 — VPF Reverse Thrust Modeling.

All results are frozen dataclasses to prevent accidental mutation after
computation. Field order matches the order in which values are calculated.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReverseKinematicsSection:
    """Velocity triangle in reverse mode for one blade section.

    Computed at N1_fraction × design RPM and Va_landing axial speed.
    """
    section: str
    radius_m: float          # Blade section radius [m]
    chord_m: float           # Blade chord [m]
    u_rev_m_s: float         # Tangential velocity at reduced N1 [m/s]
    w_rel_m_s: float         # Relative velocity magnitude [m/s]
    phi_rev_deg: float       # Inflow angle at reverse conditions [°]
    delta_r_m: float         # Radial width of representative strip [m]


@dataclass(frozen=True)
class ReverseSweepPoint:
    """Single point in the beta-pitch sweep for reverse thrust analysis."""
    delta_beta_deg: float    # Pitch offset from beta_metal_cruise [°]

    # Per-section blade angle and aerodynamic incidence
    beta_rev_root_deg: float
    beta_rev_mid_deg: float
    beta_rev_tip_deg: float
    alpha_rev_root_deg: float
    alpha_rev_mid_deg: float
    alpha_rev_tip_deg: float

    # Aerodynamic coefficients per section (may be extrapolated)
    cl_root: float;  cd_root: float
    cl_mid:  float;  cd_mid:  float
    cl_tip:  float;  cd_tip:  float

    # Whether alpha_rev falls within the available Stage 3 polar range.
    in_polar_range_root: bool
    in_polar_range_mid: bool
    in_polar_range_tip: bool

    # Integrated BEM forces
    dT_dr_root_N_m: float    # Axial thrust per unit span at root [N/m]
    dT_dr_mid_N_m: float
    dT_dr_tip_N_m: float
    thrust_kN: float         # Net integrated thrust [kN]  (< 0 = reverse)

    # Derived performance
    thrust_fraction: float   # |T| / T_forward_takeoff [0–1]
    eta_fan_rev: float       # Fan efficiency in reverse mode [–]

    # Stall margin per section: (alpha_stall_neg − alpha_rev) / |alpha_stall_neg|
    stall_margin_root: float
    stall_margin_mid: float
    stall_margin_tip: float
    stall_margin_min: float          # = min of the three above

    # Aerodynamic validity flag
    aerodynamically_valid: bool      # stall_margin_min ≥ config threshold


@dataclass(frozen=True)
class ReverseOptimalResult:
    """Optimal reverse thrust operating point selected from the sweep."""
    delta_beta_opt_deg: float        # Pitch offset at optimum [°]
    beta_opt_root_deg: float         # Absolute blade angle at root [°]
    beta_opt_mid_deg: float          # Absolute blade angle at mid-span [°]
    beta_opt_tip_deg: float          # Absolute blade angle at tip [°]
    thrust_net_kN: float             # Net reverse thrust [kN]  (< 0)
    thrust_fraction: float           # |T_rev| / T_forward_takeoff [–]
    eta_fan_rev: float               # Fan efficiency in reverse [–]
    n1_fraction: float               # N1 fraction used [–]
    va_landing_m_s: float            # Axial speed used [m/s]
    stall_margin_min: float          # Minimum stall margin across sections [–]
    aerodynamically_valid: bool


@dataclass(frozen=True)
class MechanismWeightResult:
    """VPF pitch mechanism weight and SFC impact compared to alternatives."""
    # Absolute weights (both engines combined)
    mechanism_weight_kg: float               # VPF actuator + pitch links + root reinforcement
    conventional_reverser_weight_kg: float   # Cascade + blocker doors + nacelle reinforcement

    # Balance vs alternatives
    weight_saving_vs_conventional_kg: float  # > 0 means VPF is lighter

    # SFC impact at cruise (first-order Breguet approximation)
    sfc_cruise_penalty_pct: float            # ΔSFC from carrying mechanism (vs no reverser)
    sfc_benefit_vs_conventional_pct: float   # ΔSFC improvement vs conventional reverser
