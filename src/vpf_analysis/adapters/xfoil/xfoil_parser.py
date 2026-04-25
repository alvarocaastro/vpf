"""xfoil_parser.py — robust parser for XFOIL space-delimited polar files."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List

import pandas as pd

from vpf_analysis.validation.validators import (
    PolarQualityWarning,
    validate_polar_quality,
)

LOGGER = logging.getLogger(__name__)


def parse_polar_file(
    polar_path: Path | str,
    context: str = "",
    run_quality_checks: bool = True,
) -> pd.DataFrame:
    """Parse an XFOIL polar file into a DataFrame with columns: alpha, cl, cd, cm, ld."""
    polar_path = Path(polar_path)
    if not polar_path.exists():
        raise FileNotFoundError(
            f"Polar file not found [{context}]: {polar_path}"
        )

    rows: List[dict] = []
    n_skipped = 0

    with polar_path.open("r", encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            stripped = line.strip()
            if not stripped:
                continue
            parts = stripped.split()

            try:
                alpha = float(parts[0])
            except (ValueError, IndexError):
                continue

            # Need at least alpha, CL, CD, CDp, CM (5 fields)
            if len(parts) < 5:
                n_skipped += 1
                continue

            try:
                cl = float(parts[1])
                cd = float(parts[2])
                cm = float(parts[4])
            except ValueError:
                n_skipped += 1
                continue

            ld = cl / cd if cd > 0.0 else float("nan")
            rows.append({"alpha": alpha, "cl": cl, "cd": cd, "cm": cm, "ld": ld})

    if n_skipped > 0:
        LOGGER.debug(
            "XFOIL parser [%s]: %d lines skipped (headers or malformed)",
            context or polar_path.name,
            n_skipped,
        )

    df = pd.DataFrame(rows)

    if df.empty:
        LOGGER.warning(
            "Empty XFOIL polar [%s]: %s — no valid numeric data.",
            context or "?",
            polar_path,
        )
        return df

    if run_quality_checks:
        warnings: List[PolarQualityWarning] = validate_polar_quality(
            df, context=context or polar_path.stem
        )
        for w in warnings:
            LOGGER.warning("Polar quality [%s] %s: %s", w.context, w.code, w.message)

    LOGGER.debug(
        "XFOIL polar parsed [%s]: %d points, α=[%.1f, %.1f], CL=[%.3f, %.3f]",
        context or polar_path.stem,
        len(df),
        df["alpha"].min(),
        df["alpha"].max(),
        df["cl"].min(),
        df["cl"].max(),
    )

    return df
