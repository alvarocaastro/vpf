"""
Application script for running SFC Impact Analysis.

This script orchestrates the SFC analysis stage, computing fuel consumption
improvements from aerodynamic efficiency gains enabled by Variable Pitch Fan.

Colours and rcParams are inherited from figure_generator (imported indirectly
through run_vpf_analysis). Explicit colour assignments use a two-tone palette
(baseline grey-blue / VPF green) that is consistent across the project.
"""

from __future__ import annotations

import logging
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import yaml

from vfp_analysis import config as base_config
from vfp_analysis.config_loader import get_output_dirs
# Trigger shared rcParams by importing from figure_generator
from vfp_analysis.stage5_publication_figures.figure_generator import SECTION_COLORS  # noqa: F401
from vfp_analysis.stage8_sfc_analysis.core.domain.sfc_parameters import EngineBaseline, SfcAnalysisResult
from vfp_analysis.stage8_sfc_analysis.core.services.sfc_analysis_service import (
    compute_sfc_analysis,
)
from vfp_analysis.stage8_sfc_analysis.core.services.summary_generator_service import (
    generate_sfc_summary,
)

LOGGER = logging.getLogger(__name__)

# Two-tone palette: baseline vs VPF — consistent in every SFC figure
_COLOR_BASELINE = "#4393C3"   # medium blue
_COLOR_VPF      = "#4DAC26"   # green (same as "tip" in SECTION_COLORS)


# ---------------------------------------------------------------------------
# Figure helpers
# ---------------------------------------------------------------------------

def generate_sfc_figures(
    sfc_results: list,
    figures_dir: Path,
) -> None:
    """Generate all SFC analysis figures."""
    figures_dir.mkdir(parents=True, exist_ok=True)

    _plot_sfc_vs_condition(sfc_results, figures_dir)
    _plot_sfc_reduction(sfc_results, figures_dir)
    _plot_fan_efficiency_improvement(sfc_results, figures_dir)
    _plot_efficiency_vs_sfc(sfc_results, figures_dir)


def _plot_sfc_vs_condition(sfc_results: list, figures_dir: Path) -> None:
    """Plot SFC vs flight condition (baseline vs VPF)."""
    conditions   = [r.condition for r in sfc_results]
    sfc_baseline = [r.sfc_baseline for r in sfc_results]
    sfc_new      = [r.sfc_new for r in sfc_results]

    x     = np.arange(len(conditions))
    width = 0.35

    fig, ax = plt.subplots(figsize=(7.5, 5.0))
    bars_b = ax.bar(
        x - width / 2, sfc_baseline, width,
        label="Baseline (fixed pitch)",
        color=_COLOR_BASELINE, edgecolor="white", linewidth=0.6, zorder=3,
    )
    bars_v = ax.bar(
        x + width / 2, sfc_new, width,
        label="VPF (variable pitch)",
        color=_COLOR_VPF, edgecolor="white", linewidth=0.6, zorder=3,
    )
    ax.bar_label(bars_b, fmt="%.4f", padding=3, fontsize=7)
    ax.bar_label(bars_v, fmt="%.4f", padding=3, fontsize=7)

    ax.set_xlabel("Flight Condition")
    ax.set_ylabel("Specific Fuel Consumption [lb/(lbf·hr)]")
    ax.set_title("SFC Comparison: Fixed-Pitch Baseline vs Variable Pitch Fan", pad=8)
    ax.set_xticks(x)
    ax.set_xticklabels([c.title() for c in conditions])
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(figures_dir / "sfc_vs_condition.png")
    plt.close(fig)


def _plot_sfc_reduction(sfc_results: list, figures_dir: Path) -> None:
    """Plot SFC reduction percentage vs flight condition."""
    conditions = [r.condition for r in sfc_results]
    reductions = [r.sfc_reduction_percent for r in sfc_results]

    x = np.arange(len(conditions))

    fig, ax = plt.subplots(figsize=(7.5, 5.0))
    bars = ax.bar(
        x, reductions, width=0.55,
        color=_COLOR_VPF, edgecolor="white", linewidth=0.6, zorder=3,
    )
    ax.bar_label(bars, fmt="%.2f %%", padding=3, fontsize=8, fontweight="bold")

    ax.set_xlabel("Flight Condition")
    ax.set_ylabel("SFC Reduction [%]")
    ax.set_title("SFC Reduction Achieved by Variable Pitch Fan", pad=8)
    ax.set_xticks(x)
    ax.set_xticklabels([c.title() for c in conditions])
    ax.set_ylim(bottom=0)
    fig.tight_layout()
    fig.savefig(figures_dir / "sfc_reduction_percent.png")
    plt.close(fig)


def _plot_fan_efficiency_improvement(sfc_results: list, figures_dir: Path) -> None:
    """Plot fan efficiency improvement vs flight condition."""
    conditions   = [r.condition for r in sfc_results]
    fan_baseline = [r.fan_efficiency_baseline * 100 for r in sfc_results]
    fan_new      = [r.fan_efficiency_new * 100 for r in sfc_results]

    x     = np.arange(len(conditions))
    width = 0.35

    fig, ax = plt.subplots(figsize=(7.5, 5.0))
    bars_b = ax.bar(
        x - width / 2, fan_baseline, width,
        label="Baseline (fixed pitch)",
        color=_COLOR_BASELINE, edgecolor="white", linewidth=0.6, zorder=3,
    )
    bars_v = ax.bar(
        x + width / 2, fan_new, width,
        label="VPF (variable pitch)",
        color=_COLOR_VPF, edgecolor="white", linewidth=0.6, zorder=3,
    )
    ax.bar_label(bars_b, fmt="%.1f %%", padding=3, fontsize=7)
    ax.bar_label(bars_v, fmt="%.1f %%", padding=3, fontsize=7)

    ax.set_xlabel("Flight Condition")
    ax.set_ylabel("Fan Isentropic Efficiency [%]")
    ax.set_title("Fan Efficiency: Fixed-Pitch Baseline vs Variable Pitch Fan", pad=8)
    ax.set_xticks(x)
    ax.set_xticklabels([c.title() for c in conditions])
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(figures_dir / "fan_efficiency_improvement.png")
    plt.close(fig)


def _plot_efficiency_vs_sfc(sfc_results: list, figures_dir: Path) -> None:
    """Scatter: aerodynamic efficiency (CL/CD) vs SFC — shows the inverse relationship."""
    cl_cd_vpf  = [r.cl_cd_vpf for r in sfc_results]
    sfc_new    = [r.sfc_new for r in sfc_results]
    conditions = [r.condition for r in sfc_results]

    cond_colors = ["#E31A1C", "#FF7F00", "#1F78B4", "#6A3D9A"]

    fig, ax = plt.subplots(figsize=(6.5, 5.0))
    for i, condition in enumerate(conditions):
        color = cond_colors[i % len(cond_colors)]
        ax.scatter(
            cl_cd_vpf[i], sfc_new[i],
            s=120, color=color, edgecolors="white", linewidths=0.8,
            label=condition.title(), zorder=4,
        )
        ax.annotate(
            condition.title(),
            (cl_cd_vpf[i], sfc_new[i]),
            xytext=(6, 4),
            textcoords="offset points",
            fontsize=8,
        )

    ax.set_xlabel(r"Aerodynamic lift-to-drag ratio $C_L/C_D$ [–]")
    ax.set_ylabel("Specific Fuel Consumption [lb/(lbf·hr)]")
    ax.set_title(
        r"$C_L/C_D$ vs Specific Fuel Consumption — VPF Operating Points", pad=8
    )
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(figures_dir / "efficiency_vs_sfc.png")
    plt.close(fig)


# ---------------------------------------------------------------------------
# I/O helpers (inlined from removed adapter classes)
# ---------------------------------------------------------------------------

def _write_sfc_table(sfc_results: list, output_path: Path) -> None:
    """Write SFC analysis results to CSV."""
    rows = [
        {
            "condition": r.condition,
            "CL_CD_baseline": r.cl_cd_baseline,
            "CL_CD_vpf": r.cl_cd_vpf,
            "fan_efficiency_baseline": r.fan_efficiency_baseline,
            "fan_efficiency_new": r.fan_efficiency_new,
            "SFC_baseline": r.sfc_baseline,
            "SFC_new": r.sfc_new,
            "SFC_reduction_percent": r.sfc_reduction_percent,
        }
        for r in sfc_results
    ]
    df = pd.DataFrame(rows).sort_values("condition")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, float_format="%.6f")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_sfc_analysis() -> None:
    """Execute the complete SFC impact analysis stage."""
    LOGGER.info("=" * 70)
    LOGGER.info("STAGE 8: Specific Fuel Consumption (SFC) Impact Analysis")
    LOGGER.info("=" * 70)

    output_dirs      = get_output_dirs()
    stage8_dir       = base_config.get_stage_dir(8)
    stage8_dir.mkdir(parents=True, exist_ok=True)

    stage6_dir       = base_config.get_stage_dir(6)
    optimal_pitch_dir = stage6_dir / "tables"
    tables_dir       = output_dirs["tables_sfc"]
    figures_sfc_dir  = output_dirs["figures_sfc"]

    # Step 1: Load aerodynamic results
    LOGGER.info("Loading aerodynamic performance data...")
    optimal_pitch_path = optimal_pitch_dir / "vpf_optimal_pitch.csv"
    if not optimal_pitch_path.exists():
        LOGGER.warning("No optimal pitch data found. Skipping SFC analysis.")
        return
    optimal_pitch_df = pd.read_csv(optimal_pitch_path)
    LOGGER.info("Loaded %d optimal pitch records", len(optimal_pitch_df))

    # Step 2: Load engine baseline
    LOGGER.info("Loading engine baseline parameters...")
    engine_config_path = base_config.ROOT_DIR / "config" / "engine_parameters.yaml"
    with engine_config_path.open("r", encoding="utf-8") as f:
        _cfg = yaml.safe_load(f)
    engine_baseline = EngineBaseline(
        baseline_sfc=_cfg["baseline_sfc"],
        fan_efficiency=_cfg["fan_efficiency"],
        bypass_ratio=_cfg["bypass_ratio"],
        cruise_velocity=_cfg["cruise_velocity"],
        jet_velocity=_cfg["jet_velocity"],
    )
    LOGGER.info("Baseline SFC: %.4f lb/(lbf·hr)", engine_baseline.baseline_sfc)

    # Step 3: Compute SFC improvement
    LOGGER.info("Computing SFC improvements...")
    sfc_results = compute_sfc_analysis(optimal_pitch_df, engine_baseline, engine_config_path)
    LOGGER.info("Computed SFC analysis for %d conditions", len(sfc_results))

    # Step 4: Generate figures
    LOGGER.info("Generating SFC analysis figures...")
    generate_sfc_figures(sfc_results, figures_sfc_dir)

    # Step 5: Write results
    LOGGER.info("Writing SFC analysis results...")
    _write_sfc_table(sfc_results, tables_dir / "sfc_analysis.csv")
    summary_text = generate_sfc_summary(sfc_results)
    sfc_summary_path = output_dirs["sfc_analysis_summary"]
    sfc_summary_path.parent.mkdir(parents=True, exist_ok=True)
    sfc_summary_path.write_text(summary_text, encoding="utf-8")

    # Step 6: Stage summary
    from vfp_analysis.postprocessing.stage_summary_generator import (
        generate_stage8_summary,
        write_stage_summary,
    )
    stage8_summary = generate_stage8_summary(stage8_dir)
    write_stage_summary(8, stage8_summary, stage8_dir)
    LOGGER.info("Stage 8 summary written to: %s", stage8_dir / "finalresults_stage8.txt")

    LOGGER.info("=" * 70)
    LOGGER.info("Stage 8 completed successfully.")
    LOGGER.info("  Tables:  %s", tables_dir)
    LOGGER.info("  Figures: %s", figures_sfc_dir)
    LOGGER.info("=" * 70)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    run_sfc_analysis()
