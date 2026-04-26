from __future__ import annotations

import dataclasses
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

import pandas as pd

from vpf_analysis.adapters.xfoil.xfoil_parser import parse_polar_file
from vpf_analysis.core.domain.airfoil import Airfoil
from vpf_analysis.core.domain.simulation_condition import SimulationCondition
from vpf_analysis.ports.xfoil_runner_port import XfoilRunnerPort
from vpf_analysis.stage1_airfoil_selection.scoring import (
    AirfoilScore,
    normalise_scores,
    score_airfoil,
)

LOGGER = logging.getLogger(__name__)

# Paul Tol bright palette — 4 distinct colours for candidate airfoils
_TOLS = ["#4477AA", "#EE6677", "#228833", "#CCBB44"]


@dataclass(frozen=True)
class AirfoilSelectionResult:
    best_airfoil: Airfoil
    scores: list[AirfoilScore]
    polars: pd.DataFrame


class AirfoilSelectionService:
    """Compare all candidate airfoils and select the best one."""

    def __init__(self, xfoil_runner: XfoilRunnerPort, results_dir: Path) -> None:
        self._xfoil = xfoil_runner
        self._results_dir = results_dir

    def run_selection(
        self,
        airfoils: Sequence[Airfoil],
        condition: SimulationCondition,
        progress_callback: Callable[[str], None] | None = None,
    ) -> AirfoilSelectionResult:
        """Run XFOIL for all airfoils at a single reference condition."""

        all_rows: list[pd.DataFrame] = []
        raw_scores: list[AirfoilScore] = []

        out_dir = self._results_dir / "airfoil_selection"
        out_dir.mkdir(parents=True, exist_ok=True)

        LOGGER.info(
            "Evaluating %d airfoil candidates at Re=%.2e, M=%.2f, Ncrit=%.1f",
            len(airfoils),
            condition.reynolds,
            condition.mach_rel,
            condition.ncrit,
        )

        for airfoil in airfoils:
            if progress_callback is not None:
                progress_callback(airfoil.name)
            out_file = out_dir / f"{airfoil.name.replace(' ', '_')}_polar.txt"
            LOGGER.info("  Running XFOIL: %s", airfoil.name)

            try:
                self._xfoil.run_polar(airfoil.dat_path, condition, out_file)
            except Exception as exc:
                LOGGER.warning("  XFOIL failed for %s: %s - skipping.", airfoil.name, exc)
                continue

            df = self._build_polar_df(out_file, airfoil, condition)
            if df.empty:
                LOGGER.warning("  Polar empty for %s - skipping.", airfoil.name)
                continue

            raw_scores.append(score_airfoil(df))
            all_rows.append(df)

        polars = pd.concat(all_rows, ignore_index=True) if all_rows else pd.DataFrame()

        if not raw_scores:
            raise RuntimeError(
                "No airfoil could be scored (all XFOIL runs failed or produced empty polars)."
            )

        scores = normalise_scores(raw_scores)

        for score in scores:
            LOGGER.info(
                "  %s -> (CL/CD)_2nd=%.2f  alpha_opt=%.1f°  stall=%.1f°  margin=%.1f°  robustness=%.2f  score=%.3f",
                score.airfoil,
                score.max_ld,
                score.alpha_opt,
                score.stall_alpha,
                score.stability_margin,
                score.robustness_ld,
                score.total_score,
            )

        best = max(scores, key=lambda s: s.total_score)
        LOGGER.info("Selected airfoil: %s (score=%.3f)", best.airfoil, best.total_score)

        selected_path = out_dir / "selected_airfoil.dat"
        selected_path.write_text(best.airfoil, encoding="utf-8")

        best_airfoil = next(a for a in airfoils if a.name == best.airfoil)

        self._save_comparison_figure(polars, scores, out_dir)
        self._save_scores_csv(scores, out_dir)

        return AirfoilSelectionResult(best_airfoil=best_airfoil, scores=scores, polars=polars)

    @staticmethod
    def _save_comparison_figure(
        polars: pd.DataFrame, scores: list[AirfoilScore], out_dir: Path
    ) -> None:
        import matplotlib.pyplot as plt

        from vpf_analysis.shared.plot_style import apply_style

        with apply_style():
            fig, ax = plt.subplots(figsize=(7, 4))
            for i, score in enumerate(scores):
                color = _TOLS[i % len(_TOLS)]
                sub = polars[polars["airfoil"] == score.airfoil].sort_values("alpha")
                ax.plot(sub["alpha"], sub["ld"], color=color, label=score.airfoil)
                ax.axvline(score.alpha_opt, color=color, linestyle="--", linewidth=0.9)
            ax.set_xlabel("α (°)")
            ax.set_ylabel("CL / CD")
            ax.set_title("Airfoil selection — polar comparison")
            ax.legend(loc="upper left", bbox_to_anchor=(1.0, 1.0), title="Airfoil")
            fig.savefig(out_dir / "polar_comparison.png")
            plt.close(fig)

    @staticmethod
    def _save_scores_csv(scores: list[AirfoilScore], out_dir: Path) -> None:
        rows = [dataclasses.asdict(s) for s in scores]
        pd.DataFrame(rows).to_csv(out_dir / "scores.csv", index=False)

    @staticmethod
    def _build_polar_df(
        polar_path: Path,
        airfoil: Airfoil,
        condition: SimulationCondition,
    ) -> pd.DataFrame:
        df = parse_polar_file(polar_path)
        if df.empty:
            return df
        df.insert(0, "airfoil", airfoil.name)
        df.insert(1, "condition", condition.name)
        df.insert(2, "mach", condition.mach_rel)
        df.insert(3, "re", condition.reynolds)
        return df
