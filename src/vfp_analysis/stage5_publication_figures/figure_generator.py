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
    resolve_efficiency_column,
    resolve_polar_file,
)
from vfp_analysis.stage4_performance_metrics.metrics import AerodynamicMetrics

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
# Helpers for corrected-polar figures (Figures A and B)
# ---------------------------------------------------------------------------

def _load_corrected_polar(
    stage3_dir: Path,
    condition: str,
    section: str,
) -> Optional[pd.DataFrame]:
    """Load corrected_polar.csv from the Stage 3 results folder. Returns None if missing."""
    path = stage3_dir / condition.lower() / section / "corrected_polar.csv"
    if not path.exists():
        LOGGER.warning("Corrected polar not found: %s", path)
        return None
    return pd.read_csv(path)


def _interpolate_ld_at_alpha(
    df: pd.DataFrame,
    eff_col: str,
    alpha_target: float,
) -> Optional[float]:
    """Linear interpolation of efficiency at a given alpha. Returns None if out of range."""
    df_clean = df.replace([np.inf, -np.inf], np.nan).dropna(subset=[eff_col, "alpha"])
    if df_clean.empty:
        return None
    below = df_clean[df_clean["alpha"] <= alpha_target]
    above = df_clean[df_clean["alpha"] >= alpha_target]
    if below.empty or above.empty:
        return None
    row_lo = below.iloc[-1]
    row_hi = above.iloc[0]
    if row_lo["alpha"] == row_hi["alpha"]:
        return float(row_lo[eff_col])
    t = (alpha_target - row_lo["alpha"]) / (row_hi["alpha"] - row_lo["alpha"])
    return float(row_lo[eff_col] + t * (row_hi[eff_col] - row_lo[eff_col]))


def _format_reynolds(re: float) -> str:
    """Format Reynolds number as LaTeX string, e.g. 'Re = 2.5×10⁶'."""
    exp = int(np.floor(np.log10(re)))
    coeff = re / 10 ** exp
    return rf"Re = {coeff:.1f}$\times 10^{{{exp}}}$"


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
# Figure A: Section polar comparison (efficiency + lift) per flight condition
# ---------------------------------------------------------------------------

def generate_section_polar_comparison(
    stage3_dir: Path,
    figures_dir: Path,
    flight_conditions: List[str],
    blade_sections: Optional[List[str]] = None,
) -> None:
    """
    For each flight condition, generate a dual-panel figure:
      - Left panel:  CL/CD_corrected vs α for root, mid_span, tip
      - Right panel: CL_corrected vs α for root, mid_span, tip

    The second efficiency peak (actual operating point) is marked with a
    star on each curve in both panels.
    """
    figures_dir.mkdir(parents=True, exist_ok=True)
    settings = get_plot_settings()
    w = settings["figure_size"]["width"]
    h = settings["figure_size"]["height"]
    sections = blade_sections or ["root", "mid_span", "tip"]

    for flight in flight_conditions:
        fig, (ax_eff, ax_cl) = plt.subplots(1, 2, figsize=(w * 2 + 0.5, h))
        any_plotted = False

        for section in sections:
            df = _load_corrected_polar(stage3_dir, flight, section)
            if df is None:
                continue

            try:
                eff_col = resolve_efficiency_column(df)
            except ValueError:
                LOGGER.warning("No efficiency column in %s/%s corrected polar.", flight, section)
                continue

            cl_col = "cl_corrected" if "cl_corrected" in df.columns else "cl"
            color = SECTION_COLORS.get(section, "#333333")
            section_label = section.replace("_", " ").title()

            # Locate second peak
            try:
                row_opt = find_second_peak_row(df, eff_col)
                alpha_opt = float(row_opt["alpha"])
                ld_opt = float(row_opt[eff_col])
                cl_at_opt = float(row_opt[cl_col]) if cl_col in row_opt.index else None
                has_opt = True
            except (ValueError, KeyError):
                has_opt = False
                alpha_opt = ld_opt = cl_at_opt = None

            legend_lbl = (
                rf"{section_label} ($\alpha_{{opt}}$ = {alpha_opt:.1f}°)"
                if has_opt else section_label
            )

            # --- Left: efficiency polar ---
            ax_eff.plot(df["alpha"], df[eff_col], color=color, label=legend_lbl, zorder=3)
            if has_opt:
                ax_eff.plot(
                    alpha_opt, ld_opt,
                    marker="*", color=color, markersize=11,
                    markeredgecolor="white", markeredgewidth=0.7,
                    zorder=6, linestyle="none",
                )
                ax_eff.axvline(alpha_opt, color=color, linestyle=":", linewidth=0.8, alpha=0.5)

            # --- Right: lift polar ---
            ax_cl.plot(df["alpha"], df[cl_col], color=color, label=legend_lbl, zorder=3)
            if has_opt and cl_at_opt is not None:
                ax_cl.plot(
                    alpha_opt, cl_at_opt,
                    marker="*", color=color, markersize=11,
                    markeredgecolor="white", markeredgewidth=0.7,
                    zorder=6, linestyle="none",
                )

            any_plotted = True

        if not any_plotted:
            plt.close(fig)
            continue

        ax_eff.set_xlabel(r"Angle of attack $\alpha$ [°]")
        ax_eff.set_ylabel(r"$C_L/C_D$ (Prandtl-Glauert corrected) [–]")
        ax_eff.set_title(
            f"Efficiency Polar — {flight.title()}\n"
            r"(★ = 2nd peak, actual operating point)"
        )
        ax_eff.legend(loc="lower right")

        ax_cl.set_xlabel(r"Angle of attack $\alpha$ [°]")
        ax_cl.set_ylabel(r"$C_L$ (Prandtl-Glauert corrected) [–]")
        ax_cl.set_title(
            f"Lift Polar — {flight.title()}\n"
            r"(★ = $\alpha_{opt}$ from efficiency peak)"
        )
        ax_cl.legend(loc="lower right")

        fig.suptitle(
            f"NACA 65-410 — Section Comparison — {flight.title()}",
            fontsize=11, fontweight="bold",
        )
        fig.tight_layout()
        fig.savefig(figures_dir / f"section_polar_comparison_{flight}.png")
        plt.close(fig)


# ---------------------------------------------------------------------------
# Figure B: Cruise penalty figure — central VPF thesis proof
# ---------------------------------------------------------------------------

def generate_cruise_penalty_figure(
    stage3_dir: Path,
    figures_dir: Path,
    non_cruise_conditions: Optional[List[str]] = None,
    blade_sections: Optional[List[str]] = None,
    reynolds_table: Optional[Dict[str, Dict[str, float]]] = None,
    alpha_min_second_peak: float = 3.0,
) -> None:
    """
    For each non-cruise flight condition, generate a single figure showing:
      - The efficiency polars (CL/CD_corrected vs α) for all blade sections
        (root, mid_span, tip), each with a different Re in the legend
      - A green star on each curve marking α_opt (optimal with VPF)
      - A vertical dashed red line at alpha_cruise_design (the cruise operating
        angle, derived from the actual cruise data) showing where a fixed-pitch
        blade would operate
      - A percentage annotation on the mid_span curve quantifying the
        efficiency penalty of the fixed-pitch approach

    This figure is the central visual proof of the VPF concept.
    """
    figures_dir.mkdir(parents=True, exist_ok=True)
    settings = get_plot_settings()
    w = settings["figure_size"]["width"]
    h = settings["figure_size"]["height"]

    sections = blade_sections or ["root", "mid_span", "tip"]
    conditions = non_cruise_conditions or ["takeoff", "climb", "descent"]
    re_table = reynolds_table or {}

    # --- Derive alpha_cruise_design from data (not hardcoded) ---
    alpha_cruise_design: float = _ALPHA_CRUISE_REF  # fallback
    cruise_df = _load_corrected_polar(stage3_dir, "cruise", "mid_span")
    if cruise_df is not None:
        try:
            eff_col_cr = resolve_efficiency_column(cruise_df)
            row_cr = find_second_peak_row(cruise_df, eff_col_cr, alpha_min_second_peak)
            alpha_cruise_design = float(row_cr["alpha"])
            LOGGER.info("Cruise design alpha (from data): %.2f°", alpha_cruise_design)
        except (ValueError, KeyError):
            LOGGER.warning("Could not determine cruise alpha_opt from data; using %.1f°", _ALPHA_CRUISE_REF)

    for condition in conditions:
        fig, ax = plt.subplots(figsize=(w + 1.0, h + 0.5))
        any_plotted = False
        mid_span_ld_opt: Optional[float] = None

        for section in sections:
            df = _load_corrected_polar(stage3_dir, condition, section)
            if df is None:
                continue

            try:
                eff_col = resolve_efficiency_column(df)
            except ValueError:
                continue

            color = SECTION_COLORS.get(section, "#333333")
            section_label = section.replace("_", " ").title()

            # Reynolds label for legend
            re_val = re_table.get(condition, {}).get(section)
            re_str = _format_reynolds(re_val) if re_val else ""
            curve_label = f"{section_label}  ({re_str})" if re_str else section_label

            ax.plot(df["alpha"], df[eff_col], color=color, label=curve_label, zorder=3)

            # Mark VPF optimal point
            try:
                row_opt = find_second_peak_row(df, eff_col, alpha_min_second_peak)
                alpha_opt = float(row_opt["alpha"])
                ld_opt = float(row_opt[eff_col])
                ax.plot(
                    alpha_opt, ld_opt,
                    marker="*", color="darkgreen", markersize=13,
                    markeredgecolor="white", markeredgewidth=1.0,
                    zorder=7, linestyle="none",
                    label=rf"  VPF opt. $\alpha$ = {alpha_opt:.1f}° [{section_label}]",
                )
                if section == "mid_span":
                    mid_span_ld_opt = ld_opt
                    mid_span_eff_col = eff_col
                    mid_span_df = df
            except (ValueError, KeyError):
                pass

            any_plotted = True

        if not any_plotted:
            plt.close(fig)
            continue

        # --- Fixed-pitch cruise reference line ---
        ax.axvline(
            alpha_cruise_design,
            color="#B22222",
            linestyle="--",
            linewidth=1.4,
            zorder=5,
            label=rf"Fixed-pitch cruise $\alpha_{{design}}$ = {alpha_cruise_design:.1f}°",
        )

        # --- Penalty annotation on mid_span curve ---
        if mid_span_ld_opt is not None:
            ld_at_cruise = _interpolate_ld_at_alpha(mid_span_df, mid_span_eff_col, alpha_cruise_design)
            if ld_at_cruise is not None and ld_at_cruise > 0:
                penalty_pct = 100.0 * (mid_span_ld_opt - ld_at_cruise) / mid_span_ld_opt
                eff_series = mid_span_df[mid_span_eff_col].replace([np.inf, -np.inf], np.nan).dropna()
                ld_range = float(eff_series.max() - eff_series.min()) if not eff_series.empty else 1.0
                alpha_range = float(mid_span_df["alpha"].max() - mid_span_df["alpha"].min())
                ax.annotate(
                    rf"Fixed-pitch loss $\approx${penalty_pct:.1f}%",
                    xy=(alpha_cruise_design, ld_at_cruise),
                    xytext=(alpha_cruise_design + 0.06 * alpha_range, ld_at_cruise - 0.10 * ld_range),
                    arrowprops=dict(arrowstyle="->", color="#B22222", lw=1.1),
                    fontsize=9, color="#B22222", fontweight="bold",
                    zorder=8,
                )

        ax.set_xlabel(r"Angle of attack $\alpha$ [°]")
        ax.set_ylabel(r"$C_L/C_D$ (Prandtl-Glauert corrected) [–]")
        ax.set_title(
            f"VPF Efficiency Gain — {condition.title()} Condition\n"
            r"★ = VPF optimal $\alpha$   |   $\mathbf{-\,-}$ = fixed cruise pitch (penalty)",
            pad=8,
        )
        ax.legend(loc="lower right", fontsize=8)
        fig.tight_layout()
        fig.savefig(figures_dir / f"cruise_penalty_{condition}.png")
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
    stage3_dir: Optional[Path] = None,
    reynolds_table: Optional[Dict[str, Dict[str, float]]] = None,
) -> None:
    """
    Generate all publication figures for the thesis.

    Core figures (Stages 2 polars):
      1. generate_efficiency_plots       — CL/CD vs α per case
      2. generate_efficiency_by_section  — section comparison per condition
      3. generate_alpha_opt_vs_condition — central α_opt matrix

    Extended figures (Stage 3 corrected polars, requires *stage3_dir*):
      A. generate_section_polar_comparison — efficiency + lift polars per condition
      B. generate_cruise_penalty_figure    — VPF penalty proof (central thesis fig.)
    """
    LOGGER.info("Generating efficiency plots (individual)...")
    generate_efficiency_plots(polars_dir, figures_dir, flight_conditions, blade_sections)

    LOGGER.info("Generating efficiency-by-section comparison plots...")
    generate_efficiency_by_section(polars_dir, figures_dir, flight_conditions)

    LOGGER.info("Generating alpha_opt vs condition summary plot...")
    generate_alpha_opt_vs_condition(metrics, figures_dir)

    if stage3_dir is not None and stage3_dir.is_dir():
        LOGGER.info("Generating section polar comparison figures (Figure A)...")
        generate_section_polar_comparison(
            stage3_dir, figures_dir, flight_conditions, blade_sections
        )

        LOGGER.info("Generating cruise penalty figures (Figure B)...")
        non_cruise = [c for c in flight_conditions if c != "cruise"]
        generate_cruise_penalty_figure(
            stage3_dir,
            figures_dir,
            non_cruise_conditions=non_cruise,
            blade_sections=blade_sections,
            reynolds_table=reynolds_table,
        )
    else:
        LOGGER.info("stage3_dir not provided or does not exist; skipping Figures A and B.")

    LOGGER.info("All figures generated in: %s", figures_dir)
