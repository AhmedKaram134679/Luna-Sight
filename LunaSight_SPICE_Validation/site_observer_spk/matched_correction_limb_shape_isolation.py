"""Matched-correction isolation of circular versus triaxial Earth limbs.

Validation-only stage. It solves all six existing SPICE models with the same
site, ephemeris kernels, reception-time bracket, local-up convention and root
solver. It reports shape-only paired differences within each aberration
correction. It does NOT claim to reproduce Horizons gravitational deflection.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import spiceypy as spice
from scipy.optimize import brentq

import reconcile_horizons_spice_limb as models

START_UTC = "2026-11-02T14:12:30"
STOP_UTC = "2026-11-02T14:16:00"
ROOT_TIME_TOLERANCE_SECONDS = 1.0e-4
ROOT_MARGIN_TOLERANCE_DEG = 1.0e-8


def solve_root(label: str, function, left: float, right: float) -> tuple[float, float]:
    f_left = float(function(left))
    f_right = float(function(right))
    if not (math.isfinite(f_left) and math.isfinite(f_right) and f_left * f_right < 0.0):
        raise AssertionError(
            f"{label}: expected a finite sign-changing bracket; "
            f"left={f_left:.12g}, right={f_right:.12g}"
        )
    root = float(brentq(
        function, left, right, xtol=ROOT_TIME_TOLERANCE_SECONDS,
        rtol=4.0 * np.finfo(float).eps, maxiter=100,
    ))
    residual = abs(float(function(root)))
    if residual > ROOT_MARGIN_TOLERANCE_DEG:
        raise AssertionError(f"{label}: root margin residual {residual:.6g} deg")
    print(f"{label}_root_utc={spice.et2utc(root, 'ISOC', 6)}")
    print(f"{label}_root_et_tdb={root:.9f}")
    print(f"{label}_root_margin_residual_deg={residual:.12g}")
    print(f"{label}_bracket_start_margin_deg={f_left:.12g}")
    print(f"{label}_bracket_end_margin_deg={f_right:.12g}")
    return root, residual


def main() -> None:
    models.diag.load_kernels()
    temporary_spk = None
    try:
        temporary_spk, _ = models.diag.build_observer_spk()
        left = float(spice.str2et(START_UTC))
        right = float(spice.str2et(STOP_UTC))

        print("phase=MATCHED_CORRECTION_LIMB_SHAPE_ISOLATION")
        print("site=longitude_200.0E_latitude_-88.45deg_altitude_0km")
        print("ephemeris=DE440s_for_all_six_models")
        print("observer_state=shared_LunaSight_surface_observer_SPK")
        print("local_up=shared_MOON_ME_geodetic_surface_normal_at_reception")
        print("root_solver=brentq_same_bracket_xtol_1e-4_seconds")
        print("circle_definition=apparent_Earth_center_elevation_plus_equatorial_angular_radius")
        print("ellipsoid_definition=maximum_elevation_of_tangent_triaxial_ellipsoid_limb")

        functions = {
            "NONE": (
                lambda t: models.circle_margin(t, "NONE"),
                models.geometric_ellipsoid_max,
            ),
            "LT": (
                lambda t: models.circle_margin(t, "LT"),
                lambda t: models.apparent.independent_apparent_max(t, "LT")[
                    "reference_max_elevation_deg"
                ],
            ),
            "LT+S": (
                lambda t: models.circle_margin(t, "LT+S"),
                lambda t: models.apparent.independent_apparent_max(t, "LT+S")[
                    "reference_max_elevation_deg"
                ],
            ),
        }

        roots: dict[str, float] = {}
        for correction, (circle_fn, ellipsoid_fn) in functions.items():
            print(f"matched_correction={correction}")
            circle_root, _ = solve_root(
                f"circle_{correction.lower().replace('+', '_')}",
                circle_fn, left, right,
            )
            ellipsoid_root, _ = solve_root(
                f"ellipsoid_{correction.lower().replace('+', '_')}",
                ellipsoid_fn, left, right,
            )
            delta = ellipsoid_root - circle_root
            roots[correction] = delta
            print(f"shape_only_ellipsoid_minus_circle_seconds={delta:.9f}")
            print(f"shape_only_ellipsoid_minus_circle_minutes={delta / 60.0:.9f}")

        print("cross_correction_interaction_check=NOT_ASSUMED_ADDITIVE")
        print(f"shape_delta_NONE_seconds={roots['NONE']:.9f}")
        print(f"shape_delta_LT_seconds={roots['LT']:.9f}")
        print(f"shape_delta_LT_PLUS_S_seconds={roots['LT+S']:.9f}")
        print(
            "LT_PLUS_S_shape_interaction_vs_LT_seconds="
            f"{roots['LT+S'] - roots['LT']:.9f}"
        )
        print(
            "LT_shape_interaction_vs_NONE_seconds="
            f"{roots['LT'] - roots['NONE']:.9f}"
        )
        print(
            "LT_PLUS_S_shape_interaction_vs_NONE_seconds="
            f"{roots['LT+S'] - roots['NONE']:.9f}"
        )

        # This is an explicit model-coverage audit, not a numerical estimate.
        # The historical Horizons export states Rel. light bend: Sun, EARTH.
        # Current SPICE models use geometric/light-time/stellar-aberration
        # corrections only; no gravitational deflection operator is applied.
        print("historical_horizons_relativistic_light_bend=Sun,EARTH")
        print("spice_gravitational_light_deflection=NOT_MODELED_IN_THIS_STAGE")
        print("spice_vs_horizons_gravitational_deflection_match=NOT_ESTABLISHED")
        print("de440s_vs_de441_effect_isolation=NOT_YET_VALID")
        print("historical_horizons_exports_modified=NO")
        print("main_branch_modified=NO")
        print("shape_isolation_status=PASS")
        print("gravity_deflection_reconciliation_status=PENDING")
        print("overall_interpretation=SHAPE_EFFECT_ISOLATED_WITHIN_EACH_SPICE_CORRECTION_ONLY")
    finally:
        if temporary_spk is not None:
            temporary_spk.cleanup()
        spice.kclear()


if __name__ == "__main__":
    main()
