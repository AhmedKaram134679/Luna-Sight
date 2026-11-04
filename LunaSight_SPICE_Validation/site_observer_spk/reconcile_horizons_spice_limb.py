"""Reconcile SPICE Earth-limb crossing definitions against the historical Horizons proxy.

This is an additive validation stage. It never edits historical Horizons exports.
The circular model is a SPICE-derived equatorial-angular-radius proxy, not a
claim to reproduce Horizons' solar gravitational deflection or DE441 exactly.
"""
from __future__ import annotations

import importlib.util
import math
import os
from pathlib import Path

import numpy as np
import spiceypy as spice
from scipy.optimize import brentq, minimize

ROOT = Path(__file__).resolve().parent
APPARENT_PATH = ROOT / "verify_apparent_limb.py"
spec = importlib.util.spec_from_file_location("lunasight_apparent_limb", APPARENT_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Cannot import {APPARENT_PATH}")
apparent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(apparent)
diag = apparent.diag

START_UTC = "2026-11-02T14:12:30"
STOP_UTC = "2026-11-02T14:16:00"
HORIZONS_ROOT_UTC = "2026-11-02T14:15:20.333553"
EARTH_EQUATORIAL_RADIUS_KM = 6378.137
TIME_TOLERANCE_SECONDS = 1.0e-4
ELEVATION_TOLERANCE_DEG = 1.0e-8
C_KM_S = 299792.458


def utc(et: float) -> str:
    return str(spice.et2utc(float(et), "ISOC", 6))


def geometric_ellipsoid_max(et: float) -> float:
    """Maximum elevation of the instantaneous geometric tangent ellipsoid."""
    radii = np.asarray(spice.bodvrd("EARTH", "RADII", 3)[1], dtype=float)
    observer, _ = apparent.observer_state(et)
    earth_state, _ = spice.spkezr(
        "EARTH", et, "J2000", "NONE", "SOLAR SYSTEM BARYCENTER"
    )
    earth = np.asarray(earth_state, dtype=float)[:3]
    rotation = np.asarray(spice.pxform("ITRF93", "J2000", et), dtype=float)
    observer_fixed = rotation.T @ (observer - earth)
    scaled = observer_fixed / radii
    norm_sq = float(np.dot(scaled, scaled))
    if norm_sq <= 1.0:
        raise RuntimeError("Observer is inside Earth ellipsoid.")
    axis = scaled / math.sqrt(norm_sq)
    center = scaled / norm_sq
    circle_radius = math.sqrt(1.0 - 1.0 / norm_sq)
    helper = np.array([0.0, 0.0, 1.0])
    if abs(float(np.dot(axis, helper))) > 0.9:
        helper = np.array([0.0, 1.0, 0.0])
    u = np.cross(axis, helper)
    u /= np.linalg.norm(u)
    v = np.cross(axis, u)
    up = apparent.local_up_j2000(et)

    def point(angle: float) -> np.ndarray:
        y = center + circle_radius * (u * math.cos(angle) + v * math.sin(angle))
        return radii * y

    def elev(angle: float) -> float:
        p = earth + rotation @ point(angle)
        ray = p - observer
        return math.asin(float(np.clip(np.dot(ray / np.linalg.norm(ray), up), -1, 1)))

    count = 8192
    grid = np.linspace(0.0, 2.0 * math.pi, count, endpoint=False)
    vals = np.fromiter((elev(float(a)) for a in grid), dtype=float)
    idx = int(np.argmax(vals))
    step = 2.0 * math.pi / count
    result = minimize(
        lambda x: -elev(float(x[0])),
        np.array([float(grid[idx])]),
        method="Nelder-Mead",
        options={"xatol": 1.0e-13, "fatol": 1.0e-15, "maxiter": 300},
    )
    if not result.success:
        raise RuntimeError(f"Geometric limb optimizer failed: {result.message}")
    return math.degrees(elev(float(result.x[0])))


def circle_margin(et: float, correction: str) -> float:
    """Center apparent elevation plus equatorial angular radius."""
    if correction not in ("NONE", "LT", "LT+S"):
        raise ValueError(correction)
    state, _ = spice.spkezr(
        "EARTH", et, "J2000", correction, diag.SITE_NAME
    )
    ray = np.asarray(state, dtype=float)[:3]
    if correction == "LT+S":
        # spkezr already applies stellar aberration; do not apply stelab again.
        pass
    up = apparent.local_up_j2000(et)
    center_elevation = math.asin(
        float(np.clip(np.dot(ray / np.linalg.norm(ray), up), -1.0, 1.0))
    )
    angular_radius = math.asin(
        min(1.0, EARTH_EQUATORIAL_RADIUS_KM / float(np.linalg.norm(ray)))
    )
    return math.degrees(center_elevation + angular_radius)


def solve(label: str, function, left: float, right: float) -> tuple[float, float]:
    fl, fr = float(function(left)), float(function(right))
    if not (math.isfinite(fl) and math.isfinite(fr) and fl * fr < 0.0):
        raise AssertionError(
            f"{label}: no sign-changing bracket: f(left)={fl:.12g}, f(right)={fr:.12g}"
        )
    root = float(brentq(
        function, left, right, xtol=TIME_TOLERANCE_SECONDS,
        rtol=4.0 * np.finfo(float).eps, maxiter=100
    ))
    residual = abs(float(function(root)))
    if residual > ELEVATION_TOLERANCE_DEG:
        raise AssertionError(f"{label}: root residual {residual:.6g} deg")
    print(f"{label}_root_utc={utc(root)}")
    print(f"{label}_root_et={root:.9f}")
    print(f"{label}_root_residual_deg={residual:.12g}")
    print(f"{label}_bracket_start_margin_deg={fl:.12g}")
    print(f"{label}_bracket_end_margin_deg={fr:.12g}")
    return root, residual


def main() -> None:
    diag.load_kernels()
    temporary_spk = None
    try:
        temporary_spk, _ = diag.build_observer_spk()
        left, right = float(spice.str2et(START_UTC)), float(spice.str2et(STOP_UTC))
        historical = float(spice.str2et(HORIZONS_ROOT_UTC))
        print("phase=HORIZONS_SPICE_LIMB_DEFINITION_RECONCILIATION")
        print("site=longitude_200.0E_latitude_-88.45deg_altitude_0km")
        print("earth_radii_km=6378.137,6378.137,6356.752")
        print("historical_horizons_reference=2026-11-02T14:15:20.333553_UTC")
        selected_spks = diag.selected_planetary_spk_paths()
        print("spice_planetary_spk_files=" + ";".join(path.name for path in selected_spks))
        print("spice_planetary_spk_selection=" + ("ENV_LUNASIGHT_PLANETARY_SPKS" if os.environ.get("LUNASIGHT_PLANETARY_SPKS", "").strip() else "DEFAULT_DE440S"))
        print("historical_horizons_ephemeris=DE441")
        print("circular_proxy=SPICE_apparent_center_plus_equatorial_angular_radius")
        print("circular_proxy_is_exact_horizons_reproduction=NO")

        roots = {}
        roots["circle_none"], _ = solve(
            "circle_none", lambda t: circle_margin(t, "NONE"), left, right
        )
        roots["circle_lt"], _ = solve(
            "circle_lt", lambda t: circle_margin(t, "LT"), left, right
        )
        roots["circle_lt_s"], _ = solve(
            "circle_lt_s", lambda t: circle_margin(t, "LT+S"), left, right
        )
        roots["ellipsoid_none"], _ = solve(
            "ellipsoid_none", geometric_ellipsoid_max, left, right
        )
        roots["ellipsoid_lt"], _ = solve(
            "ellipsoid_lt",
            lambda t: apparent.independent_apparent_max(t, "LT")["reference_max_elevation_deg"],
            left, right,
        )
        roots["ellipsoid_lt_s"], _ = solve(
            "ellipsoid_lt_s",
            lambda t: apparent.independent_apparent_max(t, "LT+S")["reference_max_elevation_deg"],
            left, right,
        )

        print("component_deltas_seconds=SEQUENTIAL_NOT_ASSUMED_INDEPENDENT")
        order = (
            "circle_none", "circle_lt", "circle_lt_s",
            "ellipsoid_none", "ellipsoid_lt", "ellipsoid_lt_s",
        )
        for previous, current in zip(order, order[1:]):
            print(f"delta_{previous}_to_{current}_seconds={roots[current]-roots[previous]:.9f}")
        for name, root in roots.items():
            print(f"{name}_minus_horizons_seconds={root-historical:.9f}")
        print(f"ellipsoid_lt_s_minus_horizons_seconds={roots['ellipsoid_lt_s']-historical:.9f}")
        print("historical_outputs_modified=NO")
        print("status=PASS")
    finally:
        if temporary_spk is not None:
            temporary_spk.cleanup()
        spice.kclear()


if __name__ == "__main__":
    main()
