"""Critical Mach number estimation for subsonic airfoils."""

from __future__ import annotations


def estimate_mdd(cl_operating: float, thickness_ratio: float, korn_kappa: float) -> float:
    """Drag-divergence Mach via Korn's equation: Mdd = κ/t_c - CL/10 - t_c/10."""
    mdd = korn_kappa - thickness_ratio - cl_operating / 10.0
    return max(0.50, min(mdd, 0.99))


def estimate_mcr(
    cl_operating: float,
    thickness_ratio: float = 0.10,
    korn_kappa: float = 0.87,
) -> float:
    """Critical Mach derived from Mdd (Mcr ≈ Mdd − 0.02).

    Using Korn's equation instead of the old Küchemann hardcode makes Mcr
    consistent with the wave-drag model and correct for any airfoil family.
    """
    mdd = estimate_mdd(cl_operating, thickness_ratio, korn_kappa)
    return max(0.50, min(mdd - 0.02, 0.99))


def wave_drag_increment(mach: float, mdd: float) -> float:
    """Wave drag increment via Lock's 4th-power law, capped at 250 drag counts.

        ΔCDw = 20 × (M − Mdd)^4   if M > Mdd, else 0

    Cap of 0.025 prevents unphysical values far above Mdd where the 2-D
    subsonic model is already beyond its validity boundary.
    """
    if mach <= mdd:
        return 0.0
    return min(20.0 * (mach - mdd) ** 4, 0.025)
