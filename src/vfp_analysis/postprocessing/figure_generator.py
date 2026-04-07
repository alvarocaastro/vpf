"""
Figure generation for thesis publication.

This module generates the core publication-quality figures for the VPF analysis.
Low-value individual plots (CL-α, CD-α, polar per section) have been removed;
only the three figures that directly support the thesis hypothesis are retained:

  1. generate_efficiency_plots       — CL/CD vs α with α_opt marked (one per case)
  2. generate_efficiency_by_section  — section comparison per flight condition
  3. generate_alpha_opt_vs_condition — central thesis figure: α_opt matrix

A unified academic rcParams block is applied at import time so that VPF and
SFC figures (which import _SECTION_COLORS from here) inherit consistent styling.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from vfp_analysis.config_loader import get_plot_settings
from vfp_analysis.postprocessing.aerodynamics_utils import (
    find_second_peak_row,
    resolve_polar_file,
)
from vfp_analysis.postprocessing.metrics import AerodynamicMetrics

LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Academic style — applied once at import time
# ---------------------------------------------------------------------------

# Three-section colour palette: consistent across ALL figures in the project.
# Import this constant in vpf/sfc modules instead of defining local colours.
SECTION_COLORS: Dict[str, str] = {
    "root":     "#2166AC",  # blue
    "mid_span": "#D6604D",  # red-orange
    "tip":      "#4DAC26",  # green
}

# Flight-condition colour palette (used in by-section comparison and alpha-opt)
CONDITION_COLORS: Dict[str, str] = {
    "takeoff": "#E31A1C",   # red
    "climb":   "#FF7F00",   # orange
    "cruise":  "#1F78B4",   # blue  (reference condition)
    "descent": "#6A3D9A",   # purple
}

_ACADEMIC_STYLE: Dict = {
    # Typography
    "font.family":       "serif",
    "font.serif":        ["DejaVu Serif", "Times New Roman", "Palatino", "serif"],
    "font.size":         10,
    # Axes
    "axes.titlesize":    12,
    "axes.titleweight":  "bold",
    "axes.labelsize":    10,
    "axes.labelweight":  "normal",
    "axes.spines.top":   False,
    "axes.spines.right": False,
    # Ticks
    "xtick.labelsize":   9,
    "ytick.labelsize":   9,
    "xtick.direction":   "in",
    "ytick.direction":   "in",
    # Grid
    "axes.grid":         True,
    "grid.linestyle":    ":",
    "grid.linewidth":    0.5,
    "grid.alpha":        0.65,
    # Legend
    "legend.fontsize":   9,
    "legend.framealpha": 0.85,
    "legend.edgecolor":  "0.6",
    # Lines
    "lines.linewidth":   1.8,
    "lines.markersize":  5,
    # Save
    "savefig.dpi":       300,
    "savefig.bbox":      "tight",
    # Colour cycle (matches SECTION_COLORS ordering for single-series plots)
    "axes.prop_cycle":   mpl.cycler(color=[
        "#2166AC",  # blue  (root / primary)
        "#D6604D",  # red-orange (mid_span / secondary)
        "#4DAC26",  # green (tip / tertiary)
        "#762A83",  # purple (fourth)
    ]),
}

mpl.rcParams.update(_ACADEMIC_STYLE)

# Cruise reference angle — drawn on summary plots so the reader can see the gap
_ALPHA_CRUISE_REF: float = 5.0   # adjust if your cruise α_opt differs


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _alpha_cruise_reference(ax: plt.Axes, alpha_val: float = _ALPHA_CRUISE_REF) -> None:
    """Draw a thin dashed reference line at the cruise reference angle."""
    ax.axvline(
        alpha_val,
        color="0.45",
        linestyle="--",
        linewidth=0.9,
        alpha=0.7,
        label=rf"Cruise ref. $\alpha$ = {alpha_val:.1f}°",
        zorder=2,
    )


def _smart_annotation(
    ax: plt.Axes,
    x: float,
    y: float,
    label: str,
    x_range: float,
    y_range: float,
) -> None:
    """Annotate (x, y) with an offset computed relative to axis data range."""
    dx = 0.06 * x_range   # 6 % of horizontal range
    dy = 0.06 * y_range   # 6 % of vertical range
    ax.annotate(
        label,
        xy=(x, y),
        xytext=(x + dx, y + dy),
        arrowprops=dict(
            arrowstyle="->",
            color="#B22222",
            lw=1.2,
        ),
        fontsize=9,
        fontweight="bold",
        color="#B22222",
        zorder=7,
    )


# ---------------------------------------------------------------------------
# Figure 1: CL/CD vs α — individual per case, α_opt marked
# ---------------------------------------------------------------------------

def generate_efficiency_plots(
    polars_dir: Path,
    figures_dir: Path,
    flight_conditions: List[str],
    blade_sections: List[str],
) -> None:
    """
    Generate CL/CD vs α plots for every (condition, section) pair.

    Each plot marks the optimal operating point (second peak) with a bold
    marker and a smart annotation, and draws a cruise reference line so
    the reader can immediately see the gap between α_cruise and α_opt.
    """
    figures_dir.mkdir(parents=True, exist_ok=True)
    settings = get_plot_settings()
    w = settings["figure_size"]["width"]
    h = settings["figure_size"]["height"]

    for flight in flight_conditions:
        for section in blade_sections:
            polar_file = resolve_polar_file(polars_dir, flight, section)
            if polar_file is None:
                continue

            df = pd.read_csv(polar_file)

            # Locate optimal point (second peak)
            try:
                row_opt = find_second_peak_row(df, "ld")
                alpha_opt = float(row_opt["alpha"])
                ld_max    = float(row_opt["ld"])
                has_opt   = True
            except (ValueError, KeyError):
                has_opt   = False
                alpha_opt = float("nan")
                ld_max    = float("nan")

            fig, ax = plt.subplots(figsize=(w, h))

            color = SECTION_COLORS.get(section, "#2166AC")
            ax.plot(
                df["alpha"],
                df["ld"],
                color=color,
                label=r"$C_L/C_D$",
                zorder=3,
            )

            if has_opt:
                # Optimal point marker
                ax.plot(
                    alpha_opt, ld_max,
                    marker="*",
                    color="#B22222",
                    markersize=12,
                    markeredgecolor="darkred",
                    markeredgewidth=0.8,
                    zorder=6,
                    linestyle="none",
                )
                ax.axvline(
                    alpha_opt,
                    color="#B22222",
                    linestyle="--",
                    linewidth=0.9,
                    alpha=0.75,
                    zorder=4,
                )
                # Adaptive annotation
                alpha_range = float(df["alpha"].max() - df["alpha"].min())
                ld_range    = float(df["ld"].replace([np.inf, -np.inf], np.nan).dropna().max()
                                    - df["ld"].replace([np.inf, -np.inf], np.nan).dropna().min())
                _smart_annotation(
                    ax, alpha_opt, ld_max,
                    rf"$\alpha_{{opt}}$ = {alpha_opt:.1f}°",
                    alpha_range, ld_range,
                )

            ax.set_xlabel(r"Angle of attack $\alpha$ [°]")
            ax.set_ylabel(r"Lift-to-drag ratio $C_L/C_D$ [–]")
            section_label = section.replace("_", " ").title()
            ax.set_title(
                f"Aerodynamic Efficiency — {flight.title()} / {section_label}"
            )
            ax.legend(loc="lower right")
            fig.tight_layout()
            fig.savefig(figures_dir / f"efficiency_{flight}_{section}.png")
            plt.close(fig)


# ---------------------------------------------------------------------------
# Figure 2: Section comparison — CL/CD curves overlaid per flight condition
# ---------------------------------------------------------------------------

def generate_efficiency_by_section(
    polars_dir: Path,
    figures_dir: Path,
    flight_conditions: List[str],
    alpha_cruise_ref: float = _ALPHA_CRUISE_REF,
) -> None:
    """
    Generate CL/CD vs α plots comparing root, mid_span and tip for each
    flight condition.

    Each section's α_opt is included in the legend label so the reader can
    directly compare optimal operating points across sections.
    """
    figures_dir.mkdir(parents=True, exist_ok=True)
    settings = get_plot_settings()
    w = settings["figure_size"]["width"]
    h = settings["figure_size"]["height"]

    sections = ["root", "mid_span", "tip"]

    for flight in flight_conditions:
        fig, ax = plt.subplots(figsize=(w, h))
        plotted = False

        for section in sections:
            polar_file = resolve_polar_file(polars_dir, flight, section)
            if polar_file is None:
                continue

            df = pd.read_csv(polar_file)
            color = SECTION_COLORS[section]

            # Determine α_opt for legend label
            try:
                row_opt  = find_second_peak_row(df, "ld")
                alpha_opt = float(row_opt["alpha"])
                ld_max    = float(row_opt["ld"])
                legend_label = (
                    rf"{section.replace('_', ' ').title()} "
                    rf"($\alpha_{{opt}}$ = {alpha_opt:.1f}°)"
                )
            except (ValueError, KeyError):
                alpha_opt = None
                legend_label = section.replace("_", " ").title()

            ax.plot(
                df["alpha"],
                df["ld"],
                color=color,
                label=legend_label,
                zorder=3,
            )

            # Mark α_opt on each curve
            if alpha_opt is not None:
                ax.plot(
                    alpha_opt, ld_max,
                    marker="*",
                    color=color,
                    markersize=10,
                    markeredgecolor="white",
                    markeredgewidth=0.6,
                    zorder=5,
                    linestyle="none",
                )

            plotted = True

        if not plotted:
            plt.close(fig)
            continue

        # Cruise reference
        _alpha_cruise_reference(ax, alpha_cruise_ref)

        ax.set_xlabel(r"Angle of attack $\alpha$ [°]")
        ax.set_ylabel(r"Lift-to-drag ratio $C_L/C_D$ [–]")
        ax.set_title(f"Efficiency by Blade Section — {flight.title()}")
        ax.legend(loc="lower right")
        fig.tight_layout()
        fig.savefig(figures_dir / f"efficiency_by_section_{flight}.png")
        plt.close(fig)


# ---------------------------------------------------------------------------
# Figure 3: α_opt matrix — central thesis figure
# ---------------------------------------------------------------------------

def generate_alpha_opt_vs_condition(
    metrics: List[AerodynamicMetrics],
    figures_dir: Path,
    alpha_cruise_ref: float = _ALPHA_CRUISE_REF,
) -> None:
    """
    Generate the central thesis figure: optimal angle of attack grouped by
    flight condition and blade section.

    A horizontal dashed line at the cruise reference angle makes it
    immediately visible that the fixed-pitch cruise setting is not optimal
    for other flight conditions. Bar labels show the exact α_opt value.
    """
    figures_dir.mkdir(parents=True, exist_ok=True)
    settings = get_plot_settings()
    w = settings["figure_size"]["width"]
    h = settings["figure_size"]["height"]

    # Build lookup: {condition: {section: alpha_opt}}
    data: Dict[str, Dict[str, float]] = {}
    for m in metrics:
        data.setdefault(m.flight_condition, {})[m.blade_section] = m.alpha_opt

    flight_conditions = sorted(data.keys(), key=lambda c: ["takeoff", "climb", "cruise", "descent"].index(c)
                                if c in ["takeoff", "climb", "cruise", "descent"] else 99)
    sections = ["root", "mid_span", "tip"]

    fig, ax = plt.subplots(figsize=(w + 1.5, h))  # slightly wider for labels
    x     = np.arange(len(flight_conditions))
    width = 0.22

    for i, section in enumerate(sections):
        values = [data[fc].get(section, np.nan) for fc in flight_conditions]
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
        # Value labels on each bar
        ax.bar_label(bars, fmt="%.1f°", padding=3, fontsize=8, fontweight="bold")

    # Cruise reference line
    ax.axhline(
        alpha_cruise_ref,
        color="0.35",
        linestyle="--",
        linewidth=1.0,
        label=rf"Cruise ref. $\alpha$ = {alpha_cruise_ref:.1f}°",
        zorder=2,
    )

    ax.set_xlabel("Flight Condition")
    ax.set_ylabel(r"Optimal angle of attack $\alpha_{opt}$ [°]")
    ax.set_title(
        r"Optimal Angle of Attack by Flight Condition — Key Thesis Result",
        pad=10,
    )
    ax.set_xticks(x + width)
    ax.set_xticklabels([fc.title() for fc in flight_conditions])
    ax.legend(loc="lower right")
    ax.set_ylim(bottom=0)
    fig.tight_layout()
    fig.savefig(figures_dir / "alpha_opt_vs_condition.png")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def generate_all_figures(
    polars_dir: Path,
    figures_dir: Path,
    metrics: List[AerodynamicMetrics],
    flight_conditions: List[str],
    blade_sections: List[str],
) -> None:
    """
    Generate the three core publication figures for the thesis.

    Removed from earlier version (low informational value):
      - generate_cl_vs_alpha_plots   (12 individual CL-α plots)
      - generate_cd_vs_alpha_plots   (12 individual CD-α plots)
      - generate_polar_plots         (12 individual CL-CD polars)
      - generate_efficiency_vs_reynolds (redundant with by-section)
    """
    LOGGER.info("Generating efficiency plots (individual)...")
    generate_efficiency_plots(polars_dir, figures_dir, flight_conditions, blade_sections)

    LOGGER.info("Generating efficiency-by-section comparison plots...")
    generate_efficiency_by_section(polars_dir, figures_dir, flight_conditions)

    LOGGER.info("Generating alpha_opt vs condition summary plot...")
    generate_alpha_opt_vs_condition(metrics, figures_dir)

    LOGGER.info("All figures generated in: %s", figures_dir)
