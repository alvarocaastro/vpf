"""Unit tests for Stage 7 SFC improvement model."""

from __future__ import annotations

import math

import pytest

from vpf_analysis.stage7_sfc_analysis.engine.sfc_model import compute_sfc_improvement


def test_no_change_gives_zero_saving() -> None:
    result = compute_sfc_improvement(100.0, 100.0, 1e-5)
    assert result["fuel_saving_pct"] == pytest.approx(0.0, abs=1e-9)


def test_higher_clcd_gives_positive_saving() -> None:
    result = compute_sfc_improvement(100.0, 120.0, 1e-5)
    assert result["fuel_saving_pct"] > 0.0


def test_lower_clcd_gives_negative_saving() -> None:
    result = compute_sfc_improvement(100.0, 80.0, 1e-5)
    assert result["fuel_saving_pct"] < 0.0


def test_k_throttle_zero_equals_pure_thrust_reduction() -> None:
    # With k_throttle=0, SFC stays constant; fuel saving = 1 - F_ratio
    ref, new, sfc = 100.0, 125.0, 1e-5
    result = compute_sfc_improvement(ref, new, sfc, k_throttle=0.0)
    expected = (1.0 - ref / new) * 100.0
    assert result["fuel_saving_pct"] == pytest.approx(expected, rel=1e-6)


def test_f_ratio_correct() -> None:
    result = compute_sfc_improvement(80.0, 100.0, 1e-5)
    assert result["F_ratio"] == pytest.approx(80.0 / 100.0, rel=1e-9)


def test_return_keys_complete() -> None:
    result = compute_sfc_improvement(100.0, 110.0, 1e-5)
    required = {
        "ClCd_ref", "ClCd_new", "F_ratio",
        "SFC_design_kgNs", "SFC_new_kgNs",
        "SFC_improvement_pct", "fuel_saving_pct", "delta_SFC_kgNs",
    }
    assert required <= result.keys()
