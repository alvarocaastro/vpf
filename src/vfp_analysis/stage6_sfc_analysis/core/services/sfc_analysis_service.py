"""
sfc_analysis_service.py
-----------------------
Orquesta el cálculo completo de reducción de SFC para todas las condiciones
de vuelo a partir de los datos de incidencia óptima de Stage 5.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

import pandas as pd
import yaml

from vfp_analysis.config_loader import get_flight_conditions
from vfp_analysis.stage6_sfc_analysis.core.domain.sfc_parameters import (
    EngineBaseline,
    SfcAnalysisResult,
)
from vfp_analysis.stage6_sfc_analysis.core.services.propulsion_model_service import (
    compute_fan_efficiency_improvement,
    compute_sfc_improvement,
    compute_sfc_reduction_percent,
)


def compute_sfc_analysis(
    optimal_incidence_df: pd.DataFrame,
    engine_baseline: EngineBaseline,
    config_path: Path | None = None,
) -> List[SfcAnalysisResult]:
    """
    Calcula el análisis de SFC para todas las condiciones de vuelo.

    Parameters
    ----------
    optimal_incidence_df : pd.DataFrame
        Tabla de incidencias óptimas con columna ``CL_CD_max``
        (salida de Stage 5: tables/optimal_incidence.csv).
    engine_baseline : EngineBaseline
        Parámetros base del motor.
    config_path : Path, optional
        Ruta a engine_parameters.yaml (para SFC multipliers).

    Returns
    -------
    List[SfcAnalysisResult]
    """
    sfc_multipliers: dict[str, float] = {}
    if config_path and config_path.exists():
        with config_path.open("r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
            sfc_multipliers = config.get("sfc_multipliers", {})

    flight_conditions = get_flight_conditions()
    baseline_cl_cd    = _get_baseline_cl_cd(optimal_incidence_df, "cruise")
    results: List[SfcAnalysisResult] = []

    for condition in flight_conditions:
        vpf_cl_cd = _get_vpf_cl_cd(optimal_incidence_df, condition)

        if vpf_cl_cd <= 0 or baseline_cl_cd <= 0:
            continue

        fan_efficiency_new = compute_fan_efficiency_improvement(
            baseline_cl_cd, vpf_cl_cd, engine_baseline.fan_efficiency,
        )
        efficiency_gain = (
            (fan_efficiency_new - engine_baseline.fan_efficiency)
            / engine_baseline.fan_efficiency
        )

        sfc_multiplier = sfc_multipliers.get(condition, 1.0)
        sfc_baseline   = engine_baseline.baseline_sfc * sfc_multiplier
        sfc_new        = compute_sfc_improvement(sfc_baseline, efficiency_gain)
        sfc_reduction  = compute_sfc_reduction_percent(sfc_baseline, sfc_new)

        results.append(SfcAnalysisResult(
            condition=condition,
            cl_cd_baseline=baseline_cl_cd,
            cl_cd_vpf=vpf_cl_cd,
            fan_efficiency_baseline=engine_baseline.fan_efficiency,
            fan_efficiency_new=fan_efficiency_new,
            sfc_baseline=sfc_baseline,
            sfc_new=sfc_new,
            sfc_reduction_percent=sfc_reduction,
        ))

    return results


def _mean_cl_cd(df: pd.DataFrame) -> float:
    """Devuelve la media del CL/CD del DataFrame usando la primera columna disponible."""
    for col in ("CL_CD_max", "ld_max"):
        if col in df.columns:
            return float(df[col].mean())
    return 0.0


def _get_baseline_cl_cd(df: pd.DataFrame, reference_condition: str) -> float:
    """CL/CD medio de la condición de referencia (crucero).

    Si la condición de referencia no existe en el DataFrame, usa la media global.
    Retorna 0.0 si no se encuentran columnas de eficiencia.
    """
    ref = df[df["condition"] == reference_condition]
    return _mean_cl_cd(ref) if not ref.empty else _mean_cl_cd(df)


def _get_vpf_cl_cd(df: pd.DataFrame, condition: str) -> float:
    """CL/CD medio para una condición de vuelo con VPF activo.

    Retorna 0.0 si la condición no existe en el DataFrame.
    """
    subset = df[df["condition"] == condition]
    return _mean_cl_cd(subset) if not subset.empty else 0.0
