"""
reverse_kinematics_service.py
-----------------------------
Computes velocity triangles for each blade section under reverse-thrust
operating conditions.

In reverse mode the fan spins at reduced N1 (typically 65% of design) to
avoid flutter and limit structural loads. The blade pitch is shifted to
negative angles so that the aerodynamic incidence causes reverse thrust.

Coordinate convention
---------------------
- phi_rev > 0: inflow angle measured from the tangential plane (always > 0)
- beta_rev = beta_metal + delta_beta  (delta_beta < 0 for reverse)
- alpha_rev = beta_rev − phi_rev      (negative for reverse operation)
- Thrust: dT/dr = Z × 0.5ρW² × c × (CL sinφ − CD cosφ)
          When CL < 0 and large enough → dT/dr < 0 → reverse thrust

Ref: Dixon & Hall (2013) ch. 2; Cumpsty (2004) ch. 3.
"""

from __future__ import annotations

import math
from typing import List

import pandas as pd

from vfp_analysis.stage6_reverse_thrust.core.domain.reverse_thrust_result import (
    ReverseKinematicsSection,
)

# Section ordering is fixed across the pipeline
_SECTIONS = ["root", "mid_span", "tip"]


def compute_reverse_kinematics(
    blade_twist_df: pd.DataFrame,
    chord_map: dict[str, float],
    n1_fraction: float,
    va_landing_m_s: float,
) -> List[ReverseKinematicsSection]:
    """Compute reverse-mode velocity triangles for all blade sections.

    Parameters
    ----------
    blade_twist_df:
        Stage 5 ``blade_twist_design.csv`` — must contain columns
        ``section``, ``radius_m``, ``U_cruise_m_s``.
    chord_map:
        Chord per section [m], e.g. ``{"root": 0.36, "mid_span": 0.46, "tip": 0.46}``.
    n1_fraction:
        Fan speed as fraction of design N1 (0–1).
    va_landing_m_s:
        Axial airspeed during ground roll [m/s].

    Returns
    -------
    List[ReverseKinematicsSection]
        One entry per blade section, ordered root → mid_span → tip.
    """
    # Build radius list for Δr computation (trapezoidal strips)
    rows: dict[str, dict] = {}
    for _, row in blade_twist_df.iterrows():
        sec = str(row["section"])
        if sec in _SECTIONS:
            rows[sec] = {
                "radius_m": float(row["radius_m"]),
                "u_cruise":  float(row["U_cruise_m_s"]),
            }

    radii = [rows[s]["radius_m"] for s in _SECTIONS if s in rows]
    r_hub = radii[0] - (radii[1] - radii[0]) / 2.0  # estimated hub radius

    boundaries = [r_hub] + [(radii[i] + radii[i + 1]) / 2.0 for i in range(len(radii) - 1)] + [radii[-1]]
    delta_r = [boundaries[i + 1] - boundaries[i] for i in range(len(radii))]

    results: List[ReverseKinematicsSection] = []
    for idx, sec in enumerate([s for s in _SECTIONS if s in rows]):
        r   = rows[sec]["radius_m"]
        u_c = rows[sec]["u_cruise"]
        c   = chord_map.get(sec, 0.46)

        u_rev   = n1_fraction * u_c
        w_rel   = math.sqrt(va_landing_m_s**2 + u_rev**2)
        phi_rev = math.degrees(math.atan2(va_landing_m_s, u_rev))

        results.append(ReverseKinematicsSection(
            section=sec,
            radius_m=r,
            chord_m=c,
            u_rev_m_s=u_rev,
            w_rel_m_s=w_rel,
            phi_rev_deg=phi_rev,
            delta_r_m=delta_r[idx],
        ))

    return results
