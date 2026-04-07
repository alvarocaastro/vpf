"""
Application script for running Variable Pitch Fan analysis.

This script orchestrates the VPF analysis stage, computing optimal incidence
angles and pitch adjustments from previous aerodynamic simulation results.

Colours and rcParams are inherited from figure_generator (imported at module
level) so that all VPF figures are visually consistent with the core plots.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from vfp_analysis import config as base_config
from vfp_analysis.config_loader import get_output_dirs
# Import shared palette — this also triggers the rcParams update in figure_generator
from vfp_analysis.postprocessing.figure_generator import SECTION_COLORS
from vfp_analysis.vpf_analysis.adapters.filesystem.data_loader_adapter import (
    FilesystemDataLoader,
)
from vfp_analysis.vpf_analysis.adapters.filesystem.results_writer_adapter import (
    FilesystemVpfResultsWriter,
)
from vfp_analysis.vpf_analysis.core.services.optimal_incidence_service import (
    compute_all_optimal_incidences,
)
from vfp_analysis.vpf_analysis.core.services.pitch_adjustment_service import (
    compute_pitch_adjustments,
)
from vfp_analysis.vpf_analysis.core.services.summary_generator_service import (
    generate_analysis_summary,
)

LOGGER = logging.getLogger(__name__)

_SECTIONS: List[str] = ["root", "mid_span", "tip"]


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _build_condition_section_table(
    items: list,
    value_attr: str,
) -> Dict[str, Dict[str, float]]:
    """Build a ``{condition: {section: value}}`` lookup from a list of dataclass items."""
    table: Dict[str, Dict[str, float]] = {}
    for item in items:
        table.setdefault(item.condition, {})[item.section] = getattr(item, value_attr)
    return table


def _plot_grouped_bars(
    ax: plt.Axes,
    data: Dict[str, Dict[str, float]],
    conditions: List[str],
    sections: List[str],
    zero_line: bool = False,
) -> None:
    """Render grouped bar chart on *ax* using the shared section colour palette."""
    x     = np.arange(len(conditions))
    width = 0.22

    for i, section in enumerate(sections):
        values = [data.get(cond, {}).get(section, np.nan) for cond in conditions]
        color  = SECTION_COLORS[section]
        bars   = ax.bar(
            x + i * width,
            values,
            width,
            label=section.replace("_", " ").title(),
            color=color,
            edgecolor="white",
            linewidth=0.6,
            zorder=3,
        )
        ax.bar_label(bars, fmt="%.2f°", padding=3, fontsize=8)

    if zero_line:
        ax.axhline(0, color="0.35", linestyle="--", linewidth=0.9)

    n_sections = len(sections)
    ax.set_xticks(x + width * (n_sections - 1) / 2)
    ax.set_xticklabels([c.title() for c in conditions])
    ax.legend(loc="lower right")


# ---------------------------------------------------------------------------
# Figure functions
# ---------------------------------------------------------------------------

def generate_vpf_figures(
    optimal_incidences: list,
    pitch_adjustments: list,
    df_polars: pd.DataFrame,
    figures_dir: Path,
) -> None:
    """Generate all VPF analysis figures."""
    figures_dir.mkdir(parents=True, exist_ok=True)

    _plot_alpha_opt_vs_condition(optimal_incidences, figures_dir)
    _plot_pitch_adjustment(pitch_adjustments, figures_dir)
    _plot_efficiency_curves_with_optimum(df_polars, optimal_incidences, figures_dir)
    _plot_section_comparison(optimal_incidences, figures_dir)


def _plot_alpha_opt_vs_condition(optimal_incidences: list, figures_dir: Path) -> None:
    """Plot optimal angle of attack per flight condition, grouped by blade section."""
    data       = _build_condition_section_table(optimal_incidences, "alpha_opt")
    conditions = sorted(data.keys())

    fig, ax = plt.subplots(figsize=(7.5, 5.0))
    _plot_grouped_bars(ax, data, conditions, _SECTIONS)
    ax.set_xlabel("Flight Condition")
    ax.set_ylabel(r"Optimal angle of attack $\alpha_{opt}$ [°]")
    ax.set_title("Optimal Angle of Attack by Flight Condition", pad=8)
    fig.tight_layout()
    fig.savefig(figures_dir / "vpf_alpha_opt_vs_condition.png")
    plt.close(fig)


def _plot_pitch_adjustment(pitch_adjustments: list, figures_dir: Path) -> None:
    """Plot required pitch adjustment relative to cruise per condition."""
    data       = _build_condition_section_table(pitch_adjustments, "delta_pitch")
    conditions = sorted(data.keys())

    fig, ax = plt.subplots(figsize=(7.5, 5.0))
    _plot_grouped_bars(ax, data, conditions, _SECTIONS, zero_line=True)
    ax.set_xlabel("Flight Condition")
    ax.set_ylabel(r"Required pitch adjustment $\Delta\alpha$ [°]")
    ax.set_title("Required Pitch Adjustment Relative to Cruise", pad=8)
    fig.tight_layout()
    fig.savefig(figures_dir / "vpf_pitch_adjustment.png")
    plt.close(fig)


def _plot_efficiency_curves_with_optimum(
    df_polars: pd.DataFrame,
    optimal_incidences: list,
    figures_dir: Path,
) -> None:
    """Plot efficiency curves with optimal operating points highlighted."""
    opt_lookup: Dict[tuple, tuple] = {
        (inc.condition, inc.section): (inc.alpha_opt, inc.cl_cd_max)
        for inc in optimal_incidences
    }

    # Determine efficiency column (prefer CL_CD, fallback to ld)
    eff_col: str | None = None
    for candidate in ("CL_CD", "ld"):
        if candidate in df_polars.columns:
            eff_col = candidate
            break

    if eff_col is None:
        LOGGER.warning("No efficiency column found in polar data — skipping efficiency curves.")
        return

    for condition in df_polars["condition"].unique():
        df_cond = df_polars[df_polars["condition"] == condition]

        fig, ax = plt.subplots(figsize=(7.5, 5.0))

        for section in _SECTIONS:
            df_section = df_cond[df_cond["section"] == section]
            if df_section.empty:
                continue

            color = SECTION_COLORS[section]
            ax.plot(
                df_section["alpha"],
                df_section[eff_col],
                color=color,
                label=section.replace("_", " ").title(),
                zorder=3,
            )

            key = (condition, section)
            if key in opt_lookup:
                alpha_opt, eff_max = opt_lookup[key]
                ax.plot(
                    alpha_opt, eff_max,
                    marker="*",
                    color=color,
                    markersize=12,
                    markeredgecolor="white",
                    markeredgewidth=0.6,
                    zorder=5,
                    linestyle="none",
                )

        ax.set_xlabel(r"Angle of attack $\alpha$ [°]")
        ax.set_ylabel(r"Lift-to-drag ratio $C_L/C_D$ [–]")
        ax.set_title(
            f"Efficiency Curves with Optimal Points — {condition.title()}", pad=8
        )
        ax.legend(loc="lower right")
        fig.tight_layout()
        fig.savefig(figures_dir / f"vpf_efficiency_curves_{condition}.png")
        plt.close(fig)


def _plot_section_comparison(optimal_incidences: list, figures_dir: Path) -> None:
    """Plot optimal angle comparison across blade sections for each condition."""
    conditions = sorted(set(inc.condition for inc in optimal_incidences))

    # Invert structure to {section: {condition: alpha_opt}}
    by_section: Dict[str, Dict[str, float]] = {}
    for inc in optimal_incidences:
        by_section.setdefault(inc.section, {})[inc.condition] = inc.alpha_opt

    fig, ax = plt.subplots(figsize=(7.5, 5.0))
    x     = np.arange(len(_SECTIONS))
    width = 0.18

    cond_colors = ["#E31A1C", "#FF7F00", "#1F78B4", "#6A3D9A"]
    for i, condition in enumerate(conditions):
        values = [by_section.get(section, {}).get(condition, np.nan) for section in _SECTIONS]
        color  = cond_colors[i % len(cond_colors)]
        bars   = ax.bar(x + i * width, values, width, label=condition.title(),
                        color=color, edgecolor="white", linewidth=0.6, zorder=3)
        ax.bar_label(bars, fmt="%.1f°", padding=3, fontsize=7)

    ax.set_xlabel("Blade Section")
    ax.set_ylabel(r"Optimal angle of attack $\alpha_{opt}$ [°]")
    ax.set_title("Optimal Angle of Attack by Blade Section", pad=8)
    ax.set_xticks(x + width * (len(conditions) - 1) / 2)
    ax.set_xticklabels([s.replace("_", " ").title() for s in _SECTIONS])
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(figures_dir / "vpf_section_comparison.png")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_vpf_analysis() -> None:
    """Execute the complete VPF analysis stage."""
    LOGGER.info("=" * 70)
    LOGGER.info("STAGE 6: Variable Pitch Fan Aerodynamic Analysis")
    LOGGER.info("=" * 70)

    output_dirs      = get_output_dirs()
    polars_dir       = output_dirs["polars"]
    compressibility_dir = output_dirs["compressibility"]
    tables_dir       = output_dirs["tables"]
    figures_vpf_dir  = output_dirs["figures_vpf"]
    stage6_dir       = base_config.RESULTS_DIR / "stage_6"
    stage6_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Load data
    LOGGER.info("Loading aerodynamic data...")
    loader     = FilesystemDataLoader()
    df_polars  = loader.load_polar_data(polars_dir)
    df_corrected = loader.load_compressibility_data(compressibility_dir)

    if df_polars.empty:
        LOGGER.warning("No polar data found. Skipping VPF analysis.")
        return

    LOGGER.info("Loaded %d polar data points", len(df_polars))
    if not df_corrected.empty:
        LOGGER.info("Loaded %d corrected data points", len(df_corrected))

    # Step 2: Compute optimal incidence
    LOGGER.info("Computing optimal incidence angles...")
    optimal_incidences = compute_all_optimal_incidences(df_polars, df_corrected)
    LOGGER.info("Computed optimal incidence for %d cases", len(optimal_incidences))

    # Step 3: Compute pitch adjustments
    LOGGER.info("Computing pitch adjustments relative to cruise...")
    pitch_adjustments = compute_pitch_adjustments(
        optimal_incidences, reference_condition="cruise"
    )
    LOGGER.info("Computed pitch adjustments for %d cases", len(pitch_adjustments))

    # Step 4: Generate figures
    LOGGER.info("Generating VPF analysis figures...")
    generate_vpf_figures(optimal_incidences, pitch_adjustments, df_polars, figures_vpf_dir)

    # Step 5: Write results tables
    LOGGER.info("Writing analysis results...")
    writer = FilesystemVpfResultsWriter()
    writer.write_optimal_pitch_table(
        optimal_incidences, tables_dir / "vpf_optimal_pitch.csv"
    )
    writer.write_pitch_adjustment_table(
        pitch_adjustments, tables_dir / "vpf_pitch_adjustment.csv"
    )

    # Step 6: Write summaries
    vpf_summary = generate_analysis_summary(optimal_incidences, pitch_adjustments)
    writer.write_analysis_summary(vpf_summary, output_dirs["vpf_analysis_summary"])

    from vfp_analysis.postprocessing.stage_summary_generator import (
        generate_stage6_summary,
        write_stage_summary,
    )
    stage6_summary = generate_stage6_summary(stage6_dir)
    write_stage_summary(6, stage6_summary, stage6_dir)
    LOGGER.info("Stage 6 summary written to: %s", stage6_dir / "finalresults_stage6.txt")

    LOGGER.info("=" * 70)
    LOGGER.info("Stage 6 completed successfully.")
    LOGGER.info("  Tables:  %s", tables_dir)
    LOGGER.info("  Figures: %s", figures_vpf_dir)
    LOGGER.info("=" * 70)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    run_vpf_analysis()
