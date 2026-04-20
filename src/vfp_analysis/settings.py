"""settings.py — single source of truth for all physics constants and simulation parameters."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

import yaml

from vfp_analysis import config as _base

# ---------------------------------------------------------------------------
# Physics constants / empirical coefficients (not overridden by YAML)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PhysicsConstants:
    """Empirical coefficients and physical limits for the VPF aerodynamic pipeline."""

    # ------------------------------------------------------------------
    # Optimal incidence detection (second CL/CD peak)
    # ------------------------------------------------------------------
    ALPHA_MIN_OPT_DEG: float = 1.0
    """Minimum angle for optimal peak search [°].
    Avoids the very-low-alpha (< 1°) laminar separation bubble artefact
    predicted by XFOIL while still allowing the true Mach-dependent peak
    (typically 2.2–3.5° across fan operating conditions) to be found.
    Using 3° was too conservative: it forced alpha_opt ≥ 3° even when the
    real 2D/KT peak at cruise M=0.93 lies near 2.35°.
    Ref: Drela (1989) XFOIL docs; Selig & McGranahan (2004)."""

    CL_MIN_3D: float = 0.30
    """Minimum CL for a point to be considered operational in 3D polars.
    Ref: high-bypass fan design criterion (Cumpsty 2004, ch. 9)."""

    # ------------------------------------------------------------------
    # Cascade corrections
    # ------------------------------------------------------------------
    CARTER_M_NACA6: float = 0.23
    """Carter's rule m coefficient for NACA 6-series (a/c = 0.5).
    Ref: Carter (1950), NACA TN-2273, Table 1; ESDU 05017."""

    WEINIG_SIGMA_MIN: float = 0.10
    """Minimum solidity for Weinig factor validity.
    Ref: Weinig (1935); Dixon & Hall (2013), eq. 3.54."""

    WEINIG_SIGMA_MAX: float = 2.50
    """Maximum solidity for Weinig factor validity."""

    # ------------------------------------------------------------------
    # 3D rotational corrections (Snel et al.)
    # ------------------------------------------------------------------
    SNEL_A: float = 3.0
    """Empirical coefficient a in Snel's rotational correction for attached flow.
    ΔCL_rot = a · (c/r)² · CL_2D
    Ref: Snel, Houwink & Bosschers (1994), ECN-C--94-004, sec. 2.3."""

    # ------------------------------------------------------------------
    # Efficient fan design zone (φ-ψ diagram)
    # ------------------------------------------------------------------
    PHI_DESIGN_MIN: float = 0.35
    """Lower bound of flow coefficient φ in design zone.
    Ref: Dixon & Hall (2013), ch. 5; Cumpsty (2004), ch. 2."""

    PHI_DESIGN_MAX: float = 0.55
    """Upper bound of flow coefficient φ in design zone."""

    PSI_DESIGN_MIN: float = 0.25
    """Lower bound of work coefficient ψ in design zone."""

    PSI_DESIGN_MAX: float = 0.50
    """Upper bound of work coefficient ψ in design zone."""

    # ------------------------------------------------------------------
    # Minimum quality of a valid polar
    # ------------------------------------------------------------------
    POLAR_MIN_ROWS: int = 10
    """Minimum number of points to consider a polar usable."""

    POLAR_CL_MAX_PHYSICAL: float = 2.5
    """Maximum physically reasonable CL for a subsonic airfoil."""

    POLAR_CD_MIN_PHYSICAL: float = 1e-6
    """Minimum physically reasonable CD (CD > 0 always)."""

    # ------------------------------------------------------------------
    # Physical operating ranges
    # ------------------------------------------------------------------
    REYNOLDS_MIN: float = 1e4
    """Minimum Reynolds for significant viscous flow."""

    REYNOLDS_MAX: float = 1e9
    """Maximum physically reasonable Reynolds for thin airfoils."""

    MACH_MAX_SUBSONIC: float = 0.99
    """Maximum Mach for subsonic analysis (M < 1 strictly)."""

    MACH_KT_VALID_MAX: float = 0.87
    """Upper Mach limit for Kármán-Tsien validity.
    Above this value (cruise M=0.93 on relative blade frame) KT's non-linear
    denominator approaches singularity and the correction over-predicts CL.
    Fall back to Prandtl-Glauert, which is conservative but remains monotonic.
    Ref: Moran (2003) 'Introduction to Theoretical and Computational Aerodynamics',
    ch. 9; Abbott & von Doenhoff (1959) p. 116."""


@dataclass(frozen=True)
class XfoilSettings:
    """XFOIL integration configuration."""

    ITER: int = 200
    """Max viscous iterations per α point.
    Ref: Drela (1989) XFOIL docs — increased from default for high-Re/Mach polars."""

    TIMEOUT_SELECTION_S: float = 60.0
    """Timeout for Stage 1 (airfoil selection): small α range, single Re."""

    TIMEOUT_FINAL_S: float = 180.0
    """Timeout for Stage 2 (final simulations): full α range, 12 cases."""

    MAX_RETRIES: int = 3
    """Max retries on XFOIL failure (timeout or non-zero exit code)."""

    RETRY_WAIT_S: float = 1.0
    """Wait between retries [s]."""

    CONVERGENCE_WARN_KEYWORDS: tuple = (
        "VISCAL",
        "Convergence failed",
        "RMSBL",
        "MRCHDU",
        "MRCHD",
    )
    """Keywords identifying convergence failures in XFOIL stdout."""


# ---------------------------------------------------------------------------
# Full pipeline configuration (loaded from YAML)
# ---------------------------------------------------------------------------

@dataclass
class FanGeometry:
    """Variable-pitch fan geometry."""
    rpm: float
    omega_rad_s: float
    radii_m: Dict[str, float]
    axial_velocity_m_s: Dict[str, float]


@dataclass
class BladeGeometry:
    """Blade geometry for cascade and rotational corrections."""
    num_blades: int
    chord_m: Dict[str, float]
    theta_camber_deg: float


@dataclass
class AirfoilGeometry:
    """Airfoil geometric parameters for compressibility corrections."""
    thickness_ratio: float  # t/c
    korn_kappa: float       # factor κ de Korn (drag divergence)


@dataclass
class PipelineSettings:
    """Full pipeline configuration loaded from YAML files. Use ``get_settings()`` for the cached instance."""
    physics: PhysicsConstants = field(default_factory=PhysicsConstants)
    xfoil: XfoilSettings = field(default_factory=XfoilSettings)

    flight_conditions: List[str] = field(default_factory=list)
    blade_sections: List[str] = field(default_factory=list)

    reynolds_table: Dict[str, Dict[str, float]] = field(default_factory=dict)
    ncrit_table: Dict[str, float] = field(default_factory=dict)
    target_mach: Dict[str, float] = field(default_factory=dict)
    reference_mach: float = 0.2

    alpha_min: float = -5.0
    alpha_max: float = 23.0
    alpha_step: float = 0.15

    selection_alpha_min: float = -5.0
    selection_alpha_max: float = 20.0
    selection_alpha_step: float = 0.15
    selection_reynolds: float = 3.0e6
    selection_ncrit: float = 7.0

    fan: FanGeometry = field(default_factory=lambda: FanGeometry(
        rpm=4500.0, omega_rad_s=471.24, radii_m={}, axial_velocity_m_s={},
    ))
    blade: BladeGeometry = field(default_factory=lambda: BladeGeometry(
        num_blades=18, chord_m={}, theta_camber_deg=8.0,
    ))
    airfoil_geometry: AirfoilGeometry = field(default_factory=lambda: AirfoilGeometry(
        thickness_ratio=0.10, korn_kappa=0.87,
    ))

    results_dir: Path = field(default_factory=lambda: _base.RESULTS_DIR)


# ---------------------------------------------------------------------------
# Load and cache
# ---------------------------------------------------------------------------

_SETTINGS_CACHE: PipelineSettings | None = None


def get_settings(
    analysis_config_path: Path | None = None,
) -> PipelineSettings:
    """Return cached PipelineSettings. First call loads YAML; subsequent calls are instant."""
    global _SETTINGS_CACHE
    if _SETTINGS_CACHE is not None:
        return _SETTINGS_CACHE
    _SETTINGS_CACHE = _load_settings(analysis_config_path)
    return _SETTINGS_CACHE


def clear_settings_cache() -> None:
    """Invalidate the settings cache (useful in tests)."""
    global _SETTINGS_CACHE
    _SETTINGS_CACHE = None


def _load_settings(config_path: Path | None) -> PipelineSettings:
    """Load and validate parameters from YAML files."""
    if config_path is None:
        config_path = _base.ROOT_DIR / "config" / "analysis_config.yaml"

    if not config_path.exists():
        raise FileNotFoundError(
            f"Configuration file not found: {config_path}"
        )

    with config_path.open("r", encoding="utf-8") as f:
        raw: Dict[str, Any] = yaml.safe_load(f)

    flight_conditions: List[str] = raw["flight_conditions"]
    blade_sections: List[str] = raw["blade_sections"]

    reynolds_table = {
        flight: {section: float(v) for section, v in sections.items()}
        for flight, sections in raw["reynolds"].items()
    }
    ncrit_table = {k: float(v) for k, v in raw["ncrit"].items()}
    target_mach = {k: float(v) for k, v in raw["target_mach"].items()}

    alpha_cfg = raw["alpha"]
    sel_cfg = raw.get("selection_alpha", alpha_cfg)
    sel = raw.get("selection", {})

    fg = raw["fan_geometry"]
    rpm = float(fg["rpm"])
    fan = FanGeometry(
        rpm=rpm,
        omega_rad_s=rpm * 2.0 * math.pi / 60.0,
        radii_m={k: float(v) for k, v in fg["radius"].items()},
        axial_velocity_m_s={k: float(v) for k, v in fg["axial_velocity"].items()},
    )

    bg = raw["blade_geometry"]
    blade = BladeGeometry(
        num_blades=int(bg["num_blades"]),
        chord_m={k: float(v) for k, v in bg["chord"].items()},
        theta_camber_deg=float(bg["theta_camber_deg"]),
    )

    ag = raw.get("airfoil_geometry", {})
    airfoil_geom = AirfoilGeometry(
        thickness_ratio=float(ag.get("thickness_ratio", 0.10)),
        korn_kappa=float(ag.get("korn_kappa", 0.87)),
    )

    # xfoil settings (optional section, falls back to hardcoded defaults)
    xf_raw = raw.get("xfoil", {})
    import dataclasses as _dc
    xfoil_settings = _dc.replace(
        XfoilSettings(),
        **{k: v for k, v in {
            "ITER":                 xf_raw.get("iter"),
            "TIMEOUT_SELECTION_S":  xf_raw.get("timeout_selection_s"),
            "TIMEOUT_FINAL_S":      xf_raw.get("timeout_final_s"),
            "MAX_RETRIES":          xf_raw.get("max_retries"),
            "RETRY_WAIT_S":         xf_raw.get("retry_wait_s"),
        }.items() if v is not None}
    )

    return PipelineSettings(
        physics=PhysicsConstants(),
        xfoil=xfoil_settings,
        flight_conditions=flight_conditions,
        blade_sections=blade_sections,
        reynolds_table=reynolds_table,
        ncrit_table=ncrit_table,
        target_mach=target_mach,
        reference_mach=float(raw.get("reference_mach", 0.2)),
        alpha_min=float(alpha_cfg["min"]),
        alpha_max=float(alpha_cfg["max"]),
        alpha_step=float(alpha_cfg["step"]),
        selection_alpha_min=float(sel_cfg["min"]),
        selection_alpha_max=float(sel_cfg["max"]),
        selection_alpha_step=float(sel_cfg["step"]),
        selection_reynolds=float(sel.get("reynolds", 3.0e6)),
        selection_ncrit=float(sel.get("ncrit", 7.0)),
        fan=fan,
        blade=blade,
        airfoil_geometry=airfoil_geom,
        results_dir=_base.RESULTS_DIR,
    )
