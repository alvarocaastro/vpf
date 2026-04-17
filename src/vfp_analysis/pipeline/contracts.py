"""
contracts.py
------------
Contratos de I/O entre stages del pipeline VPF.

Cada StageNResult es un dataclass que encapsula:
  - Los artefactos generados (rutas a directorios/ficheros de salida)
  - Los valores clave calculados que necesitan los stages siguientes

Beneficios
----------
- El flujo de datos entre stages es explícito y verificable en tiempo de ejecución.
- Permite ejecutar cualquier stage de forma independiente sin conocer la
  implementación interna de los anteriores.
- Facilita los tests unitarios: cada stage puede ser probado con un StageNResult
  construido manualmente como fixture.
- Documenta qué produce cada stage y qué consume el siguiente.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Stage 1 — Selección de perfil aerodinámico
# ---------------------------------------------------------------------------

@dataclass
class Stage1Result:
    """Salida del Stage 1: selección automática de perfil.

    Inputs del stage
    ----------------
    - Candidatos en ``data/airfoils/`` (leídos de ``config.py::AIRFOILS``)
    - Condición de selección de ``PipelineSettings`` (Re, Ncrit, alpha range)

    Outputs
    -------
    - ``selected_airfoil_name``: nombre del perfil ganador (ej. "NACA 65-410")
    - ``selected_airfoil_dat``: ruta al fichero .dat del perfil ganador
    - ``stage_dir``: directorio raíz de resultados del stage
    - ``selection_dir``: sub-directorio con los polares de selección
    """
    selected_airfoil_name: str
    selected_airfoil_dat: Path
    stage_dir: Path
    selection_dir: Path

    def validate(self) -> None:
        """Verifica que los artefactos existen tras ejecutar el stage."""
        from vfp_analysis.validation.validators import require_dir, require_file
        require_file(self.selected_airfoil_dat, "perfil seleccionado .dat")
        require_dir(self.stage_dir, "Stage 1 results dir")


# ---------------------------------------------------------------------------
# Stage 2 — Simulaciones XFOIL (12 polares)
# ---------------------------------------------------------------------------

@dataclass
class Stage2Result:
    """Salida del Stage 2: polares XFOIL por condición y sección.

    Inputs del stage
    ----------------
    - ``Stage1Result.selected_airfoil_dat``
    - Condiciones de vuelo y secciones de pala (``PipelineSettings``)

    Outputs
    -------
    - ``source_polars``: directorio ``simulation_plots/`` con la estructura
      ``{flight}/{section}/polar.csv``
    - ``alpha_eff_map``: dict {(flight, section): alpha_opt_deg}
    - ``stall_map``: dict {(flight, section): alpha_stall_deg}
    - ``n_simulations``: número de simulaciones ejecutadas
    - ``n_convergence_warnings``: total de avisos de convergencia XFOIL
    """
    source_polars: Path                              # stage2/simulation_plots/
    alpha_eff_map: Dict[Tuple[str, str], float]     # (flight, section) → α_opt
    stall_map: Dict[Tuple[str, str], float]          # (flight, section) → α_stall
    n_simulations: int
    n_convergence_warnings: int
    stage_dir: Path

    def validate(self) -> None:
        from vfp_analysis.validation.validators import require_dir
        require_dir(self.source_polars, "Stage 2 simulation_plots")
        require_dir(self.stage_dir, "Stage 2 results dir")
        if self.n_simulations == 0:
            raise ValueError("Stage 2: no se ejecutaron simulaciones XFOIL")
        if len(self.alpha_eff_map) < self.n_simulations:
            raise ValueError(
                f"Stage 2: alpha_eff_map incompleto "
                f"({len(self.alpha_eff_map)} de {self.n_simulations} casos)"
            )


# ---------------------------------------------------------------------------
# Stage 3 — Correcciones de compresibilidad
# ---------------------------------------------------------------------------

@dataclass
class Stage3Result:
    """Salida del Stage 3: polares corregidos por PG y K-T.

    Inputs del stage
    ----------------
    - ``Stage2Result.source_polars``
    - ``PipelineSettings``: target_mach, airfoil_geometry

    Outputs
    -------
    - ``corrected_dir``: directorio con estructura ``{flight}/{section}/corrected_polar.csv``
    - ``n_cases_corrected``: número de casos procesados correctamente
    - ``n_cases_failed``: número de casos que fallaron
    """
    corrected_dir: Path           # stage3/
    n_cases_corrected: int
    n_cases_failed: int
    stage_dir: Path

    @property
    def success_rate(self) -> float:
        total = self.n_cases_corrected + self.n_cases_failed
        return self.n_cases_corrected / total if total > 0 else 0.0

    def validate(self) -> None:
        from vfp_analysis.validation.validators import require_dir
        require_dir(self.corrected_dir, "Stage 3 corrected polars dir")
        if self.n_cases_corrected == 0:
            raise ValueError("Stage 3: ningún polar corregido — revisar Stage 2 outputs")
        # Verify at least one corrected_polar.csv exists inside the directory tree
        polar_files = list(self.corrected_dir.rglob("corrected_polar.csv"))
        if not polar_files:
            raise ValueError(
                f"Stage 3: corrected_dir existe pero no contiene ningún "
                f"corrected_polar.csv: {self.corrected_dir}"
            )


# ---------------------------------------------------------------------------
# Stage 4 — Métricas de rendimiento
# ---------------------------------------------------------------------------

@dataclass
class Stage4Result:
    """Salida del Stage 4: métricas aerodinámicas y figuras.

    Inputs del stage
    ----------------
    - ``Stage3Result.corrected_dir`` (o Stage2 si Stage3 no está disponible)

    Outputs
    -------
    - ``metrics``: lista de AerodynamicMetrics por caso
    - ``tables_dir``: directorio con summary_table.csv, clcd_max_by_section.csv
    - ``figures_dir``: directorio con figuras analíticas y de publicación
    """
    metrics: List[Any]    # List[AerodynamicMetrics] (Any para evitar import circular)
    tables_dir: Path
    figures_dir: Path
    stage_dir: Path

    def validate(self) -> None:
        from vfp_analysis.validation.validators import require_dir
        require_dir(self.stage_dir, "Stage 4 results dir")
        require_dir(self.tables_dir, "Stage 4 tables dir")
        if not self.metrics:
            raise ValueError("Stage 4: lista de métricas vacía")


# ---------------------------------------------------------------------------
# Stage 5 — Pitch & Kinematics
# ---------------------------------------------------------------------------

@dataclass
class Stage5Result:
    """Salida del Stage 5: análisis completo de cinemática y aerodinámica 3D.

    Inputs del stage
    ----------------
    - Stage2/3 polares
    - ``PipelineSettings``: fan geometry, blade geometry

    Outputs
    -------
    - ``tables_dir``: 9 CSVs (cascade_corrections, rotational_corrections,
      rotational_corrections_du_selig, optimal_incidence, pitch_adjustment,
      blade_twist_design, off_design_incidence, stage_loading, kinematics_analysis)
    - ``figures_dir``: ≥16 figuras (16 fijas + 1 por condición de vuelo)
    - ``n_tables``: número de tablas generadas
    - ``n_figures``: número de figuras generadas
    - ``twist_total_deg``: twist de diseño root→tip [°]
    - ``max_off_design_loss_pct``: pérdida máxima de eficiencia off-design [%]
    """
    tables_dir: Path
    figures_dir: Path
    n_tables: int
    n_figures: int
    twist_total_deg: float
    max_off_design_loss_pct: float
    stage_dir: Path

    def validate(self) -> None:
        from vfp_analysis.validation.validators import require_dir
        require_dir(self.tables_dir, "Stage 5 tables dir")
        require_dir(self.figures_dir, "Stage 5 figures dir")
        if self.n_tables < 9:
            raise ValueError(
                f"Stage 5: solo {self.n_tables} tablas (se esperan ≥9)"
            )


# ---------------------------------------------------------------------------
# Stage 6 — Reverse Thrust Modeling
# ---------------------------------------------------------------------------

@dataclass
class Stage6Result:
    """Salida del Stage 6: modelado de empuje reverso VPF.

    Inputs del stage
    ----------------
    - ``Stage5Result.tables_dir`` (blade_twist_design.csv)
    - ``results/stage3_compressibility_correction/takeoff/`` polars
    - ``engine_parameters.yaml`` (reverse_thrust section)

    Outputs
    -------
    - ``tables_dir``: 4 CSVs (kinematics, sweep, optimal, mechanism_weight)
    - ``figures_dir``: 4 PNG figures
    - ``beta_opt_deg``: optimal blade angle at mid-span in reverse [°]
    - ``thrust_fraction``: achieved |T_rev| / T_forward_takeoff [0–1]
    - ``mechanism_weight_kg``: VPF mechanism weight both engines [kg]
    - ``sfc_cruise_penalty_pct``: cruise SFC increase from mechanism weight [%]
    """
    tables_dir: Path
    figures_dir: Path
    n_tables: int
    n_figures: int
    beta_opt_deg: float
    thrust_fraction: float
    mechanism_weight_kg: float
    sfc_cruise_penalty_pct: float
    stage_dir: Path

    def validate(self) -> None:
        from vfp_analysis.validation.validators import require_dir
        require_dir(self.stage_dir, "Stage 6 results dir")
        require_dir(self.tables_dir, "Stage 6 tables dir")
        require_dir(self.figures_dir, "Stage 6 figures dir")
        if self.n_tables < 4:
            raise ValueError(f"Stage 6: {self.n_tables} tablas (se esperan ≥4)")
        if not (0.0 < self.thrust_fraction < 1.0):
            raise ValueError(
                f"Stage 6: thrust_fraction fuera de rango físico: {self.thrust_fraction}"
            )
        if self.mechanism_weight_kg <= 0:
            raise ValueError("Stage 6: mechanism_weight_kg debe ser positivo")


# ---------------------------------------------------------------------------
# Stage 7 — SFC Analysis
# ---------------------------------------------------------------------------

@dataclass
class Stage7Result:
    """Salida del Stage 7: impacto del VPF en el consumo específico de combustible.

    Inputs del stage
    ----------------
    - ``Stage5Result.tables_dir`` (optimal_incidence.csv)
    - ``Stage6Result.tables_dir`` (mechanism_weight.csv)
    - ``engine_parameters.yaml``

    Outputs
    -------
    - ``tables_dir``: sfc_analysis.csv
    - ``figures_dir``: figuras
    - ``mean_sfc_reduction_pct``: reducción media de SFC [%]
    """
    tables_dir: Path
    figures_dir: Path
    mean_sfc_reduction_pct: float
    stage_dir: Path

    def validate(self) -> None:
        from vfp_analysis.validation.validators import require_dir
        require_dir(self.stage_dir, "Stage 7 results dir")
        require_dir(self.tables_dir, "Stage 7 tables dir")
        require_dir(self.figures_dir, "Stage 7 figures dir")
        if math.isnan(self.mean_sfc_reduction_pct):
            raise ValueError(
                "Stage 7: mean_sfc_reduction_pct es NaN — "
                "revisar que sfc_analysis.csv contiene columna 'sfc_reduction'"
            )
