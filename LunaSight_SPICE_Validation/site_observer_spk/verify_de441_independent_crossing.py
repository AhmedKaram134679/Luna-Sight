"""Independent stability and limbpt event-time cross-check for the DE441 LT+S limb.

Uses the existing continuous point-wise retarded tangent triaxial ellipsoid
model unchanged. All outputs are new and isolated; historical roots/exports
are never read as inputs to the solver or overwritten.
"""
from __future__ import annotations

import csv
import importlib.util
import json
import math
from pathlib import Path

import numpy as np
import spiceypy as spice
from scipy.optimize import brentq

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "verify_apparent_limb.py"
spec = importlib.util.spec_from_file_location("lunasight_apparent_limb", SOURCE)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Cannot import unchanged limb model: {SOURCE}")
model = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model)

START_UTC = "2026-11-02T14:12:30"
END_UTC = "2026-11-02T14:13:00"
SEARCH_STEPS_SECONDS = (2.0, 1.0, 0.5)
ROOT_TOLERANCES_SECONDS = (1.0e-3, 1.0e-4, 1.0e-5)
SIDE_OFFSET_SECONDS = 0.5
MAX_ROOT_SPREAD_SECONDS = 0.002
MAX_ROOT_RESIDUAL_DEG = 1.0e-7
MAX_LIMBPT_ROOT_DELTA_SECONDS = 0.002
MAX_ROOT_ELEVATION_DELTA_ARCSEC = 0.05
JSON_PATH = ROOT / "de441_independent_crossing_event_results.json"
CSV_PATH = ROOT / "de441_independent_crossing_event_results.csv"


def utc(et: float) -> str:
    return str(spice.et2utc(float(et), "ISOC", 9))


def solve(function, left: float, right: float, tolerance: float):
    f_left, f_right = float(function(left)), float(function(right))
    if not (math.isfinite(f_left) and math.isfinite(f_right) and f_left * f_right < 0.0):
        raise AssertionError(
            f"Strict sign-changing bracket required; got f(a)={f_left}, f(b)={f_right}"
        )
    root, info = brentq(
        function, left, right, xtol=tolerance,
        rtol=4.0 * np.finfo(float).eps, maxiter=100,
        full_output=True, disp=True,
    )
    if not info.converged:
        raise AssertionError(f"Brent solver failed: {info.flag}")
    return float(root), f_left, f_right, int(info.iterations), int(info.function_calls)


def find_bracket(function, start: float, end: float, step: float):
    count = int(math.ceil((end - start) / step))
    grid = np.linspace(start, end, count + 1)
    values = [float(function(float(t))) for t in grid]
    for i in range(len(grid) - 1):
        if values[i] * values[i + 1] < 0.0:
            return float(grid[i]), float(grid[i + 1])
    raise AssertionError(f"No crossing found at search spacing {step:g} seconds")


def main() -> None:
    model.diag.load_kernels()
    temporary_spk = None
    try:
        temporary_spk, _ = model.diag.build_observer_spk()
        start = float(spice.str2et(START_UTC))
        end = float(spice.str2et(END_UTC))
        continuous_cache: dict[float, float] = {}
        limbpt_cache: dict[float, float] = {}

        def continuous(et: float) -> float:
            key = float(et)
            if key not in continuous_cache:
                continuous_cache[key] = float(
                    model.independent_apparent_max(key, "LT+S")[
                        "reference_max_elevation_deg"
                    ]
                )
            value = continuous_cache[key]
            if not math.isfinite(value):
                raise RuntimeError(f"Non-finite continuous elevation at ET {key}")
            return value

        def limbpt(et: float) -> float:
            key = float(et)
            if key not in limbpt_cache:
                limbpt_cache[key] = float(
                    model.limbpt_max(key, "LT+S")["limbpt_max_elevation_deg"]
                )
            value = limbpt_cache[key]
            if not math.isfinite(value):
                raise RuntimeError(f"Non-finite limbpt elevation at ET {key}")
            return value

        bracket_results = []
        roots = []
        for step in SEARCH_STEPS_SECONDS:
            a, b = find_bracket(continuous, start, end, step)
            root, fa, fb, iterations, calls = solve(
                continuous, a, b, ROOT_TOLERANCES_SECONDS[1]
            )
            roots.append(root)
            bracket_results.append({
                "search_step_seconds": step,
                "bracket_start_utc": utc(a),
                "bracket_end_utc": utc(b),
                "f_start_deg": fa,
                "f_end_deg": fb,
                "root_utc": utc(root),
                "root_et": root,
                "residual_deg": continuous(root),
                "iterations": iterations,
                "function_calls": calls,
            })

        tolerance_results = []
        for tolerance in ROOT_TOLERANCES_SECONDS:
            root, fa, fb, iterations, calls = solve(
                continuous, start, end, tolerance
            )
            roots.append(root)
            tolerance_results.append({
                "xtol_seconds": tolerance,
                "root_utc": utc(root),
                "root_et": root,
                "residual_deg": continuous(root),
                "iterations": iterations,
                "function_calls": calls,
            })

        reference_root = tolerance_results[1]["root_et"]
        residual = continuous(reference_root)
        before = continuous(reference_root - SIDE_OFFSET_SECONDS)
        after = continuous(reference_root + SIDE_OFFSET_SECONDS)
        if not (before > 0.0 and after < 0.0):
            raise AssertionError("Continuous root is not bracketed by the required descending sign change.")
        if abs(residual) > MAX_ROOT_RESIDUAL_DEG:
            raise AssertionError(f"Root residual {residual:.6e} deg exceeds limit.")
        spread = float(max(roots) - min(roots))
        if spread > MAX_ROOT_SPREAD_SECONDS:
            raise AssertionError(f"Root varies by {spread:.9g}s across search/tolerance settings.")

        # Independent event extraction: solve the NAIF limbpt elevation function
        # itself, using the same LT+S correction and triaxial ellipsoid model.
        limbpt_a, limbpt_b = find_bracket(limbpt, start, end, SEARCH_STEPS_SECONDS[0])
        limbpt_root, limbpt_fa, limbpt_fb, limbpt_iterations, limbpt_calls = solve(
            limbpt, limbpt_a, limbpt_b, ROOT_TOLERANCES_SECONDS[1]
        )
        limbpt_residual = limbpt(limbpt_root)
        root_delta = abs(limbpt_root - reference_root)
        elevation_delta_arcsec = abs(limbpt_residual - residual) * 3600.0
        if root_delta > MAX_LIMBPT_ROOT_DELTA_SECONDS:
            raise AssertionError(f"Continuous and limbpt roots differ by {root_delta:.9g}s.")
        if elevation_delta_arcsec > MAX_ROOT_ELEVATION_DELTA_ARCSEC:
            raise AssertionError(f"Root residual difference is {elevation_delta_arcsec:.9g} arcsec.")

        result = {
            "status": "PASS",
            "event_definition": "LT+S maximum elevation of continuous point-wise retarded tangent triaxial Earth ellipsoid",
            "model_source": "verify_apparent_limb.py (unchanged)",
            "observer": {"longitude_deg_east": 200.0, "latitude_deg": -88.45, "altitude_km": 0.0},
            "interval_utc": [START_UTC, END_UTC],
            "continuous_root_utc": utc(reference_root),
            "continuous_root_et_tdb_seconds_past_j2000": reference_root,
            "continuous_root_residual_deg": residual,
            "elevation_at_root_minus_0_5s_deg": before,
            "elevation_at_root_plus_0_5s_deg": after,
            "local_slope_deg_per_second": (after - before) / (2.0 * SIDE_OFFSET_SECONDS),
            "root_spread_across_all_variants_seconds": spread,
            "search_step_results": bracket_results,
            "solver_tolerance_results": tolerance_results,
            "limbpt_independent_event": {
                "method": "NAIF limbpt TANGENT/ELLIPSOID, ELLIPSOID LIMB, LT+S",
                "bracket_start_utc": utc(limbpt_a),
                "bracket_end_utc": utc(limbpt_b),
                "bracket_start_elevation_deg": limbpt_fa,
                "bracket_end_elevation_deg": limbpt_fb,
                "root_utc": utc(limbpt_root),
                "root_et_tdb_seconds_past_j2000": limbpt_root,
                "root_residual_deg": limbpt_residual,
                "root_difference_from_continuous_seconds": root_delta,
                "root_residual_difference_arcsec": elevation_delta_arcsec,
                "iterations": limbpt_iterations,
                "function_calls": limbpt_calls,
                "ncuts": model.NCUTS,
            },
            "acceptance_limits": {
                "root_residual_deg": MAX_ROOT_RESIDUAL_DEG,
                "root_spread_seconds": MAX_ROOT_SPREAD_SECONDS,
                "limbpt_root_difference_seconds": MAX_LIMBPT_ROOT_DELTA_SECONDS,
                "root_residual_difference_arcsec": MAX_ROOT_ELEVATION_DELTA_ARCSEC,
            },
            "continuous_function_evaluations": len(continuous_cache),
            "limbpt_function_evaluations": len(limbpt_cache),
            "historical_roots_modified": False,
            "historical_horizons_outputs_modified": False,
        }
        JSON_PATH.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        with CSV_PATH.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(["method", "resolution_seconds", "root_utc", "root_et", "residual_deg"])
            for row in bracket_results:
                writer.writerow(["continuous_search_step", row["search_step_seconds"], row["root_utc"], row["root_et"], row["residual_deg"]])
            for row in tolerance_results:
                writer.writerow(["continuous_solver_xtol", row["xtol_seconds"], row["root_utc"], row["root_et"], row["residual_deg"]])
            writer.writerow(["independent_limbpt", SEARCH_STEPS_SECONDS[0], utc(limbpt_root), limbpt_root, limbpt_residual])

        print("event_definition=" + result["event_definition"])
        print("continuous_root_utc=" + utc(reference_root))
        print(f"continuous_root_residual_deg={residual:.12g}")
        print(f"elevation_before_root_deg={before:.12g}")
        print(f"elevation_after_root_deg={after:.12g}")
        print(f"root_spread_across_variants_seconds={spread:.12g}")
        print("limbpt_method=NAIF_TANGENT/ELLIPSOID_ELLIPSOID_LIMB_LT+S")
        print("limbpt_root_utc=" + utc(limbpt_root))
        print(f"limbpt_root_difference_seconds={root_delta:.12g}")
        print(f"limbpt_root_residual_deg={limbpt_residual:.12g}")
        print(f"continuous_evaluations={len(continuous_cache)}")
        print(f"limbpt_evaluations={len(limbpt_cache)}")
        print("sign_change=PASS")
        print("root_residual=PASS")
        print("search_step_stability=PASS")
        print("solver_tolerance_stability=PASS")
        print("independent_limbpt_event=PASS")
        print("historical_roots_modified=NO")
        print("historical_horizons_outputs_modified=NO")
        print("json_output=" + JSON_PATH.name)
        print("csv_output=" + CSV_PATH.name)
        print("status=PASS")
    finally:
        if temporary_spk is not None:
            temporary_spk.cleanup()
        spice.kclear()


if __name__ == "__main__":
    main()
