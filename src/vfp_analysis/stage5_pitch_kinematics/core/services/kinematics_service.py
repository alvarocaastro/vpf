"""
kinematics_service.py
---------------------
Resuelve los triángulos de velocidad y calcula el paso mecánico real.

Para cada (condición, sección):
    Va    = velocidad axial explícita del config [m/s]   ← NO Mach × a
    U     = ω × r                                        # velocidad de pala [m/s]
    φ     = arctan(Va / U)                               # ángulo de entrada de flujo [°]
    β     = α_opt_3D + φ                                 # ángulo de paso mecánico [°]
    Δβ    = β(condición) − β(crucero)                    # ajuste respecto a referencia [°]

Fuente única de verdad: analysis_config.yaml (sección fan_geometry).
Va, radios y RPM se leen de ahí mediante config_loader para evitar duplicación
con engine_parameters.yaml.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Dict, List

from vfp_analysis.config_loader import get_axial_velocities, get_blade_radii, get_fan_rpm
from vfp_analysis.stage5_pitch_kinematics.core.domain.pitch_kinematics_result import (
    KinematicsResult,
    PitchAdjustment,
)


def compute_kinematics(
    pitch_adjustments: List[PitchAdjustment],
    engine_config_path: Path,
    reference_condition: str = "cruise",
) -> List[KinematicsResult]:
    """
    Calcula triángulos de velocidad y paso mecánico para cada caso.

    Parameters
    ----------
    pitch_adjustments : List[PitchAdjustment]
        Ajustes de paso aerodinámico de pitch_adjustment_service.
    engine_config_path : Path
        Ignorado — mantenido por compatibilidad de firma. Los parámetros
        geométricos se leen de analysis_config.yaml (fuente única).
    reference_condition : str
        Condición de referencia para calcular Δβ.

    Returns
    -------
    List[KinematicsResult]
    """
    rpm     = get_fan_rpm()
    radii   = get_blade_radii()
    va_dict = get_axial_velocities()
    omega   = rpm * (2.0 * math.pi / 60.0)   # [rad/s]

    results: List[KinematicsResult] = []
    reference_beta: Dict[str, float] = {}            # section → β_mech_ref

    # Pasada 1: β absoluto por caso
    for adj in pitch_adjustments:
        va    = va_dict.get(adj.condition, float("nan"))
        r     = radii.get(adj.section, float("nan"))
        u     = omega * r if not math.isnan(r) else float("nan")
        phi   = math.degrees(math.atan2(va, u)) if (u > 0 and not math.isnan(va)) else 0.0
        beta  = adj.alpha_opt + phi

        results.append(KinematicsResult(
            condition=adj.condition,
            section=adj.section,
            axial_velocity=va,
            tangential_velocity=u,
            inflow_angle_deg=phi,
            alpha_aero_deg=adj.alpha_opt,
            beta_mech_deg=beta,
        ))

        if adj.condition == reference_condition:
            reference_beta[adj.section] = beta

    # Pasada 2: Δβ respecto a la referencia
    for res in results:
        ref_b = reference_beta.get(res.section, res.beta_mech_deg)
        res.delta_beta_mech_deg = res.beta_mech_deg - ref_b

    return results
