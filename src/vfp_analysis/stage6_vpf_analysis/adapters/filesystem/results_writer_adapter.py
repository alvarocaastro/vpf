from __future__ import annotations

from pathlib import Path

import pandas as pd


class FilesystemVpfResultsWriter:
    """Persist Stage 6 tables and text summaries to disk."""

    @staticmethod
    def write_optimal_pitch_table(optimal_incidences: list, output_path: Path) -> None:
        rows = [
            {
                "condition": item.condition,
                "section": item.section,
                "Re": item.reynolds,
                "Mach": item.mach,
                "alpha_opt": item.alpha_opt,
                "CL_CD_max": item.cl_cd_max,
            }
            for item in optimal_incidences
        ]
        df = pd.DataFrame(rows).sort_values(["condition", "section"])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False, float_format="%.6f")

    @staticmethod
    def write_pitch_adjustment_table(pitch_adjustments: list, output_path: Path) -> None:
        rows = [
            {
                "condition": item.condition,
                "section": item.section,
                "alpha_opt": item.alpha_opt,
                "delta_pitch": item.delta_pitch,
            }
            for item in pitch_adjustments
        ]
        df = pd.DataFrame(rows).sort_values(["condition", "section"])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False, float_format="%.6f")

    @staticmethod
    def write_analysis_summary(summary_text: str, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(summary_text, encoding="utf-8")
