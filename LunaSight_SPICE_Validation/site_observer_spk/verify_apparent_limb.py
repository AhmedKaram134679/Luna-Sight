"""Independent apparent Earth-limb reference for SPICE LT and LT+S.

Validation only. The reference optimizes over a continuously parameterized
triaxial ellipsoid surface and solves each candidate point's retarded epoch;
it does not use limbpt points to construct its reference solution.
"""
from __future__ import annotations

import importlib.util
import math
from pathlib import Path

import numpy as np
import spiceypy as spice
from scipy.optimize import minimize

ROOT = Path(__file__).resolve().parent
sys_path = ROOT / "verify_limbpt_and_geometry.py"
spec = importlib.util.spec_from_file_location("lunasight_geometry_diagnostics", sys_path)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Cannot import shared diagnostic helpers from {sys_path}")
diag = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diag)

C_KM_S = 299792.458
NCUTS = 5760
MAX_DIFFERENCE_ARCSEC = 0.05
TIMES_UTC = (
    "2026-11-02T14:12:30",
    "2026-11-02T14:13:00",
    "2026-11-02T14:14:00",
    "2026-11-02T14:15:00",
    "2026-11-02T14:15:20",
    "2026-11-02T14:15:21",
    "2026-11-02T14:16:00",
)


def unit(vector: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vector))
    if not math.isfinite(norm) or norm <= 0.0:
        raise RuntimeError("Cannot normalize a zero or invalid vector.")
    return vector / norm


def local_up_j2000(et: float) -> np.ndarray:
    site = diag.independent_geodetic_point()
    radii = np.asarray(spice.bodvrd("MOON", "RADII", 3)[1], dtype=float)
    normal = unit(site / (radii * radii))
    return unit(np.asarray(spice.pxform("MOON_ME", "J2000", et)) @ normal)


def observer_state(et: float) -> tuple[np.ndarray, np.ndarray]:
    state, _ = spice.spkezr(
        diag.SITE_NAME, et, "J2000", "NONE", "SOLAR SYSTEM BARYCENTER"
    )
    state = np.asarray(state, dtype=float)
    return state[:3], state[3:]


def surface_point(radii: np.ndarray, lon: float, lat: float) -> np.ndarray:
    c = math.cos(lat)
    return radii * np.array(
        [c * math.cos(lon), c * math.sin(lon), math.sin(lat)], dtype=float
    )


def initial_geometric_seed(et: float) -> tuple[float, float]:
    """Find a global geometric tangent-limb maximum to seed the apparent solve."""
    from scipy.optimize import minimize_scalar

    radii = np.asarray(spice.bodvrd("EARTH", "RADII", 3)[1], dtype=float)
    obs, _ = observer_state(et)
    earth, _ = spice.spkezr("EARTH", et, "J2000", "NONE", "SOLAR SYSTEM BARYCENTER")
    earth = np.asarray(earth, dtype=float)[:3]
    observer_fixed = np.asarray(spice.pxform("J2000", "ITRF93", et)) @ (obs - earth)
    scaled = observer_fixed / radii
    norm_sq = float(np.dot(scaled, scaled))
    if norm_sq <= 1.0:
        raise RuntimeError("Observer lies inside the Earth ellipsoid.")
    axis = unit(scaled)
    circle_center = scaled / norm_sq
    circle_radius = math.sqrt(1.0 - 1.0 / norm_sq)
    helper = np.array([0.0, 0.0, 1.0])
    if abs(float(np.dot(axis, helper))) > 0.9:
        helper = np.array([0.0, 1.0, 0.0])
    u = unit(np.cross(axis, helper))
    v = np.cross(axis, u)
    up = local_up_j2000(et)

    def point_at(angle: float) -> np.ndarray:
        y = circle_center + circle_radius * (u * math.cos(angle) + v * math.sin(angle))
        return radii * y

    def elevation(angle: float) -> float:
        p = earth + np.asarray(spice.pxform("ITRF93", "J2000", et)) @ point_at(angle)
        return math.asin(float(np.clip(np.dot(unit(p - obs), up), -1.0, 1.0)))

    count = 8192
    grid = np.linspace(0.0, 2.0 * math.pi, count, endpoint=False)
    vals = np.fromiter((elevation(float(a)) for a in grid), dtype=float)
    i = int(np.argmax(vals))
    step = 2.0 * math.pi / count
    center = float(grid[i])
    opt = minimize_scalar(
        lambda d: -elevation((center + d) % (2.0 * math.pi)),
        bounds=(-step, step),
        method="bounded",
        options={"xatol": 1.0e-14},
    )
    p = point_at((center + float(opt.x)) % (2.0 * math.pi))
    lon = math.atan2(float(p[1] / radii[1]), float(p[0] / radii[0]))
    lat = math.asin(float(np.clip(p[2] / radii[2], -1.0, 1.0)))
    return lon, lat


def independent_apparent_max(et: float, correction: str) -> dict[str, float]:
    """Optimize apparent elevation over the ellipsoid with point-wise light time.

    Reception observer state is fixed at et. For every candidate surface point,
    solve the retarded emission epoch with two Newtonian light-time iterations,
    transform that point using the Earth-fixed frame at emission, and for LT+S
    apply NAIF stellar aberration using the observer's SSB velocity at reception.
    """
    if correction not in ("LT", "LT+S"):
        raise ValueError(f"Unsupported correction: {correction}")
    radii = np.asarray(spice.bodvrd("EARTH", "RADII", 3)[1], dtype=float)
    obs, obs_vel = observer_state(et)
    up = local_up_j2000(et)
    lon0, lat0 = initial_geometric_seed(et)

    def evaluate(params: np.ndarray) -> tuple[float, float]:
        lon = float(params[0])
        lat = float(params[1])
        if lat <= -math.pi / 2.0 or lat >= math.pi / 2.0:
            return -math.pi, et
        fixed = surface_point(radii, lon, lat)
        center_at_reception, _ = spice.spkezr(
            "EARTH", et, "J2000", "NONE", "SOLAR SYSTEM BARYCENTER"
        )
        center_at_reception = np.asarray(center_at_reception, dtype=float)[:3]
        light_time = float(np.linalg.norm(center_at_reception - obs) / C_KM_S)
        # Match NAIF LT's documented two-iteration Newtonian light-time solve.
        for _ in range(2):
            emission_et = et - light_time
            center_state, _ = spice.spkezr(
                "EARTH", emission_et, "J2000", "NONE", "SOLAR SYSTEM BARYCENTER"
            )
            center = np.asarray(center_state, dtype=float)[:3]
            rotation = np.asarray(spice.pxform("ITRF93", "J2000", emission_et))
            point_ssb = center + rotation @ fixed
            light_time = float(np.linalg.norm(point_ssb - obs) / C_KM_S)
        emission_et = et - light_time
        center_state, _ = spice.spkezr(
            "EARTH", emission_et, "J2000", "NONE", "SOLAR SYSTEM BARYCENTER"
        )
        center = np.asarray(center_state, dtype=float)[:3]
        rotation = np.asarray(spice.pxform("ITRF93", "J2000", emission_et))
        point_ssb = center + rotation @ fixed
        ray = point_ssb - obs
        if correction == "LT+S":
            ray = np.asarray(spice.stelab(ray, obs_vel), dtype=float)
        elevation = math.asin(float(np.clip(np.dot(unit(ray), up), -1.0, 1.0)))
        return elevation, emission_et

    def objective(params: np.ndarray) -> float:
        return -evaluate(params)[0]

    bounds = (
        (lon0 - 0.05, lon0 + 0.05),
        (max(-math.pi / 2 + 1.0e-8, lat0 - 0.05),
         min(math.pi / 2 - 1.0e-8, lat0 + 0.05)),
    )
    result = minimize(
        objective,
        np.array([lon0, lat0], dtype=float),
        method="Powell",
        bounds=bounds,
        options={"xtol": 1.0e-11, "ftol": 1.0e-14, "maxiter": 500},
    )
    elevation, emission_et = evaluate(np.asarray(result.x, dtype=float))
    if not result.success:
        raise RuntimeError(
            f"Independent {correction} optimizer did not converge: {result.message}"
        )
    if any(
        abs(float(result.x[i]) - bounds[i][j]) < 1.0e-7
        for i in range(2) for j in (0, 1)
    ):
        raise RuntimeError(f"Independent {correction} optimum hit search boundary.")
    return {
        "reference_max_elevation_deg": math.degrees(elevation),
        "reference_emission_et": emission_et,
        "reference_light_time_seconds": et - emission_et,
        "optimizer_iterations": float(getattr(result, "nit", -1)),
        "optimizer_evaluations": float(getattr(result, "nfev", -1)),
    }


def limbpt_max(et: float, correction: str) -> dict[str, float]:
    """Get limbpt's highest-elevation point and its associated emission epoch."""
    ncuts = NCUTS
    center_vec, _ = spice.spkpos("EARTH", et, "ITRF93", "NONE", diag.SITE_NAME)
    center_vec = np.asarray(center_vec, dtype=float)
    helper = np.array([0.0, 0.0, 1.0])
    if abs(float(np.dot(unit(center_vec), helper))) > 0.9:
        helper = np.array([0.0, 1.0, 0.0])
    refvec = unit(np.cross(center_vec, helper))
    npts, points, epochs, _ = spice.limbpt(
        "TANGENT/ELLIPSOID", "EARTH", et, "ITRF93", correction,
        "ELLIPSOID LIMB", diag.SITE_NAME, refvec,
        2.0 * math.pi / ncuts, ncuts, math.radians(1.0), 1.0e-10, 4 * ncuts,
    )
    points = np.asarray(points, dtype=float)
    epochs = np.asarray(epochs, dtype=float)
    count = int(np.sum(np.asarray(npts, dtype=int).reshape(-1)))
    if count <= 0:
        raise RuntimeError(f"limbpt returned no points for {correction} at {et}")
    obs, obs_vel = observer_state(et)
    up = local_up_j2000(et)
    elevations = []
    for i in range(count):
        limb_et = float(epochs[i])
        center_state, _ = spice.spkezr(
            "EARTH", limb_et, "J2000", "NONE", "SOLAR SYSTEM BARYCENTER"
        )
        center = np.asarray(center_state, dtype=float)[:3]
        rotation = np.asarray(spice.pxform("ITRF93", "J2000", limb_et))
        point = center + rotation @ points[i]
        ray = point - obs
        if correction == "LT+S":
            ray = np.asarray(spice.stelab(ray, obs_vel), dtype=float)
        elevations.append(math.asin(float(np.clip(np.dot(unit(ray), up), -1.0, 1.0))))
    i_max = int(np.argmax(elevations))
    return {
        "limbpt_max_elevation_deg": math.degrees(elevations[i_max]),
        "limbpt_max_point_emission_et": float(epochs[i_max]),
        "limbpt_epoch_span_seconds": float(np.max(epochs[:count]) - np.min(epochs[:count])),
        "limbpt_point_count": float(count),
    }


def main() -> None:
    diag.load_kernels()
    temporary_spk = None
    failures = []
    try:
        temporary_spk, _ = diag.build_observer_spk()
        print("reference_model=CONTINUOUS_TRIAxIAL_SURFACE_POINTWISE_LT")
        print("stellar_aberration=NAIF_STELAB_WITH_OBSERVER_SSB_VELOCITY_AT_RECEPTION")
        print(f"limbpt_ncuts={NCUTS}")
        print(f"acceptance_tolerance_arcsec={MAX_DIFFERENCE_ARCSEC}")
        for utc in TIMES_UTC:
            et = float(spice.str2et(utc))
            print(f"epoch_utc={utc}")
            for correction in ("LT", "LT+S"):
                reference = independent_apparent_max(et, correction)
                candidate = limbpt_max(et, correction)
                delta_arcsec = abs(
                    reference["reference_max_elevation_deg"]
                    - candidate["limbpt_max_elevation_deg"]
                ) * 3600.0
                epoch_delta = abs(
                    reference["reference_emission_et"]
                    - candidate["limbpt_max_point_emission_et"]
                )
                print(f"abcorr={correction}")
                for key, value in reference.items():
                    print(f"{key}={value:.12g}")
                for key, value in candidate.items():
                    print(f"{key}={value:.12g}")
                print(f"max_elevation_difference_arcsec={delta_arcsec:.12g}")
                print(f"reference_vs_limbpt_max_point_epoch_difference_seconds={epoch_delta:.12g}")
                passed = delta_arcsec <= MAX_DIFFERENCE_ARCSEC
                print(f"comparison_status={'PASS' if passed else 'FAIL'}")
                if not passed:
                    failures.append((utc, correction, delta_arcsec))
        if failures:
            details = "; ".join(f"{utc} {corr}: {delta:.6g} arcsec" for utc, corr, delta in failures)
            raise AssertionError(f"Independent apparent-limb comparison failed: {details}")
        print("event_time_status=NOT_EVALUATED")
        print("status=PASS")
    finally:
        if temporary_spk is not None:
            temporary_spk.cleanup()
        spice.kclear()


if __name__ == "__main__":
    main()
