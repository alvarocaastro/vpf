from __future__ import annotations

from pathlib import Path
from typing import Protocol

from vfp_analysis.core.domain.simulation_condition import SimulationCondition


class XfoilRunnerPort(Protocol):
    """Port for launching an XFOIL polar computation."""

    def run_polar(
        self,
        airfoil_dat: Path,
        condition: SimulationCondition,
        output_file: Path,
    ) -> None:
        """Execute an XFOIL polar sweep and persist the output file."""

