"""Build and verify an independent SPICE SPK observer for a lunar surface site.

This is deliberately a stage-1 validation utility. It does not calculate Earth's
limb and does not alter any historical comparison outputs.
"""
from __future__ import annotations

import math
import tempfile
from pathlib import Path

import numpy as np
import spiceypy as spice

ROOT = Path(__file__).resolve().parent
KERNEL_DIR = ROOT.parent / "kernels"
SITE_NAME = "LUNASIGHT_SURFACE_OBSERVER"
SITE_ID = -999001
MOON_ID = 301
MOON_FRAME = "MOON_ME"
INERTIAL_FRAME = "J2000"
SITE_LON_DEG = 200.0
SITE_LAT_DEG = -88.45
SITE_ALT_KM = 0.0
START_UTC = "2026-11-02T14:12:20"
STOP_UTC = "2026-11-02T14:16:10"
SAMPLE_SECONDS = 1.0
SPK_DEGREE = 7
POSITION_TOLERANCE_KM = 2.0e-7
VELOCITY_TOLERANCE_KM_S = 2.0e-8

KERNEL_FILES = (
    "naif0012.tls",
    "pck00011.tpc",
    "de440s.bsp",
    "moon_pa_de440_200625.bpc",
    "moon_de440_220930.tf",
)


def require_kernels() -> None:
    missing = [name for name in KERNEL_FILES if not (KERNEL_DIR / name).is_file()]
    if missing:
        raise FileNotFoundError(
            "Missing required kernels in " + str(KERNEL_DIR) + ": " + ", ".join(missing)
        )
    for name in KERNEL_FILES:
        path = KERNEL_DIR / name
        if path.stat().st_size == 0:
            raise RuntimeError(f"Kernel is empty: {path}")
        spice.furnsh(str(path))


def unit_surface_point() -> np.ndarray:
    radii = np.asarray(spice.bodvrd("MOON", "RADII", 3)[1], dtype=float)
    lon = math.radians(SITE_LON_DEG)
    lat = math.radians(SITE_LAT_DEG)
    # Geodetic surface normal; Moon PCK radii are expected to be spherical here,
    # but the ellipsoid formula remains valid if the radii differ.
    normal = np.array(
        [math.cos(lat) * math.cos(lon), math.cos(lat) * math.sin(lon), math.sin(lat)],
        dtype=float,
    )
    normal /= np.linalg.norm(normal)
    denominator = math.sqrt(float(np.sum((radii * normal) ** 2)))
    surface = (radii * radii * normal) / denominator
    return surface + SITE_ALT_KM * normal


def site_relative_state(et: float, surface_fixed: np.ndarray) -> np.ndarray:
    rotation = np.asarray(spice.pxform(MOON_FRAME, INERTIAL_FRAME, et), dtype=float)
    position = rotation @ surface_fixed
    # Centered finite difference of the rotated site vector. The interval is
    # short compared with the lunar rotation period and avoids frame-rate
    # omissions in a hand-built velocity.
    dt = 0.25
    r_before = np.asarray(
        spice.pxform(MOON_FRAME, INERTIAL_FRAME, et - dt), dtype=float
    ) @ surface_fixed
    r_after = np.asarray(
        spice.pxform(MOON_FRAME, INERTIAL_FRAME, et + dt), dtype=float
    ) @ surface_fixed
    velocity = (r_after - r_before) / (2.0 * dt)
    return np.concatenate((position, velocity))


def build_site_spk(path: Path, epochs: np.ndarray, states: np.ndarray) -> None:
    handle = spice.spkopn(str(path), "LunaSight independent lunar surface observer", 0)
    try:
        spice.spkw09(
            handle,
            SITE_ID,
            MOON_ID,
            INERTIAL_FRAME,
            float(epochs[0]),
            float(epochs[-1]),
            "LUNASIGHT SURFACE SITE TYPE 9",
            SPK_DEGREE,
            states,
            epochs,
        )
    finally:
        spice.spkcls(handle)


def verify() -> dict[str, float | int | str]:
    require_kernels()
    spice.boddef(SITE_NAME, SITE_ID)
    surface_fixed = unit_surface_point()
    start = float(spice.str2et(START_UTC))
    stop = float(spice.str2et(STOP_UTC))
    # Pad both ends so centered finite differences and interpolation are valid.
    epochs = np.arange(start - 10.0, stop + 10.0 + SAMPLE_SECONDS, SAMPLE_SECONDS)
    states = np.vstack([site_relative_state(float(et), surface_fixed) for et in epochs])

    with tempfile.TemporaryDirectory(prefix="lunasight_site_spk_") as tmp:
        spk_path = Path(tmp) / "lunasight_surface_observer.bsp"
        build_site_spk(spk_path, epochs, states)
        spice.furnsh(str(spk_path))
        try:
            check_epochs = np.linspace(start, stop, 31)
            position_errors: list[float] = []
            velocity_errors: list[float] = []
            for et in check_epochs:
                expected = site_relative_state(float(et), surface_fixed)
                actual_state, _ = spice.spkezr(
                    SITE_NAME, float(et), INERTIAL_FRAME, "NONE", "MOON"
                )
                actual = np.asarray(actual_state, dtype=float)
                position_errors.append(float(np.linalg.norm(actual[:3] - expected[:3])))
                velocity_errors.append(float(np.linalg.norm(actual[3:] - expected[3:])))
            max_position = max(position_errors)
            max_velocity = max(velocity_errors)
            if max_position > POSITION_TOLERANCE_KM:
                raise AssertionError(
                    f"SPK site position error {max_position:.3e} km exceeds "
                    f"{POSITION_TOLERANCE_KM:.3e} km"
                )
            if max_velocity > VELOCITY_TOLERANCE_KM_S:
                raise AssertionError(
                    f"SPK site velocity error {max_velocity:.3e} km/s exceeds "
                    f"{VELOCITY_TOLERANCE_KM_S:.3e} km/s"
                )
            return {
                "observer_name": SITE_NAME,
                "observer_id": SITE_ID,
                "center_body_id": MOON_ID,
                "sample_count": int(len(epochs)),
                "check_count": int(len(check_epochs)),
                "max_position_error_km": max_position,
                "max_velocity_error_km_s": max_velocity,
                "status": "PASS",
            }
        finally:
            spice.unload(str(spk_path))


def main() -> None:
    try:
        result = verify()
        for key, value in result.items():
            print(f"{key}={value}")
    finally:
        spice.kclear()


if __name__ == "__main__":
    main()
