"""
Service for applying compressibility corrections to aerodynamic results.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import pandas as pd

from vfp_analysis.compressibility.adapters.correction_models.prandtl_glauert_model import (
    PrandtlGlauertModel,
)
from vfp_analysis.compressibility.core.domain.compressibility_case import (
    CompressibilityCase,
)
from vfp_analysis.compressibility.core.domain.correction_result import (
    CorrectionResult,
)


class CompressibilityCorrectionService:
    """Orchestrates Prandtl-Glauert compressibility correction for one case."""

    def __init__(
        self,
        correction_model: PrandtlGlauertModel,
        base_output_dir: Path,
    ) -> None:
        self._model = correction_model
        self._base_output = base_output_dir

    def correct_case(
        self,
        case: CompressibilityCase,
        input_polar_path: Path,
        section: Optional[str] = None,
    ) -> CorrectionResult:
        """Apply compressibility correction to one polar file."""
        if not input_polar_path.is_file():
            raise FileNotFoundError(f"Polar file not found: {input_polar_path}")

        df_original = pd.read_csv(input_polar_path)
        df_corrected = self._model.correct_polar(df_original, case)

        output_dir = self._base_output / case.flight_condition.lower()
        if section:
            output_dir = output_dir / section
        output_dir.mkdir(parents=True, exist_ok=True)

        polar_path      = output_dir / "corrected_polar.csv"
        cl_alpha_path   = output_dir / "corrected_cl_alpha.csv"
        efficiency_path = output_dir / "corrected_efficiency.csv"
        plot_path       = output_dir / "corrected_plots.png"

        df_corrected.to_csv(polar_path, index=False, float_format="%.6f")
        df_corrected[["alpha", "cl_corrected"]].to_csv(cl_alpha_path, index=False, float_format="%.6f")
        df_corrected[["alpha", "ld_corrected"]].to_csv(efficiency_path, index=False, float_format="%.6f")

        self._plot_comparison(df_original, df_corrected, case, plot_path)

        case_name = f"{case.flight_condition}_{section}" if section else case.flight_condition
        return CorrectionResult(
            case=case_name,
            section=section,
            output_dir=output_dir,
            corrected_polar_path=polar_path,
            corrected_cl_alpha_path=cl_alpha_path,
            corrected_efficiency_path=efficiency_path,
            corrected_plot_path=plot_path,
        )

    @staticmethod
    def _plot_comparison(
        df_original: pd.DataFrame,
        df_corrected: pd.DataFrame,
        case: CompressibilityCase,
        output_path: Path,
    ) -> None:
        """Generate comparison plots: original vs corrected."""
        fig, axes = plt.subplots(2, 1, figsize=(6.0, 8.0))

        ax1 = axes[0]
        ax1.plot(df_original["alpha"], df_original["cl"],
                 label=f"Original (M={case.reference_mach:.2f})", linewidth=1.4, linestyle="--")
        ax1.plot(df_corrected["alpha"], df_corrected["cl_corrected"],
                 label=f"Corrected (M={case.target_mach:.2f})", linewidth=1.6)
        ax1.set_xlabel(r"$\alpha$ [deg]")
        ax1.set_ylabel(r"$C_L$")
        ax1.set_title(f"$C_L$ vs $\\alpha$ – {case.flight_condition}")
        ax1.legend(loc="lower right")

        ax2 = axes[1]
        ld_original = df_original["cl"] / df_original["cd"]
        ax2.plot(df_original["alpha"], ld_original,
                 label=f"Original (M={case.reference_mach:.2f})", linewidth=1.4, linestyle="--")
        ax2.plot(df_corrected["alpha"], df_corrected["ld_corrected"],
                 label=f"Corrected (M={case.target_mach:.2f})", linewidth=1.6)
        ax2.set_xlabel(r"$\alpha$ [deg]")
        ax2.set_ylabel(r"$C_L/C_D$")
        ax2.set_title(f"Efficiency $C_L/C_D$ vs $\\alpha$ – {case.flight_condition}")
        ax2.legend(loc="lower right")

        fig.tight_layout()
        fig.savefig(output_path, dpi=300, bbox_inches="tight")
        plt.close(fig)
