"""
data_loader.py
--------------
Filesystem adapter for Stage 6 — loads Stage 5 kinematics tables and
Stage 3 corrected polars needed for reverse thrust analysis.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict

import pandas as pd

LOGGER = logging.getLogger(__name__)

_SECTIONS = ["root", "mid_span", "tip"]


class ReverseDataLoader:
    """Loads Stage 5 and Stage 3 data required for reverse thrust analysis."""

    def __init__(self, stage5_dir: Path, stage3_dir: Path) -> None:
        self._s5 = stage5_dir
        self._s3 = stage3_dir

    def load_blade_twist(self) -> pd.DataFrame:
        path = self._s5 / "tables" / "blade_twist_design.csv"
        if not path.exists():
            raise FileNotFoundError(f"Stage 5 blade_twist_design.csv not found: {path}")
        return pd.read_csv(path)

    def load_polars_takeoff(self) -> Dict[str, pd.DataFrame]:
        """Load Stage 3 takeoff corrected polars for each section.

        Takeoff Mach (~0.47 on ground) is closest to the Stage 3 takeoff
        condition (M=0.85 relative blade frame) among the available polars.
        Using the takeoff polar gives the most relevant CD base for the
        separation extrapolation needed at negative alpha.
        """
        polars: Dict[str, pd.DataFrame] = {}
        for sec in _SECTIONS:
            path = self._s3 / "takeoff" / sec / "corrected_polar.csv"
            if not path.exists():
                LOGGER.warning("Takeoff polar not found for section %s: %s", sec, path)
                continue
            df = pd.read_csv(path)
            required = {"alpha", "cl_kt", "cd_corrected"}
            if not required.issubset(df.columns):
                missing = required - set(df.columns)
                LOGGER.warning("Missing columns %s in %s — skipping section.", missing, path)
                continue
            polars[sec] = df
        if not polars:
            raise FileNotFoundError(
                f"No takeoff corrected polars found under {self._s3 / 'takeoff'}"
            )
        return polars
