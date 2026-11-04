"""Independent geometry and SPICE limbpt diagnostics for LunaSight.

This is a validation-only diagnostic. It does not solve for or certify an
Earth-limb crossing time and does not modify historical comparison outputs.
"""
from __future__ import annotations

import math
import os
import tempfile
from pathlib import Path

import numpy as np
import spiceypy as spice

ROOT = Path(__file__).resolve().parent
VALIDATION_ROOT = ROOT.parent
KERNEL_DIR = VALIDATION_ROOT / "kernels"
SPK_SCRIPT = ROOT / "verify_surface_observer.py"

SITE_NAME = "LUNASIGHT_SURFACE_OBSERVER"
SITE_ID = -999001
MOON_ID = 301
SITE_LON_DEG = 200.0
SITE_LAT_DEG = -88.45
SITE_ALT_KM = 0.0
MOON_FRAME = "MOON_ME"
INERTIAL_FRAME = "J2000"
EARTH_FRAME = "ITRF93"
TEST_UTC = "2026-11-02T14:14:00"
C_KM_S = 299792.458

KERNEL_FILES = (
    "naif0012.tls",
    "pck00011.tpc",
    "moon_pa_de440_200625.bpc",
    "moon_de440_220930.tf",
    "earth_latest_high_prec.bpc",
    "earth_assoc_itrf93.tf",
)
GEOMETRY_POSITION_TOL_KM = 1.0e-7
GEOMETRY_VELOCITY_TOL_KM_S = 2.0e-8
CHAIN_POSITION_TOL_KM = 1.0e-6
CHAIN_VELOCITY_TOL_KM_S = 1.0e-9


def load_kernels() -> None:
    missing = [name for name in KERNEL_FILES if not (KERNEL_DIR / name).is_file()]
    if missing:
        raise FileNotFoundError(
            f"Missing required kernels in {KERNEL_DIR}: {', '.join(missing)}"
        )
    for name in KERNEL_FILES:
        path = KERNEL_DIR / name
        if path.stat().st_size == 0:
            raise RuntimeError(f"Kernel is empty: {path}")
        spice.furnsh(str(path))

    # The planetary ephemeris is independently selectable so the same
    # validation suite can be run against the historical DE440s baseline and
    # a separately provisioned DE441 pair without changing lunar-orientation
    # kernels or silently renaming one ephemeris as the other.
    configured_spks = os.environ.get("LUNASIGHT_PLANETARY_SPKS", "").strip()
    planetary_spks = (
        [Path(item).expanduser().resolve() for item in configured_spks.split(os.pathsep) if item]
        if configured_spks
        else [KERNEL_DIR / "de440s.bsp"]
    )
    if not planetary_spks:
        raise RuntimeError("LUNASIGHT_PLANETARY_SPKS contains no usable paths.")
    for path in planetary_spks:
        if not path.is_file() or path.stat().st_size == 0:
            raise FileNotFoundError(f"Missing or empty planetary SPK: {path}")
        spice.furnsh(str(path))


def independent_geodetic_point() -> np.ndarray:
    """Use CSPICE georec as an independent geodetic-to-Cartesian implementation."""
    radii = np.asarray(spice.bodvrd("MOON", "RADII", 3)[1], dtype=float)
    # georec models a spheroid. Do not silently use it for a triaxial body.
    if not np.allclose(radii[0], radii[1], rtol=0.0, atol=1.0e-12):
        raise RuntimeError(
            "MOON radii are not spheroidal in this kernel set; georec is not "
            "a valid independent mapping for this body model."
        )
    flattening = float((radii[0] - radii[2]) / radii[0])
    return np.asarray(
        spice.georec(
            math.radians(SITE_LON_DEG),
            math.radians(SITE_LAT_DEG),
            SITE_ALT_KM,
            float(radii[0]),
            flattening,
        ),
        dtype=float,
    )


def current_script_site_point() -> np.ndarray:
    """Reproduce the existing script's radial-normal construction for comparison."""
    radii = np.asarray(spice.bodvrd("MOON", "RADII", 3)[1], dtype=float)
    lon = math.radians(SITE_LON_DEG)
    lat = math.radians(SITE_LAT_DEG)
    normal = np.array(
        [math.cos(lat) * math.cos(lon), math.cos(lat) * math.sin(lon), math.sin(lat)],
        dtype=float,
    )
    normal /= np.linalg.norm(normal)
    denominator = math.sqrt(float(np.sum((radii * normal) ** 2)))
    return (radii * radii * normal) / denominator + SITE_ALT_KM * normal


def build_observer_spk() -> tuple[tempfile.TemporaryDirectory, Path]:
    """Build the temporary Type 9 SPK using the established stage-1 utility."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("lunasight_stage1_spk", SPK_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load SPK builder from {SPK_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    surface = module.unit_surface_point()
    start = float(spice.str2et("2026-11-02T14:12:00"))
    stop = float(spice.str2et("2026-11-02T14:17:00"))
    epochs = np.arange(start - 10.0, stop + 11.0, 1.0)
    states = np.vstack([module.site_relative_state(float(et), surface) for et in epochs])

    tmp = tempfile.TemporaryDirectory(prefix="lunasight_limbpt_")
    path = Path(tmp.name) / "lunasight_surface_observer.bsp"
    module.build_site_spk(path, epochs, states)
    spice.boddef(SITE_NAME, SITE_ID)
    spice.furnsh(str(path))
    return tmp, path


def verify_geometry(et: float) -> dict[str, float]:
    geodetic = independent_geodetic_point()
    existing = current_script_site_point()
    fixed_point_delta = float(np.linalg.norm(geodetic - existing))

    # sxform independently supplies both rotation and its time derivative;
    # unlike the original utility, this does not finite-difference pxform.
    fixed_state = np.concatenate((geodetic, np.zeros(3, dtype=float)))
    xform = np.asarray(spice.sxform(MOON_FRAME, INERTIAL_FRAME, et), dtype=float)
    expected_state = xform @ fixed_state
    actual_state, _ = spice.spkezr(
        SITE_NAME, et, INERTIAL_FRAME, "NONE", "MOON"
    )
    actual_state = np.asarray(actual_state, dtype=float)
    pos_error = float(np.linalg.norm(actual_state[:3] - expected_state[:3]))
    vel_error = float(np.linalg.norm(actual_state[3:] - expected_state[3:]))

    if fixed_point_delta > GEOMETRY_POSITION_TOL_KM:
        raise AssertionError(
            f"Independent geodetic mapping disagrees with existing site point by "
            f"{fixed_point_delta:.6e} km"
        )
    if pos_error > GEOMETRY_POSITION_TOL_KM:
        raise AssertionError(
            f"Observer position vs independent sxform state differs by {pos_error:.6e} km"
        )
    if vel_error > GEOMETRY_VELOCITY_TOL_KM_S:
        raise AssertionError(
            f"Observer velocity vs independent sxform state differs by {vel_error:.6e} km/s"
        )

    # Verify the SPK hierarchy reaches the solar-system barycenter consistently.
    site_ssb, _ = spice.spkezr(SITE_NAME, et, INERTIAL_FRAME, "NONE", "SOLAR SYSTEM BARYCENTER")
    moon_ssb, _ = spice.spkezr("MOON", et, INERTIAL_FRAME, "NONE", "SOLAR SYSTEM BARYCENTER")
    site_moon, _ = spice.spkezr(SITE_NAME, et, INERTIAL_FRAME, "NONE", "MOON")
    site_ssb = np.asarray(site_ssb, dtype=float)
    moon_ssb = np.asarray(moon_ssb, dtype=float)
    site_moon = np.asarray(site_moon, dtype=float)
    chain_pos_error = float(np.linalg.norm(site_ssb[:3] - (moon_ssb[:3] + site_moon[:3])))
    chain_vel_error = float(np.linalg.norm(site_ssb[3:] - (moon_ssb[3:] + site_moon[3:])))
    if chain_pos_error > CHAIN_POSITION_TOL_KM:
        raise AssertionError(f"SPK center chain position closure failed: {chain_pos_error:.6e} km")
    if chain_vel_error > CHAIN_VELOCITY_TOL_KM_S:
        raise AssertionError(f"SPK center chain velocity closure failed: {chain_vel_error:.6e} km/s")

    return {
        "independent_geodetic_point_delta_km": fixed_point_delta,
        "observer_position_error_km": pos_error,
        "observer_velocity_error_km_s": vel_error,
        "ssb_chain_position_closure_km": chain_pos_error,
        "ssb_chain_velocity_closure_km_s": chain_vel_error,
    }


def limb_point_elevations(
    et: float, correction: str, ncuts: int
) -> dict[str, float | int]:
    """Run NAIF limbpt and evaluate returned limb rays at observer reception time."""
    if ncuts < 36 or ncuts > 12000:
        raise ValueError("ncuts must be between 36 and 12000 for this diagnostic.")
    maxn = 4 * ncuts
    # Choose a reference vector guaranteed not to be parallel to the
    # observer-target center vector in the target-fixed frame.
    center_vec, _ = spice.spkpos(
        "EARTH", et, EARTH_FRAME, "NONE", SITE_NAME
    )
    center_vec = np.asarray(center_vec, dtype=float)
    helper = np.array([0.0, 0.0, 1.0], dtype=float)
    if abs(float(np.dot(center_vec / np.linalg.norm(center_vec), helper))) > 0.9:
        helper = np.array([0.0, 1.0, 0.0], dtype=float)
    refvec = np.cross(center_vec, helper)
    refnorm = float(np.linalg.norm(refvec))
    if not math.isfinite(refnorm) or refnorm <= 0.0:
        raise RuntimeError("Could not construct a non-degenerate limbpt reference vector.")
    refvec /= refnorm
    npts, points, epochs, tangents = spice.limbpt(
        "TANGENT/ELLIPSOID",
        "EARTH",
        et,
        EARTH_FRAME,
        correction,
        "ELLIPSOID LIMB",
        SITE_NAME,
        refvec,
        2.0 * math.pi / ncuts,
        ncuts,
        math.radians(1.0),
        1.0e-10,
        maxn,
    )
    del tangents  # The points and epochs are sufficient for this diagnostic.
    points = np.asarray(points, dtype=float)
    epochs = np.asarray(epochs, dtype=float)
    npts_array = np.asarray(npts, dtype=int).reshape(-1)
    count = int(np.sum(npts_array))
    if count <= 0:
        raise RuntimeError(f"limbpt returned no points for abcorr={correction}")
    if points.ndim != 2 or points.shape[1] != 3 or len(points) < count:
        raise RuntimeError(f"Unexpected limbpt points array shape: {points.shape}")
    if len(epochs) < count:
        raise RuntimeError(f"Unexpected limbpt epochs array length: {len(epochs)}")

    observer_state, _ = spice.spkezr(
        SITE_NAME, et, INERTIAL_FRAME, "NONE", "SOLAR SYSTEM BARYCENTER"
    )
    observer_state = np.asarray(observer_state, dtype=float)
    observer_pos = observer_state[:3]
    observer_vel = observer_state[3:]
    elevations: list[float] = []
    for i in range(count):
        limb_et = float(epochs[i])
        # limbpt points are target-fixed coordinates at their returned epochs.
        earth_center_state, _ = spice.spkezr(
            "EARTH", limb_et, INERTIAL_FRAME, "NONE", "SOLAR SYSTEM BARYCENTER"
        )
        earth_center_position = np.asarray(earth_center_state, dtype=float)[:3]
        rotation = np.asarray(spice.pxform(EARTH_FRAME, INERTIAL_FRAME, limb_et), dtype=float)
        point_ssb = earth_center_position + rotation @ points[i]
        ray = point_ssb - observer_pos
        if correction == "LT+S":
            ray = np.asarray(spice.stelab(ray, observer_vel), dtype=float)
        # Use the Moon's ellipsoid geodetic normal, transformed to J2000, as local up.
        moon_radii = np.asarray(spice.bodvrd("MOON", "RADII", 3)[1], dtype=float)
        site_fixed = independent_geodetic_point()
        normal_fixed = np.array(
            [site_fixed[0] / (moon_radii[0] ** 2),
             site_fixed[1] / (moon_radii[1] ** 2),
             site_fixed[2] / (moon_radii[2] ** 2)],
            dtype=float,
        )
        normal_fixed /= np.linalg.norm(normal_fixed)
        up = np.asarray(spice.pxform(MOON_FRAME, INERTIAL_FRAME, et), dtype=float) @ normal_fixed
        ray_norm = float(np.linalg.norm(ray))
        up_norm = float(np.linalg.norm(up))
        if ray_norm <= 0.0 or up_norm <= 0.0:
            raise RuntimeError("Invalid zero-length ray or local-up vector.")
        elevations.append(math.degrees(math.asin(float(np.clip(np.dot(ray / ray_norm, up / up_norm), -1.0, 1.0)))))

    return {
        "point_count": count,
        "max_limb_elevation_deg": max(elevations),
        "min_limb_elevation_deg": min(elevations),
        "mean_limb_elevation_deg": float(np.mean(elevations)),
        "epoch_span_seconds": float(np.max(epochs[:count]) - np.min(epochs[:count])),
    }


def independent_ellipsoid_limb_max(et: float) -> dict[str, float]:
    """Continuously optimize the instantaneous geometric ellipsoid limb.

    This reference does not call limbpt. It parameterizes the tangent circle
    after scaling the triaxial ellipsoid to a unit sphere, then independently
    maximizes the observer-to-limb-point elevation. It is an instantaneous
    NONE-geometry reference, not an LT/LT+S apparent-limb solution.
    """
    from scipy.optimize import minimize_scalar

    radii = np.asarray(spice.bodvrd("EARTH", "RADII", 3)[1], dtype=float)
    observer_state, _ = spice.spkezr(
        SITE_NAME, et, INERTIAL_FRAME, "NONE", "SOLAR SYSTEM BARYCENTER"
    )
    earth_state, _ = spice.spkezr(
        "EARTH", et, INERTIAL_FRAME, "NONE", "SOLAR SYSTEM BARYCENTER"
    )
    observer_ssb = np.asarray(observer_state, dtype=float)[:3]
    earth_ssb = np.asarray(earth_state, dtype=float)[:3]
    observer_fixed = np.asarray(
        spice.pxform(INERTIAL_FRAME, EARTH_FRAME, et), dtype=float
    ) @ (observer_ssb - earth_ssb)

    # For x = A*y on the unit sphere, the tangent condition is
    # dot(A^-1 o, y) = 1. Its intersection with |y|=1 is a circle.
    scaled_observer = observer_fixed / radii
    norm_sq = float(np.dot(scaled_observer, scaled_observer))
    if norm_sq <= 1.0:
        raise RuntimeError("Observer is not outside the Earth ellipsoid.")
    circle_center = scaled_observer / norm_sq
    circle_radius = math.sqrt(1.0 - 1.0 / norm_sq)
    axis = scaled_observer / math.sqrt(norm_sq)
    helper = np.array([0.0, 0.0, 1.0])
    if abs(float(np.dot(axis, helper))) > 0.9:
        helper = np.array([0.0, 1.0, 0.0])
    basis_u = np.cross(axis, helper)
    basis_u /= np.linalg.norm(basis_u)
    basis_v = np.cross(axis, basis_u)

    moon_radii = np.asarray(spice.bodvrd("MOON", "RADII", 3)[1], dtype=float)
    site_fixed = independent_geodetic_point()
    up_fixed = np.array(
        [site_fixed[0] / moon_radii[0] ** 2,
         site_fixed[1] / moon_radii[1] ** 2,
         site_fixed[2] / moon_radii[2] ** 2],
        dtype=float,
    )
    up_fixed /= np.linalg.norm(up_fixed)
    up_j2000 = np.asarray(spice.pxform(MOON_FRAME, INERTIAL_FRAME, et)) @ up_fixed

    def elevation(angle: float) -> float:
        unit_point = (
            circle_center
            + circle_radius
            * (basis_u * math.cos(angle) + basis_v * math.sin(angle))
        )
        limb_fixed = radii * unit_point
        limb_ssb = earth_ssb + np.asarray(
            spice.pxform(EARTH_FRAME, INERTIAL_FRAME, et)
        ) @ limb_fixed
        ray = limb_ssb - observer_ssb
        ray /= np.linalg.norm(ray)
        return math.asin(float(np.clip(np.dot(ray, up_j2000), -1.0, 1.0)))

    # Locate the global maximum on a dense periodic scan, then refine within
    # the neighboring grid interval. This avoids assuming unimodality globally.
    grid_count = 65536
    angles = np.linspace(0.0, 2.0 * math.pi, grid_count, endpoint=False)
    values = np.fromiter((elevation(float(a)) for a in angles), dtype=float)
    index = int(np.argmax(values))
    spacing = 2.0 * math.pi / grid_count
    center = float(angles[index])

    def wrapped_objective(delta: float) -> float:
        return -elevation((center + delta) % (2.0 * math.pi))

    optimum = minimize_scalar(
        wrapped_objective,
        bounds=(-spacing, spacing),
        method="bounded",
        options={"xatol": 1.0e-14},
    )
    maximum = -float(optimum.fun)
    return {
        "independent_geometric_limb_max_elevation_deg": math.degrees(maximum),
        "independent_optimizer_success": float(bool(optimum.success)),
        "independent_grid_samples": float(grid_count),
    }


def main() -> None:
    load_kernels()
    tmp = None
    try:
        tmp, _ = build_observer_spk()
        et = float(spice.str2et(TEST_UTC))
        geometry = verify_geometry(et)
        print("geometry_status=PASS")
        for key, value in geometry.items():
            print(f"{key}={value:.12g}")

        print(f"limbpt_test_utc={TEST_UTC}")
        independent = independent_ellipsoid_limb_max(et)
        print("independent_reference_model=INSTANTANEOUS_TRIAxIAL_ELLIPSOID_TANGENT_CIRCLE")
        for key, value in independent.items():
            print(f"{key}={value:.12g}")
        print("limbpt_method=TANGENT/ELLIPSOID")
        print("limbpt_corloc=ELLIPSOID LIMB")
        print("limbpt_event_time_status=NOT_EVALUATED")
        # A coarse 36-point ring is useful for smoke testing, but it is not
        # sufficient to estimate the maximum limb elevation reliably. Check
        # angular-sampling convergence at progressively finer resolutions.
        for correction in ("NONE", "LT", "LT+S"):
            previous = None
            for ncuts in (36, 180, 720, 2880, 5760):
                result = limb_point_elevations(et, correction, ncuts)
                print(f"limbpt_abcorr={correction}")
                print(f"limbpt_ncuts={ncuts}")
                for key, value in result.items():
                    print(f"{key}={value:.12g}" if isinstance(value, float) else f"{key}={value}")
                if previous is not None:
                    delta = abs(
                        float(result["max_limb_elevation_deg"])
                        - float(previous["max_limb_elevation_deg"])
                    )
                    print(f"max_elevation_change_from_previous_deg={delta:.12g}")
                if correction == "NONE":
                    delta_to_reference = abs(
                        float(result["max_limb_elevation_deg"])
                        - independent["independent_geometric_limb_max_elevation_deg"]
                    )
                    print(f"max_elevation_delta_vs_independent_reference_deg={delta_to_reference:.12g}")
                previous = result
        print("status=PASS")
    finally:
        if tmp is not None:
            tmp.cleanup()
        spice.kclear()


if __name__ == "__main__":
    main()
