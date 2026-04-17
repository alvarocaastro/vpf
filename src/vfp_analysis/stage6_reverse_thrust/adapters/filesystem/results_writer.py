"""
results_writer.py
-----------------
Filesystem adapter for Stage 6 — writes CSVs and figures for the reverse
thrust analysis results.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from vfp_analysis.shared.plot_style import COLORS, apply_style
from vfp_analysis.stage6_reverse_thrust.core.domain.reverse_thrust_result import (
    MechanismWeightResult,
    ReverseKinematicsSection,
    ReverseOptimalResult,
    ReverseSweepPoint,
)

LOGGER = logging.getLogger(__name__)

_SECTION_LABELS = {"root": "Root", "mid_span": "Mid-span", "tip": "Tip"}
_SECTION_COLORS = {
    "root":     COLORS.get("takeoff", "#E66101"),
    "mid_span": COLORS.get("cruise",  "#4477AA"),
    "tip":      COLORS.get("descent", "#1A9850"),
}


class ReverseResultsWriter:
    """Writes all Stage 6 outputs (tables + figures) to disk."""

    def __init__(self, output_dir: Path) -> None:
        self._out = output_dir
        (output_dir / "tables").mkdir(parents=True, exist_ok=True)
        (output_dir / "figures").mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Tables
    # ------------------------------------------------------------------

    def write_kinematics(self, kinematics: List[ReverseKinematicsSection]) -> Path:
        rows = [
            {
                "section": k.section,
                "radius_m": k.radius_m,
                "chord_m": k.chord_m,
                "u_rev_m_s": k.u_rev_m_s,
                "w_rel_m_s": k.w_rel_m_s,
                "phi_rev_deg": k.phi_rev_deg,
                "delta_r_m": k.delta_r_m,
            }
            for k in kinematics
        ]
        path = self._out / "tables" / "reverse_kinematics.csv"
        pd.DataFrame(rows).to_csv(path, index=False, float_format="%.6f")
        return path

    def write_sweep(self, sweep: List[ReverseSweepPoint]) -> Path:
        rows = []
        for p in sweep:
            rows.append({
                "delta_beta_deg": p.delta_beta_deg,
                "beta_rev_root_deg": p.beta_rev_root_deg,
                "beta_rev_mid_deg": p.beta_rev_mid_deg,
                "beta_rev_tip_deg": p.beta_rev_tip_deg,
                "alpha_rev_root_deg": p.alpha_rev_root_deg,
                "alpha_rev_mid_deg": p.alpha_rev_mid_deg,
                "alpha_rev_tip_deg": p.alpha_rev_tip_deg,
                "cl_root": p.cl_root, "cd_root": p.cd_root,
                "cl_mid":  p.cl_mid,  "cd_mid":  p.cd_mid,
                "cl_tip":  p.cl_tip,  "cd_tip":  p.cd_tip,
                "in_polar_range_root": p.in_polar_range_root,
                "in_polar_range_mid":  p.in_polar_range_mid,
                "in_polar_range_tip":  p.in_polar_range_tip,
                "dT_dr_root_N_m": p.dT_dr_root_N_m,
                "dT_dr_mid_N_m":  p.dT_dr_mid_N_m,
                "dT_dr_tip_N_m":  p.dT_dr_tip_N_m,
                "thrust_kN": p.thrust_kN,
                "thrust_fraction": p.thrust_fraction,
                "eta_fan_rev": p.eta_fan_rev,
                "stall_margin_root": p.stall_margin_root,
                "stall_margin_mid":  p.stall_margin_mid,
                "stall_margin_tip":  p.stall_margin_tip,
                "stall_margin_min":  p.stall_margin_min,
                "aerodynamically_valid": p.aerodynamically_valid,
            })
        path = self._out / "tables" / "reverse_thrust_sweep.csv"
        pd.DataFrame(rows).to_csv(path, index=False, float_format="%.6f")
        return path

    def write_optimal(self, opt: ReverseOptimalResult) -> Path:
        data = {
            "metric": [
                "delta_beta_opt_deg", "beta_opt_root_deg", "beta_opt_mid_deg",
                "beta_opt_tip_deg", "thrust_net_kN", "thrust_fraction_pct",
                "eta_fan_rev", "n1_fraction", "va_landing_m_s",
                "stall_margin_min", "aerodynamically_valid",
            ],
            "value": [
                opt.delta_beta_opt_deg, opt.beta_opt_root_deg, opt.beta_opt_mid_deg,
                opt.beta_opt_tip_deg, opt.thrust_net_kN, opt.thrust_fraction * 100.0,
                opt.eta_fan_rev, opt.n1_fraction, opt.va_landing_m_s,
                opt.stall_margin_min, int(opt.aerodynamically_valid),
            ],
        }
        path = self._out / "tables" / "reverse_thrust_optimal.csv"
        pd.DataFrame(data).to_csv(path, index=False, float_format="%.4f")
        return path

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

    # ------------------------------------------------------------------
    # Figures
    # ------------------------------------------------------------------

    def write_figures(
        self,
        sweep: List[ReverseSweepPoint],
        opt: ReverseOptimalResult,
        kinematics: List[ReverseKinematicsSection],
        mw: MechanismWeightResult,
        t_forward_kN: float,
    ) -> List[Path]:
        paths = []
        with apply_style():
            paths.append(self._plot_thrust_sweep(sweep, opt, t_forward_kN))
            paths.append(self._plot_efficiency_stall(sweep, opt))
            paths.append(self._plot_spanwise(sweep, opt, kinematics))
            paths.append(self._plot_weight_comparison(mw))
        return paths

    def _plot_thrust_sweep(
        self,
        sweep: List[ReverseSweepPoint],
        opt: ReverseOptimalResult,
        t_forward_kN: float,
    ) -> Path:
        db  = [p.delta_beta_deg    for p in sweep]
        tf  = [p.thrust_fraction * 100 for p in sweep]
        rev = [p.thrust_kN < 0    for p in sweep]

        fig, ax = plt.subplots(figsize=(7, 4.5))
        ax.plot(db, tf, color="#4477AA", linewidth=2.2, label="Reverse thrust fraction")
        ax.axhspan(30, 50, alpha=0.12, color="#228833", label="Target zone 30–50%")
        ax.axvline(opt.delta_beta_opt_deg, color="#E53935", linewidth=1.5,
                   linestyle="--", label=f"Optimum Δβ = {opt.delta_beta_opt_deg:.1f}°")
        ax.scatter([opt.delta_beta_opt_deg], [opt.thrust_fraction * 100],
                   color="#E53935", zorder=5, s=60)
        ax.axhline(0, color="black", linewidth=0.8, linestyle=":")
        ax.set_xlabel(r"$\Delta\beta$ from $\beta_\mathrm{metal}$ [°]")
        ax.set_ylabel(r"$|T_\mathrm{rev}| / T_\mathrm{fwd,takeoff}$ [%]")
        ax.set_title("VPF Reverse Thrust — Pitch Sweep")
        ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", borderaxespad=0)
        ax.grid(alpha=0.3)
        path = self._out / "figures" / "thrust_vs_pitch_sweep.png"
        fig.savefig(path, bbox_inches="tight")
        plt.close(fig)
        return path

    def _plot_efficiency_stall(
        self,
        sweep: List[ReverseSweepPoint],
        opt: ReverseOptimalResult,
    ) -> Path:
        db  = [p.delta_beta_deg for p in sweep]
        eta = [p.eta_fan_rev    for p in sweep]
        sm  = [p.stall_margin_min for p in sweep]

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(7, 6), sharex=True)
        ax1.plot(db, eta, color="#4477AA", linewidth=2.0)
        ax1.axvline(opt.delta_beta_opt_deg, color="#E53935", linewidth=1.5, linestyle="--")
        ax1.set_ylabel(r"$\eta_\mathrm{fan,rev}$ [–]")
        ax1.set_title("Fan Efficiency in Reverse Mode")
        ax1.grid(alpha=0.3)

        ax2.plot(db, sm, color="#D55E00", linewidth=2.0)
        ax2.axhline(0, color="black", linewidth=0.8, linestyle="--", label="Stall boundary")
        ax2.axvline(opt.delta_beta_opt_deg, color="#E53935", linewidth=1.5, linestyle="--",
                    label=f"Optimum Δβ = {opt.delta_beta_opt_deg:.1f}°")
        ax2.set_xlabel(r"$\Delta\beta$ from $\beta_\mathrm{metal}$ [°]")
        ax2.set_ylabel("Stall margin [–]")
        ax2.set_title("Minimum Stall Margin Across Sections")
        ax2.legend(bbox_to_anchor=(1.02, 1), loc="upper left", borderaxespad=0)
        ax2.grid(alpha=0.3)

        fig.tight_layout()
        path = self._out / "figures" / "efficiency_and_stall_margin.png"
        fig.savefig(path, bbox_inches="tight")
        plt.close(fig)
        return path

    def _plot_spanwise(
        self,
        sweep: List[ReverseSweepPoint],
        opt: ReverseOptimalResult,
        kinematics: List[ReverseKinematicsSection],
    ) -> Path:
        opt_pt = next((p for p in sweep if abs(p.delta_beta_deg - opt.delta_beta_opt_deg) < 0.01), None)
        if opt_pt is None:
            opt_pt = min(sweep, key=lambda p: abs(p.delta_beta_deg - opt.delta_beta_opt_deg))

        sections = ["root", "mid_span", "tip"]
        kin_map = {k.section: k for k in kinematics}
        dT_values = [opt_pt.dT_dr_root_N_m, opt_pt.dT_dr_mid_N_m, opt_pt.dT_dr_tip_N_m]
        radii = [kin_map[s].radius_m for s in sections]

        fig, ax = plt.subplots(figsize=(6, 4.5))
        colors = [_SECTION_COLORS.get(s, "#4477AA") for s in sections]
        bars = ax.bar([_SECTION_LABELS.get(s, s) for s in sections],
                      [v / 1000 for v in dT_values],
                      color=colors, edgecolor="white", linewidth=0.6)
        ax.bar_label(bars, fmt="%.1f", padding=3, fontsize=9)
        ax.axhline(0, color="black", linewidth=0.8)
        ax.set_ylabel(r"$dT/dr$ [kN/m]")
        ax.set_title(
            f"Spanwise Thrust Distribution at Optimal Δβ = {opt.delta_beta_opt_deg:.1f}°\n"
            f"(Total reverse thrust = {opt.thrust_net_kN:.1f} kN  ·  "
            f"{opt.thrust_fraction*100:.1f}% of forward takeoff thrust)"
        )
        ax.grid(axis="y", alpha=0.3)
        path = self._out / "figures" / "spanwise_thrust_at_optimum.png"
        fig.savefig(path, bbox_inches="tight")
        plt.close(fig)
        return path

    def _plot_weight_comparison(self, mw: MechanismWeightResult) -> Path:
        labels  = ["No reverser\n(baseline)", "VPF mechanism\n(this work)", "Cascade reverser\n(conventional)"]
        weights = [0.0, mw.mechanism_weight_kg, mw.conventional_reverser_weight_kg]
        sfc_impacts = [0.0, mw.sfc_cruise_penalty_pct, mw.sfc_cruise_penalty_pct - mw.sfc_benefit_vs_conventional_pct]

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
            f"SFC benefit vs conventional: −{mw.sfc_benefit_vs_conventional_pct:.3f}%",
            fontsize=10, y=1.01,
        )
        fig.tight_layout()
        path = self._out / "figures" / "mechanism_weight_comparison.png"
        fig.savefig(path, bbox_inches="tight")
        plt.close(fig)
        return path
