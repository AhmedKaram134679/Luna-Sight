"""Solve and verify the LT+S apparent Earth-limb horizon crossing.

This adds a new validation stage only. It does not modify historical Horizons
exports, historical comparison scripts, or their recorded results. The solved
event is the maximum elevation of the point-wise retarded tangent limb of the
triaxial Earth ellipsoid, with stellar aberration applied at observer reception.
It is not the historical Horizons circular/equatorial-radius proxy.
"""
from __future__ import annotations

import importlib.util
import math
from pathlib import Path

import numpy as np
import spiceypy as spice
from scipy.optimize import brentq

ROOT = Path(__file__).resolve().parent
APPARENT_SCRIPT = ROOT / "verify_apparent_limb.py"
spec = importlib.util.spec_from_file_location("lunasight_apparent_limb", APPARENT_SCRIPT)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Cannot import apparent-limb reference from {APPARENT_SCRIPT}")
apparent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(apparent)

BRACKET_START_UTC = "2026-11-02T14:12:30"
BRACKET_END_UTC = "2026-11-02T14:13:00"
HISTORICAL_HORIZONS_PROXY_UTC = "2026-11-02T14:15:20.333553"
ROOT_TIME_TOLERANCE_SECONDS = 1.0e-4
ROOT_ELEVATION_TOLERANCE_DEG = 1.0e-8
LIMBPT_CROSSCHECK_TOLERANCE_ARCSEC = 0.05


def elevation_deg(et: float) -> float:
    return apparent.independent_apparent_max(float(et), "LT+S")[
        "reference_max_elevation_deg"
    ]


def utc_string(et: float) -> str:
    return str(spice.et2utc(float(et), "ISOC", 6))


def main() -> None:
    apparent.diag.load_kernels()
    temporary_spk = None
    try:
        temporary_spk, _ = apparent.diag.build_observer_spk()
        left = float(spice.str2et(BRACKET_START_UTC))
        right = float(spice.str2et(BRACKET_END_UTC))
        historical = float(spice.str2et(HISTORICAL_HORIZONS_PROXY_UTC))

        f_left = elevation_deg(left)
        f_right = elevation_deg(right)
        print("event_definition=LT+S_MAXIMUM_ELEVATION_OF_CONTINUOUS_POINTWISE_RETARDED_TANGENT_TRIAxIAL_ELLIPSOID")
        print("observer_site=longitude_200.0E_latitude_-88.45deg_altitude_0km")
        print(f"bracket_start_utc={BRACKET_START_UTC}")
        print(f"bracket_start_max_limb_elevation_deg={f_left:.12g}")
        print(f"bracket_end_utc={BRACKET_END_UTC}")
        print(f"bracket_end_max_limb_elevation_deg={f_right:.12g}")
        if not (math.isfinite(f_left) and math.isfinite(f_right) and f_left * f_right < 0.0):
            raise AssertionError("Crossing bracket does not contain a verified sign change.")

        root = float(
            brentq(
                elevation_deg,
                left,
                right,
                xtol=ROOT_TIME_TOLERANCE_SECONDS,
                rtol=4.0 * np.finfo(float).eps,
                maxiter=100,
                full_output=False,
                disp=True,
            )
        )
        root_elevation = elevation_deg(root)
        if abs(root_elevation) > ROOT_ELEVATION_TOLERANCE_DEG:
            raise AssertionError(
                f"Root elevation residual {root_elevation:.6e} deg exceeds "
                f"{ROOT_ELEVATION_TOLERANCE_DEG:.6e} deg"
            )

        half_window = 0.5
        before = elevation_deg(root - half_window)
        after = elevation_deg(root + half_window)
        slope_deg_s = (after - before) / (2.0 * half_window)
        if not (before > 0.0 and after < 0.0 and slope_deg_s < 0.0):
            raise AssertionError("Root is not a verified descending horizon crossing.")

        # Independent cross-check: evaluate the dense NAIF limbpt solution at
        # the continuous-reference root. Do not use limbpt to define the root.
        limbpt = apparent.limbpt_max(root, "LT+S")
        limbpt_elevation = float(limbpt["limbpt_max_elevation_deg"])
        crosscheck_arcsec = abs(limbpt_elevation - root_elevation) * 3600.0
        if crosscheck_arcsec > LIMBPT_CROSSCHECK_TOLERANCE_ARCSEC:
            raise AssertionError(
                f"limbpt cross-check differs by {crosscheck_arcsec:.6g} arcsec, "
                f"limit is {LIMBPT_CROSSCHECK_TOLERANCE_ARCSEC:.6g} arcsec"
            )

        delta_seconds = root - historical
        print(f"crossing_root_utc={utc_string(root)}")
        print(f"crossing_root_et_seconds_past_j2000_tdb={root:.9f}")
        print(f"root_max_limb_elevation_deg={root_elevation:.12g}")
        print(f"root_elevation_residual_deg={abs(root_elevation):.12g}")
        print(f"root_time_tolerance_seconds={ROOT_TIME_TOLERANCE_SECONDS:.12g}")
        print(f"elevation_at_root_minus_0.5s_deg={before:.12g}")
        print(f"elevation_at_root_plus_0.5s_deg={after:.12g}")
        print(f"local_elevation_slope_deg_per_second={slope_deg_s:.12g}")
        print(f"limbpt_max_elevation_at_continuous_root_deg={limbpt_elevation:.12g}")
        print(f"limbpt_crosscheck_difference_arcsec={crosscheck_arcsec:.12g}")
        print(f"limbpt_point_count={int(limbpt['limbpt_point_count'])}")
        print(f"historical_horizons_circular_proxy_utc={HISTORICAL_HORIZONS_PROXY_UTC}")
        print(f"apparent_ellipsoid_minus_historical_proxy_seconds={delta_seconds:.9f}")
        print(f"apparent_ellipsoid_minus_historical_proxy_minutes={delta_seconds / 60.0:.9f}")
        print("comparison_interpretation=DIFFERENT_LIMB_DEFINITIONS; time_delta_is_not_by_itself_an_error")
        print("historical_outputs_modified=NO")
        print("event_time_status=PASS")
        print("status=PASS")
    finally:
        if temporary_spk is not None:
            temporary_spk.cleanup()
        spice.kclear()


if __name__ == "__main__":
    main()
