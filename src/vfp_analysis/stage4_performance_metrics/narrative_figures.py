"""Narrative figures for VPF thesis: pitch requirement and fixed vs variable pitch comparison."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

import matplotlib.pyplot as plt
import pandas as pd

from vfp_analysis.shared.plot_style import apply_style

# Paul Tol colorblind-safe palette
_SECTION_COLORS = {
    "root":     "#4477AA",
    "mid_span": "#EE6677",
    "tip":      "#228833",
}

_CONDITION_ORDER = ["takeoff", "climb", "cruise", "descent"]
_CONDITION_LABELS = {
    "takeoff": "Takeoff",
    "climb":   "Climb",
    "cruise":  "Cruise",
    "descent": "Descent",
}


def generate_pitch_requirement_figure(pitch_map_csv: Path, output_dir: Path) -> Path:
    """Two-panel figure: α_opt and Δβ_mech vs flight condition per section.

    Top panel  — α_opt vs condition, one line per section, cruise reference dashed.
    Bottom panel — Δβ_mech = β_deg − β_cruise[section] vs condition, shaded actuation band.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(pitch_map_csv)
    sections = [s for s in ["root", "mid_span", "tip"] if s in df["section"].unique()]
    conditions = [c for c in _CONDITION_ORDER if c in df["flight"].unique()]

    # Cruise reference angles (β at cruise per section)
    cruise_beta: Dict[str, float] = {}
    cruise_alpha: Optional[float] = None
    cruise_rows = df[df["flight"] == "cruise"]
    for section in sections:
        row = cruise_rows[cruise_rows["section"] == section]
        if not row.empty:
            cruise_beta[section] = float(row["beta_deg"].iloc[0])
            if section == "mid_span" and cruise_alpha is None:
                cruise_alpha = float(row["alpha_opt"].iloc[0])

    condition_labels = [_CONDITION_LABELS.get(c, c) for c in conditions]
    x = range(len(conditions))

    with apply_style():
        fig, (ax_top, ax_bot) = plt.subplots(2, 1, figsize=(6.5, 6.0), sharex=True)

        # ── Top panel: α_opt vs condition ──────────────────────────────────
        for section in sections:
            rows = df[df["section"] == section].set_index("flight")
            y = [float(rows.loc[c, "alpha_opt"]) if c in rows.index else float("nan")
                 for c in conditions]
            ax_top.plot(x, y, marker="o", color=_SECTION_COLORS.get(section, "#999999"),
                        label=section.replace("_", " ").title(), linewidth=1.8, markersize=5)

        if cruise_alpha is not None:
            ax_top.axhline(cruise_alpha, color="#999999", linestyle="--", linewidth=1.2,
                           alpha=0.8, zorder=3)
            ax_top.annotate("Fixed-pitch design point",
                            xy=(len(conditions) - 1, cruise_alpha),
                            xytext=(-80, 8), textcoords="offset points",
                            fontsize=7.5, color="#666666",
                            arrowprops=dict(arrowstyle="->", color="#999999", lw=0.8))

        ax_top.set_ylabel(r"$\alpha_{opt}$ [°]")
        ax_top.set_title("Optimal angle of attack per flight condition")
        ax_top.legend(loc="upper right", fontsize=8)

        # ── Bottom panel: Δβ_mech vs condition ─────────────────────────────
        delta_values: list[list[float]] = []
        for section in sections:
            rows = df[df["section"] == section].set_index("flight")
            ref = cruise_beta.get(section, 0.0)
            deltas = [float(rows.loc[c, "beta_deg"]) - ref if c in rows.index else float("nan")
                      for c in conditions]
            delta_values.append(deltas)
            ax_bot.plot(x, deltas, marker="s", color=_SECTION_COLORS.get(section, "#999999"),
                        label=section.replace("_", " ").title(), linewidth=1.8, markersize=5)

        ax_bot.axhline(0, color="#999999", linestyle="--", linewidth=1.2, alpha=0.8)

        # Shaded band = full actuation range across all sections
        all_deltas = [v for row in delta_values for v in row if not pd.isna(v)]
        if all_deltas:
            d_min, d_max = min(all_deltas), max(all_deltas)
            for xi in x:
                pt_deltas = [row[xi] for row in delta_values
                             if xi < len(row) and not pd.isna(row[xi])]
                if pt_deltas:
                    ax_bot.fill_between([xi - 0.12, xi + 0.12],
                                        [min(pt_deltas)] * 2, [max(pt_deltas)] * 2,
                                        color="#BBBBBB", alpha=0.35, zorder=1)
            total_range = d_max - d_min
            ax_bot.annotate(f"Total range: {total_range:.1f}°",
                            xy=(len(conditions) / 2 - 0.5, (d_max + d_min) / 2),
                            ha="center", fontsize=8, color="#444444")

        ax_bot.set_ylabel(r"$\Delta\beta_{mech}$ [°]")
        ax_bot.set_title("Required mechanical pitch adjustment vs cruise")
        ax_bot.legend(loc="upper right", fontsize=8)
        ax_bot.set_xticks(list(x))
        ax_bot.set_xticklabels(condition_labels)

        fig.tight_layout()
        out = output_dir / "pitch_requirement_summary.png"
        fig.savefig(out, dpi=300)
        plt.close(fig)

    return out


def generate_fixed_vs_variable_figure(
    polars_dir: Path,
    pitch_map_csv: Path,
    output_dir: Path,
) -> Path:
    """Single-panel figure comparing fixed vs variable pitch operating points.

    Shows mid-span CL/CD vs α for all flight conditions, with VPF α_opt markers
    and a fixed cruise reference line.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    pitch_df = pd.read_csv(pitch_map_csv)
    mid_rows = pitch_df[pitch_df["section"] == "mid_span"].set_index("flight")

    conditions = [c for c in _CONDITION_ORDER if c in mid_rows.index]

    # Paul Tol colors per condition
    cond_colors = {
        "takeoff": "#4477AA",
        "climb":   "#CCBB44",
        "cruise":  "#228833",
        "descent": "#EE6677",
    }

    with apply_style():
        fig, ax = plt.subplots(figsize=(6.5, 4.8))

        cruise_alpha_opt: Optional[float] = None

        for cond in conditions:
            polar_path = polars_dir / f"{cond}_mid_span.csv"
            if not polar_path.exists():
                continue
            pf = pd.read_csv(polar_path)
            if "alpha" not in pf.columns or "ld" not in pf.columns:
                continue
            pf = pf.replace([float("inf"), float("-inf")], pd.NA).dropna(subset=["ld"])
            color = cond_colors.get(cond, "#888888")
            label = _CONDITION_LABELS.get(cond, cond)
            ax.plot(pf["alpha"], pf["ld"], color=color, linewidth=1.6, label=label, alpha=0.85)

            if cond in mid_rows.index:
                alpha_opt = float(mid_rows.loc[cond, "alpha_opt"])
                # Interpolate LD at alpha_opt
                ld_at_opt = float(pf.set_index("alpha")["ld"].reindex(
                    pf["alpha"].tolist() + [alpha_opt]
                ).sort_index().interpolate(method="index").loc[alpha_opt])
                ax.axvline(alpha_opt, color=color, linestyle="--",
                           linewidth=1.1, alpha=0.7, zorder=3)
                ax.scatter(alpha_opt, ld_at_opt, color=color, s=50,
                           edgecolors="white", linewidths=1.0, zorder=5)
                if cond == "cruise":
                    cruise_alpha_opt = alpha_opt

        # Fixed pitch reference
        if cruise_alpha_opt is not None:
            ax.axvline(cruise_alpha_opt, color="#AA3377", linestyle="-",
                       linewidth=1.8, zorder=4,
                       label=f"Fixed-pitch design point (cruise, α={cruise_alpha_opt:.1f}°)")

        ax.set_xlabel(r"$\alpha$ [°]")
        ax.set_ylabel(r"$C_L / C_D$")
        ax.set_title("Mid-span: fixed vs variable pitch operating point")
        ax.legend(loc="lower right", fontsize=8)
        fig.tight_layout()

        out = output_dir / "fixed_vs_variable_pitch.png"
        fig.savefig(out, dpi=300)
        plt.close(fig)

    return out
