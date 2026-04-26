from __future__ import annotations

import dataclasses
from dataclasses import dataclass

import numpy as np
import pandas as pd

from vpf_analysis.postprocessing.aerodynamics_utils import (
    compute_stall_alpha,
    find_second_peak_row,
)

WEIGHT_MAX_LD = 1.20
WEIGHT_ROBUSTNESS_LD = 0.35
WEIGHT_STABILITY_MARGIN = 0.80


@dataclass(frozen=True)
class AirfoilScore:
    airfoil: str
    max_ld: float
    alpha_opt: float
    stall_alpha: float
    stability_margin: float
    robustness_ld: float
    total_score: float


def score_airfoil(df: pd.DataFrame) -> AirfoilScore:
    """Fan-oriented score for one airfoil polar.

    1. ``max_ld``: second L/D peak (alpha >= 3°) to skip laminar-bubble artefact.
    2. ``stall_alpha``: first alpha where CL drops >5% below CL_max.
    3. ``stability_margin``: stall_alpha - alpha_opt.
    4. ``robustness_ld``: mean L/D within ±FWHM/2 of the peak (resolution-independent).

    total_score is raw here; call ``normalise_scores`` to get normalised totals.
    """
    if df.empty:
        return AirfoilScore(
            airfoil="", max_ld=np.nan, alpha_opt=np.nan, stall_alpha=np.nan,
            stability_margin=np.nan, robustness_ld=np.nan, total_score=np.nan,
        )

    airfoil_name = str(df["airfoil"].iloc[0])
    valid = df.replace([np.inf, -np.inf], np.nan).dropna(subset=["ld", "alpha", "cl"])
    if valid.empty:
        return AirfoilScore(
            airfoil=airfoil_name, max_ld=np.nan, alpha_opt=np.nan, stall_alpha=np.nan,
            stability_margin=np.nan, robustness_ld=np.nan, total_score=np.nan,
        )

    row_opt = find_second_peak_row(valid, "ld", alpha_min=3.0)
    max_ld = float(row_opt["ld"])
    alpha_opt = float(row_opt["alpha"])

    stall_alpha = compute_stall_alpha(valid, "cl")
    stability_margin = max(0.0, stall_alpha - alpha_opt)

    # FWHM of L/D curve → window half-width independent of alpha-sweep resolution
    above_half = valid[valid["ld"] >= max_ld / 2.0]
    if len(above_half) >= 2:
        half_fwhm = (float(above_half["alpha"].max()) - float(above_half["alpha"].min())) / 2.0
    else:
        half_fwhm = 1.0
    df_window = valid[
        (valid["alpha"] >= alpha_opt - half_fwhm) & (valid["alpha"] <= alpha_opt + half_fwhm)
    ]
    robustness_ld = float(df_window["ld"].mean()) if not df_window.empty else max_ld

    total_score = (
        WEIGHT_MAX_LD * max_ld
        + WEIGHT_ROBUSTNESS_LD * robustness_ld
        + WEIGHT_STABILITY_MARGIN * stability_margin
    )

    return AirfoilScore(
        airfoil=airfoil_name,
        max_ld=max_ld,
        alpha_opt=alpha_opt,
        stall_alpha=stall_alpha,
        stability_margin=stability_margin,
        robustness_ld=robustness_ld,
        total_score=total_score,
    )


def normalise_scores(scores: list[AirfoilScore]) -> list[AirfoilScore]:
    """Return new AirfoilScore list with total_score recomputed after min-max normalisation.

    Each component (max_ld, robustness_ld, stability_margin) is scaled to [0, 1]
    across all valid candidates before the weights are applied, so no single
    metric dominates by magnitude.
    """
    valid_idx = [i for i, s in enumerate(scores) if not np.isnan(s.max_ld)]
    if len(valid_idx) < 2:
        return scores

    def _minmax(vals: list[float]) -> list[float]:
        arr = np.array(vals, dtype=float)
        lo, hi = float(np.nanmin(arr)), float(np.nanmax(arr))
        if hi == lo:
            return [0.5] * len(vals)
        return [(v - lo) / (hi - lo) for v in vals]

    max_lds_n = _minmax([scores[i].max_ld for i in valid_idx])
    rob_n = _minmax([scores[i].robustness_ld for i in valid_idx])
    stab_n = _minmax([scores[i].stability_margin for i in valid_idx])

    result = list(scores)
    for j, i in enumerate(valid_idx):
        total = (
            WEIGHT_MAX_LD * max_lds_n[j]
            + WEIGHT_ROBUSTNESS_LD * rob_n[j]
            + WEIGHT_STABILITY_MARGIN * stab_n[j]
        )
        result[i] = dataclasses.replace(scores[i], total_score=float(total))
    return result
