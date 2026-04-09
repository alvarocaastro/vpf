from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import run_analysis
from vfp_analysis import config as base_config


def _existing_count(path: Path, pattern: str) -> int:
    return len(list(path.glob(pattern))) if path.exists() else 0


def _validate_stage_outputs(stage_num: int) -> list[str]:
    stage_dir = base_config.get_stage_dir(stage_num)
    checks: list[tuple[Path, str]] = []

    if stage_num == 1:
        checks = [
            (stage_dir / "airfoil_selection" / "selected_airfoil.dat", "selected airfoil"),
        ]
    elif stage_num == 2:
        checks = [
            (stage_dir / "simulation_plots", "simulation plots directory"),
            (stage_dir / "polars", "organized polar directory"),
        ]
    elif stage_num == 3:
        checks = [
            (stage_dir, "compressibility output directory"),
        ]
    elif stage_num == 4:
        checks = [
            (stage_dir / "tables" / "summary_table.csv", "summary table"),
            (stage_dir / "tables" / "clcd_max_by_section.csv", "section metrics table"),
        ]
    elif stage_num == 5:
        checks = [
            (stage_dir / "figures", "figure directory"),
        ]
    elif stage_num == 6:
        checks = [
            (stage_dir / "tables" / "vpf_optimal_pitch.csv", "optimal pitch table"),
            (stage_dir / "tables" / "vpf_pitch_adjustment.csv", "pitch adjustment table"),
            (stage_dir / "figures", "VPF figure directory"),
        ]
    elif stage_num == 7:
        checks = [
            (stage_dir / "tables" / "kinematics_analysis.csv", "kinematics table"),
            (stage_dir / "figures", "kinematics figure directory"),
        ]
    elif stage_num == 8:
        checks = [
            (stage_dir / "tables" / "sfc_analysis.csv", "SFC table"),
            (stage_dir / "figures", "SFC figure directory"),
        ]

    messages: list[str] = []
    for path, label in checks:
        status = "OK" if path.exists() else "MISSING"
        messages.append(f"[{status}] {label}: {path}")

    if stage_num == 2:
        polars_dir = stage_dir / "polars"
        messages.append(f"[INFO] Stage 2 flat polars: {_existing_count(polars_dir, '*.csv')}")
    elif stage_num == 3:
        corrected = _existing_count(stage_dir, "*/*/corrected_polar.csv")
        messages.append(f"[INFO] Stage 3 corrected polars: {corrected}")
    elif stage_num == 5:
        figures_dir = stage_dir / "figures"
        messages.append(f"[INFO] Stage 5 figures: {_existing_count(figures_dir, '*.png')}")
    elif stage_num == 6:
        figures_dir = stage_dir / "figures"
        messages.append(f"[INFO] Stage 6 figures: {_existing_count(figures_dir, '*.png')}")
    elif stage_num == 8:
        figures_dir = stage_dir / "figures"
        messages.append(f"[INFO] Stage 8 figures: {_existing_count(figures_dir, '*.png')}")

    return messages


def _load_cached_airfoil() -> "run_analysis.Airfoil | None":
    """Reconstruct the selected Airfoil object from Stage 1 results on disk."""
    stage1_dir = base_config.get_stage_dir(1)
    dat_path = stage1_dir / "airfoil_selection" / "selected_airfoil.dat"
    if not dat_path.is_file():
        return None
    # Infer name from file (first line of a dat file is typically the name)
    try:
        name = dat_path.read_text().splitlines()[0].strip()
    except Exception:
        name = dat_path.stem
    from vfp_analysis.core.domain.airfoil import Airfoil
    return Airfoil(name=name, family="", dat_path=dat_path)


def _load_cached_polars() -> "Path | None":
    """Return the Stage 2 simulation_plots directory (what step_3_xfoil_simulations returns)."""
    stage2_dir = base_config.get_stage_dir(2)
    sim_plots_dir = stage2_dir / "simulation_plots"
    # Check that at least one polar.csv exists inside the subdirectory structure
    if sim_plots_dir.exists() and any(sim_plots_dir.glob("*/*/polar.csv")):
        return sim_plots_dir
    return None


def run_stage_check(stage_num: int, clean: bool = True, cache: bool = False) -> None:
    """Run the pipeline up to *stage_num* and validate its outputs.

    Parameters
    ----------
    stage_num : int
        Target stage (1–8).
    clean : bool
        Wipe previous results before running (ignored when *cache* is True).
    cache : bool
        Skip re-running stages whose results already exist on disk and load
        their outputs directly.  Implies ``clean=False``.
    """
    if stage_num < 1 or stage_num > 8:
        raise ValueError("stage_num must be between 1 and 8")

    if cache:
        clean = False  # cache mode never wipes existing results

    print("=" * 80)
    print(f"Stage check requested: Stage {stage_num}"
          + ("  [cache mode — skipping completed stages]" if cache else ""))
    print("=" * 80)

    if clean:
        print("[RUN] Cleaning previous results")
        run_analysis.step_1_clean_results()

    selected_airfoil = None
    source_polars = None
    metrics = None

    # ── Stage 1 ─────────────────────────────────────────────────────────────
    if stage_num >= 1:
        if cache and (airfoil := _load_cached_airfoil()) is not None:
            selected_airfoil = airfoil
            print(f"[CACHE] Stage 1 - using cached airfoil: {selected_airfoil.name}")
        else:
            print("[RUN] Stage 1 - airfoil selection")
            selected_airfoil = run_analysis.step_2_airfoil_selection()
            print(f"[INFO] Selected airfoil: {selected_airfoil.name}")

    # ── Stage 2 ─────────────────────────────────────────────────────────────
    if stage_num >= 2:
        if cache and (polars := _load_cached_polars()) is not None:
            source_polars = polars
            print(f"[CACHE] Stage 2 - using cached polars: {source_polars}")
        else:
            print("[RUN] Stage 2 - XFOIL simulations")
            source_polars = run_analysis.step_3_xfoil_simulations(selected_airfoil)
            print(f"[INFO] Stage 2 source polars: {source_polars}")

    # ── Stage 3 ─────────────────────────────────────────────────────────────
    if stage_num >= 3:
        stage3_dir = base_config.get_stage_dir(3)
        cached_s3 = cache and _existing_count(stage3_dir, "*/*/corrected_polar.csv") > 0
        if cached_s3:
            print("[CACHE] Stage 3 - using cached compressibility corrections")
        else:
            print("[RUN] Stage 3 - compressibility correction")
            run_analysis.step_4_compressibility_correction(source_polars)

    # ── Stage 4 ─────────────────────────────────────────────────────────────
    if stage_num >= 4:
        stage4_dir = base_config.get_stage_dir(4)
        cached_s4 = cache and (stage4_dir / "tables" / "summary_table.csv").is_file()
        if cached_s4:
            print("[CACHE] Stage 4 - loading cached metrics")
            metrics = run_analysis.step_5_compute_metrics()  # fast read-only
        else:
            print("[RUN] Stage 4 - metrics and tables")
            metrics = run_analysis.step_5_compute_metrics()
            run_analysis.step_6_export_tables(metrics)
            print(f"[INFO] Metric cases computed: {len(metrics)}")

    # ── Stage 5 ─────────────────────────────────────────────────────────────
    if stage_num >= 5:
        stage5_dir = base_config.get_stage_dir(5)
        cached_s5 = cache and _existing_count(stage5_dir / "figures", "*.png") > 0
        if cached_s5:
            print("[CACHE] Stage 5 - using cached figures")
        else:
            print("[RUN] Stage 5 - publication figures")
            if metrics is None:
                metrics = run_analysis.step_5_compute_metrics()
                run_analysis.step_6_export_tables(metrics)
            run_analysis.step_7_generate_figures(metrics)

    # ── Stage 6 ─────────────────────────────────────────────────────────────
    if stage_num >= 6:
        stage6_dir = base_config.get_stage_dir(6)
        cached_s6 = cache and (stage6_dir / "tables" / "vpf_optimal_pitch.csv").is_file()
        if cached_s6:
            print("[CACHE] Stage 6 - using cached VPF analysis")
        else:
            print("[RUN] Stage 6 - VPF analysis")
            run_analysis.step_8_vpf_analysis()

    # ── Stage 7 ─────────────────────────────────────────────────────────────
    if stage_num >= 7:
        stage7_dir = base_config.get_stage_dir(7)
        cached_s7 = cache and (stage7_dir / "tables" / "kinematics_analysis.csv").is_file()
        if cached_s7:
            print("[CACHE] Stage 7 - using cached kinematics analysis")
        else:
            print("[RUN] Stage 7 - kinematics analysis")
            run_analysis.step_9_kinematics_analysis()

    # ── Stage 8 ─────────────────────────────────────────────────────────────
    if stage_num >= 8:
        stage8_dir = base_config.get_stage_dir(8)
        cached_s8 = cache and (stage8_dir / "tables" / "sfc_analysis.csv").is_file()
        if cached_s8:
            print("[CACHE] Stage 8 - using cached SFC analysis")
        else:
            print("[RUN] Stage 8 - SFC analysis")
            run_analysis.step_10_sfc_analysis()

    print("-" * 80)
    for line in _validate_stage_outputs(stage_num):
        print(line)
    print("=" * 80)


def build_parser(stage_num: int) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=f"Run and validate the pipeline up to Stage {stage_num}."
    )
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="Do not remove previous results before running.",
    )
    parser.add_argument(
        "--cache",
        action="store_true",
        help=(
            "Skip stages whose results already exist on disk. "
            "Only the target stage is (re-)run. Implies --no-clean."
        ),
    )
    return parser
