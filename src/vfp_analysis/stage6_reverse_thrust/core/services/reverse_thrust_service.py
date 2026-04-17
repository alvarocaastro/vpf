"""
reverse_thrust_service.py
-------------------------
Blade Element Momentum (BEM) analysis for VPF reverse thrust.

For each pitch-sweep point the service:
  1. Computes blade angle beta_rev = beta_metal + delta_beta for each section.
  2. Derives aerodynamic incidence alpha_rev = beta_rev − phi_rev.
  3. Looks up (CL, CD) from the Stage 3 takeoff polar; extrapolates below
     alpha_min using a linear slope + quadratic separation-drag model.
  4. Applies BEM to integrate radial strips into net axial thrust and shaft
     torque, then derives η_fan_rev and stall margins.
  5. Selects the optimal delta_beta closest to the target thrust fraction.

Extrapolation model below polar alpha_min (typically −5°)
----------------------------------------------------------
  dCL/dα  — computed from the lowest 5 rows of the polar
  CL_extrap = CL(α_min) + (dCL/dα) × (α − α_min)
  CD_extrap = CD(α_min) + 0.015 × (α_min − α)²
  Clips: |CL| ≤ 2.0,  CD ≤ 2.5

Physical note: operating in the stalled regime for reverse thrust is
intentional — the blades block and redirect flow to generate braking force.
The stall margin is still tracked to bound flutter risk at the root.

Ref: Dixon & Hall (2013) §2.4; Montgomerie (2004) extrapolation method;
     Leishman (2006) helicopter reverse-flow aerodynamics.
"""

from __future__ import annotations

import math
from typing import List, Tuple

import numpy as np
import pandas as pd

from vfp_analysis.stage6_reverse_thrust.core.domain.reverse_thrust_result import (
    ReverseKinematicsSection,
    ReverseOptimalResult,
    ReverseSweepPoint,
)

# Conservative negative-stall estimate for NACA 65-series at these Re.
# Negative stall is gentler for cambered profiles: |α_stall_neg| ≈ 0.8 × α_stall_pos.
# With typical α_stall_pos ≈ 14–16°: α_stall_neg ≈ −12°.
_ALPHA_STALL_NEG_DEFAULT_DEG = -12.0


def _get_aero_coeffs(
    polar_df: pd.DataFrame,
    alpha_deg: float,
) -> Tuple[float, float, bool]:
    """Return (CL, CD, in_polar_range) for a given alpha.

    Uses linear interpolation within the polar range and the Montgomerie-style
    linear/quadratic extrapolation below alpha_min.

    Parameters
    ----------
    polar_df:
        Stage 3 corrected polar. Must contain ``alpha``, ``cl_kt``,
        ``cd_corrected`` columns.
    alpha_deg:
        Target angle of attack [°].

    Returns
    -------
    (cl, cd, in_polar_range)
    """
    df = polar_df.dropna(subset=["cl_kt", "cd_corrected", "alpha"]).sort_values("alpha")

    alpha_min = float(df["alpha"].iloc[0])
    alpha_max = float(df["alpha"].iloc[-1])

    if alpha_min <= alpha_deg <= alpha_max:
        cl = float(np.interp(alpha_deg, df["alpha"], df["cl_kt"]))
        cd = float(np.interp(alpha_deg, df["alpha"], df["cd_corrected"]))
        return cl, cd, True

    # Below polar range: linear CL slope + quadratic CD separation
    n_pts = min(5, len(df))
    alpha_low = df["alpha"].iloc[:n_pts].values
    cl_low    = df["cl_kt"].iloc[:n_pts].values
    cd_low    = df["cd_corrected"].iloc[:n_pts].values

    dcl_dalpha = float(np.polyfit(alpha_low, cl_low, 1)[0])    # [1/°]
    cl_at_min  = float(np.interp(alpha_min, df["alpha"], df["cl_kt"]))
    cd_at_min  = float(np.interp(alpha_min, df["alpha"], df["cd_corrected"]))

    delta = alpha_deg - alpha_min               # < 0
    cl_extrap = cl_at_min + dcl_dalpha * delta
    cd_extrap = cd_at_min + 0.015 * delta**2   # separation drag grows quadratically

    # Physical clips
    cl_extrap = float(np.clip(cl_extrap, -2.0, 2.0))
    cd_extrap = float(np.clip(cd_extrap, cd_at_min, 2.5))

    return cl_extrap, cd_extrap, False


def _stall_margin(alpha_rev_deg: float, polar_df: pd.DataFrame) -> float:
    """Compute stall margin for one section in reverse.

    Returns (α_stall_neg − α_rev) / |α_stall_neg|.
    Positive → not yet stalled; negative → past stall.
    """
    # Estimate negative stall from polar or use conservative default
    df = polar_df.dropna(subset=["cl_kt", "alpha"]).sort_values("alpha")
    neg_part = df[df["alpha"] <= 0]
    alpha_stall_neg = _ALPHA_STALL_NEG_DEFAULT_DEG
    if len(neg_part) >= 3:
        # Find where CL gradient reverses sign in the negative-alpha region
        cls = neg_part["cl_kt"].values
        alphas = neg_part["alpha"].values
        grads = np.diff(cls) / np.diff(alphas)
        sign_changes = np.where(np.diff(np.sign(grads)))[0]
        if len(sign_changes) > 0:
            alpha_stall_neg = float(alphas[sign_changes[-1] + 1])

    margin = (alpha_stall_neg - alpha_rev_deg) / abs(alpha_stall_neg)
    return float(margin)


def _bem_forces(
    kin: ReverseKinematicsSection,
    beta_metal_deg: float,
    delta_beta_deg: float,
    polar_df: pd.DataFrame,
    rho: float,
    n_blades: int,
) -> Tuple[float, float, float, float, float, float, bool, bool]:
    """BEM forces for one section at one sweep point.

    Returns
    -------
    (CL, CD, dT_dr [N/m], dQ_dr [Nm/m], stall_margin, alpha_rev, in_polar_range, valid)
    """
    beta_rev_deg = beta_metal_deg + delta_beta_deg
    alpha_rev_deg = beta_rev_deg - kin.phi_rev_deg

    cl, cd, in_range = _get_aero_coeffs(polar_df, alpha_rev_deg)

    phi_rad = math.radians(kin.phi_rev_deg)
    sin_phi = math.sin(phi_rad)
    cos_phi = math.cos(phi_rad)

    q = 0.5 * rho * kin.w_rel_m_s**2        # Dynamic pressure [Pa]
    thrust_coeff = cl * sin_phi - cd * cos_phi
    torque_coeff = cl * cos_phi + cd * sin_phi

    dT_dr = n_blades * q * kin.chord_m * thrust_coeff   # [N/m]
    dQ_dr = n_blades * q * kin.chord_m * kin.radius_m * torque_coeff  # [Nm/m]

    sm = _stall_margin(alpha_rev_deg, polar_df)

    return cl, cd, dT_dr, dQ_dr, sm, alpha_rev_deg, in_range, beta_rev_deg


def compute_reverse_sweep(
    kinematics: List[ReverseKinematicsSection],
    blade_twist_df: pd.DataFrame,
    polar_map: dict[str, pd.DataFrame],
    delta_beta_values: np.ndarray,
    rho: float,
    n_blades: int,
    t_forward_takeoff_kN: float,
    stall_margin_min_threshold: float,
) -> Tuple[List[ReverseSweepPoint], float]:
    """Run the full pitch sweep and return sweep results plus design RPM ω.

    Parameters
    ----------
    kinematics:
        Output of ``compute_reverse_kinematics``.
    blade_twist_df:
        Stage 5 ``blade_twist_design.csv``.
    polar_map:
        {section: corrected_polar DataFrame} from Stage 3 takeoff condition.
    delta_beta_values:
        Array of pitch offsets to evaluate [°].
    rho:
        Air density [kg/m³].
    n_blades:
        Number of fan blades.
    t_forward_takeoff_kN:
        Forward takeoff thrust per engine for normalisation [kN].
    stall_margin_min_threshold:
        Minimum stall margin for ``aerodynamically_valid`` flag.

    Returns
    -------
    (sweep_points, omega_rev [rad/s])
    """
    # Build beta_metal per section
    beta_metal: dict[str, float] = {}
    for _, row in blade_twist_df.iterrows():
        sec = str(row["section"])
        beta_metal[sec] = float(row["beta_metal_deg"])

    # Angular velocity at reverse N1
    mid_kin = next(k for k in kinematics if k.section == "mid_span")
    omega_rev = mid_kin.u_rev_m_s / mid_kin.radius_m  # [rad/s]

    sections = ["root", "mid_span", "tip"]
    kin_map = {k.section: k for k in kinematics}

    sweep_points: List[ReverseSweepPoint] = []

    for db in delta_beta_values:
        # Per-section BEM
        sec_data: dict[str, dict] = {}
        for sec in sections:
            if sec not in kin_map or sec not in polar_map:
                continue
            cl, cd, dT_dr, dQ_dr, sm, alpha_rev, in_range, beta_rev = _bem_forces(
                kin=kin_map[sec],
                beta_metal_deg=beta_metal.get(sec, 30.0),
                delta_beta_deg=float(db),
                polar_df=polar_map[sec],
                rho=rho,
                n_blades=n_blades,
            )
            sec_data[sec] = dict(
                cl=cl, cd=cd, dT_dr=dT_dr, dQ_dr=dQ_dr,
                stall_margin=sm, alpha_rev=alpha_rev,
                in_range=in_range, beta_rev=beta_rev,
            )

        if len(sec_data) < 3:
            continue

        # Integrate thrust and torque (trapezoidal over sections)
        T_total = sum(sec_data[s]["dT_dr"] * kin_map[s].delta_r_m for s in sections if s in sec_data)
        Q_total = sum(sec_data[s]["dQ_dr"] * kin_map[s].delta_r_m for s in sections if s in sec_data)

        T_kN = T_total / 1000.0
        thrust_fraction = abs(T_kN) / t_forward_takeoff_kN if t_forward_takeoff_kN > 0 else 0.0

        # Fan efficiency in reverse: |P_thrust| / P_shaft
        p_thrust = abs(T_total * mid_kin.u_rev_m_s / mid_kin.radius_m * mid_kin.radius_m)
        # Use Va_landing for thrust power: P = |T| × Va
        va = math.sqrt(mid_kin.w_rel_m_s**2 - mid_kin.u_rev_m_s**2)  # Va from W_rel and U
        p_thrust = abs(T_total) * va
        p_shaft  = abs(Q_total * omega_rev)
        eta_rev  = p_thrust / p_shaft if p_shaft > 1.0 else 0.0
        eta_rev  = min(eta_rev, 0.99)

        stall_margins = [sec_data[s]["stall_margin"] for s in sections if s in sec_data]
        sm_min = min(stall_margins)
        valid  = sm_min >= stall_margin_min_threshold

        sweep_points.append(ReverseSweepPoint(
            delta_beta_deg=float(db),
            beta_rev_root_deg=sec_data["root"]["beta_rev"],
            beta_rev_mid_deg=sec_data["mid_span"]["beta_rev"],
            beta_rev_tip_deg=sec_data["tip"]["beta_rev"],
            alpha_rev_root_deg=sec_data["root"]["alpha_rev"],
            alpha_rev_mid_deg=sec_data["mid_span"]["alpha_rev"],
            alpha_rev_tip_deg=sec_data["tip"]["alpha_rev"],
            cl_root=sec_data["root"]["cl"], cd_root=sec_data["root"]["cd"],
            cl_mid=sec_data["mid_span"]["cl"],  cd_mid=sec_data["mid_span"]["cd"],
            cl_tip=sec_data["tip"]["cl"],  cd_tip=sec_data["tip"]["cd"],
            in_polar_range_root=sec_data["root"]["in_range"],
            in_polar_range_mid=sec_data["mid_span"]["in_range"],
            in_polar_range_tip=sec_data["tip"]["in_range"],
            dT_dr_root_N_m=sec_data["root"]["dT_dr"],
            dT_dr_mid_N_m=sec_data["mid_span"]["dT_dr"],
            dT_dr_tip_N_m=sec_data["tip"]["dT_dr"],
            thrust_kN=T_kN,
            thrust_fraction=thrust_fraction,
            eta_fan_rev=eta_rev,
            stall_margin_root=sec_data["root"]["stall_margin"],
            stall_margin_mid=sec_data["mid_span"]["stall_margin"],
            stall_margin_tip=sec_data["tip"]["stall_margin"],
            stall_margin_min=sm_min,
            aerodynamically_valid=valid,
        ))

    return sweep_points, omega_rev


def select_optimal_point(
    sweep: List[ReverseSweepPoint],
    target_thrust_fraction: float,
    n1_fraction: float,
    va_landing_m_s: float,
) -> ReverseOptimalResult:
    """Select the best operating point from the sweep.

    Preference order:
      1. Aerodynamically valid points (stall_margin_min ≥ threshold).
      2. Among those, closest to target_thrust_fraction.
      3. If none are valid, relax to any point with T < 0 (reverse thrust).

    Parameters
    ----------
    sweep:
        Full list of sweep points.
    target_thrust_fraction:
        Desired |T_rev| / T_forward_takeoff.
    n1_fraction, va_landing_m_s:
        Stored in the result for reference.

    Returns
    -------
    ReverseOptimalResult
    """
    reverse_points = [p for p in sweep if p.thrust_kN < 0.0]
    if not reverse_points:
        # Fallback: pick point with most negative thrust even if no reverse
        reverse_points = sweep

    valid_pts = [p for p in reverse_points if p.aerodynamically_valid]
    candidate_pool = valid_pts if valid_pts else reverse_points

    best = min(candidate_pool, key=lambda p: abs(p.thrust_fraction - target_thrust_fraction))

    return ReverseOptimalResult(
        delta_beta_opt_deg=best.delta_beta_deg,
        beta_opt_root_deg=best.beta_rev_root_deg,
        beta_opt_mid_deg=best.beta_rev_mid_deg,
        beta_opt_tip_deg=best.beta_rev_tip_deg,
        thrust_net_kN=best.thrust_kN,
        thrust_fraction=best.thrust_fraction,
        eta_fan_rev=best.eta_fan_rev,
        n1_fraction=n1_fraction,
        va_landing_m_s=va_landing_m_s,
        stall_margin_min=best.stall_margin_min,
        aerodynamically_valid=best.aerodynamically_valid,
    )
