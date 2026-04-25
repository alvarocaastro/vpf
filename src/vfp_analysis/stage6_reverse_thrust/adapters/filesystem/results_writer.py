"""Filesystem adapter for Stage 6 — writes mechanism weight CSV and figure."""

from __future__ import annotations

import logging
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from vfp_analysis.shared.plot_style import apply_style
from vfp_analysis.stage6_reverse_thrust.core.domain.reverse_thrust_result import (
    MechanismWeightResult,
)

LOGGER = logging.getLogger(__name__)


class ReverseResultsWriter:
    def __init__(self, output_dir: Path) -> None:
        self._out = output_dir
        (output_dir / "tables").mkdir(parents=True, exist_ok=True)
        (output_dir / "figures").mkdir(parents=True, exist_ok=True)

    def write_mechanism_weight(self, mw: MechanismWeightResult) -> Path:
        data = {
            "metric": [
                "mechanism_weight_kg",
                "conventional_reverser_weight_kg",
                "weight_saving_vs_conventional_kg",
                "sfc_cruise_penalty_pct",
                "sfc_benefit_vs_conventional_pct",
            ],
            "value": [
                mw.mechanism_weight_kg,
                mw.conventional_reverser_weight_kg,
                mw.weight_saving_vs_conventional_kg,
                mw.sfc_cruise_penalty_pct,
                mw.sfc_benefit_vs_conventional_pct,
            ],
        }
        path = self._out / "tables" / "mechanism_weight.csv"
        pd.DataFrame(data).to_csv(path, index=False, float_format="%.4f")
        return path

    def write_figures(self, mw: MechanismWeightResult) -> list[Path]:
        with apply_style():
            return [self._plot_weight_comparison(mw)]

    def _plot_weight_comparison(self, mw: MechanismWeightResult) -> Path:
        labels  = ["No reverser\n(baseline)", "VPF mechanism\n(this work)", "Cascade reverser\n(conventional)"]
        weights = [0.0, mw.mechanism_weight_kg, mw.conventional_reverser_weight_kg]
        sfc_impacts = [
            0.0,
            mw.sfc_cruise_penalty_pct,
            mw.sfc_cruise_penalty_pct - mw.sfc_benefit_vs_conventional_pct,
        ]
        colors_bar = ["#BBBBBB", "#4477AA", "#D55E00"]

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9, 4.5))

        bars1 = ax1.bar(labels, weights, color=colors_bar, edgecolor="white", linewidth=0.6)
        ax1.bar_label(bars1, fmt="%.0f kg", padding=3, fontsize=9)
        ax1.set_ylabel("Reverser system weight [kg]  (both engines)")
        ax1.set_title("Weight Comparison")
        ax1.grid(axis="y", alpha=0.3)

        bars2 = ax2.bar(labels, sfc_impacts, color=colors_bar, edgecolor="white", linewidth=0.6)
        ax2.bar_label(bars2, fmt="%.3f%%", padding=3, fontsize=9)
        ax2.set_ylabel("ΔSFC at cruise [%]  (vs no reverser)")
        ax2.set_title("Cruise SFC Penalty")
        ax2.grid(axis="y", alpha=0.3)

        fig.suptitle(
            f"VPF mechanism saves {mw.weight_saving_vs_conventional_kg:.0f} kg vs conventional  |  "
            f"SFC benefit vs conventional: -{mw.sfc_benefit_vs_conventional_pct:.3f}%",
            fontsize=10, y=1.01,
        )
        fig.tight_layout()
        path = self._out / "figures" / "mechanism_weight_comparison.png"
        fig.savefig(path, bbox_inches="tight", dpi=300)
        plt.close(fig)
        return path
