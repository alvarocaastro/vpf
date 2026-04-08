from __future__ import annotations

from pathlib import Path

from vfp_analysis.core.domain.simulation_condition import SimulationCondition
from vfp_analysis.xfoil_runner import XfoilPolarRequest, run_xfoil_polar


class XfoilRunnerAdapter:
    """Thin wrapper around xfoil_runner with a 180 s timeout for final analyses."""

    def run_polar(
        self,
        airfoil_dat: Path,
        condition: SimulationCondition,
        output_file: Path,
    ) -> None:
        request = XfoilPolarRequest(
            airfoil_dat=airfoil_dat,
            re=condition.reynolds,
            alpha_start=condition.alpha_min,
            alpha_end=condition.alpha_max,
            alpha_step=condition.alpha_step,
            mach=condition.mach_rel,
            n_crit=condition.ncrit,
            output_file=output_file,
        )
        run_xfoil_polar(request, timeout=180.0)
