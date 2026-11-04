"""Verify DE441 coverage and compare its event-epoch states with DE440s.

This utility validates kernel loading and ephemeris availability only. It does
not apply gravitational deflection or claim Horizons reproduction.
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import spiceypy as spice

import verify_limbpt_and_geometry as diag

TEST_UTC = "2026-11-02T14:14:00"
BODIES = ("SUN", "EARTH", "MOON")


def load_baseline() -> dict[str, np.ndarray]:
    spice.kclear()
    os.environ.pop("LUNASIGHT_PLANETARY_SPKS", None)
    diag.load_kernels()
    et = float(spice.str2et(TEST_UTC))
    states = {}
    for body in BODIES:
        state, _ = spice.spkezr(
            body, et, "J2000", "NONE", "SOLAR SYSTEM BARYCENTER"
        )
        states[body] = np.asarray(state, dtype=float)
    return states


def load_de441(paths: list[Path]) -> dict[str, np.ndarray]:
    spice.kclear()
    os.environ["LUNASIGHT_PLANETARY_SPKS"] = os.pathsep.join(map(str, paths))
    diag.load_kernels()
    et = float(spice.str2et(TEST_UTC))
    states = {}
    for body in BODIES:
        state, _ = spice.spkezr(
            body, et, "J2000", "NONE", "SOLAR SYSTEM BARYCENTER"
        )
        states[body] = np.asarray(state, dtype=float)
    # The selected Moon orientation kernels and site SPK must remain usable
    # alongside DE441, since ephemeris replacement must not break site geometry.
    temporary_spk, _ = diag.build_observer_spk()
    try:
        site, _ = spice.spkezr(
            diag.SITE_NAME, et, "J2000", "NONE", "SOLAR SYSTEM BARYCENTER"
        )
        states["LUNASIGHT_SURFACE_OBSERVER"] = np.asarray(site, dtype=float)
    finally:
        temporary_spk.cleanup()
    return states


def main() -> None:
    root = Path(__file__).resolve().parents[1] / "kernels"
    de441_paths = [
        root / "de441_part-1.bsp",
        root / "de441_part-2.bsp",
    ]
    missing = [str(path) for path in de441_paths if not path.is_file() or path.stat().st_size == 0]
    if missing:
        raise FileNotFoundError("Missing DE441 SPK parts: " + ", ".join(missing))

    baseline = load_baseline()
    de441 = load_de441(de441_paths)
    print("phase=DE441_EPHEMERIS_COVERAGE_AND_COMPARISON")
    print(f"test_epoch_utc={TEST_UTC}")
    print("de441_kernel_parts=2")
    print("de441_source=NAIF_GENERIC_KERNELS")
    for body in BODIES:
        position_delta = float(np.linalg.norm(de441[body][:3] - baseline[body][:3]))
        velocity_delta = float(np.linalg.norm(de441[body][3:] - baseline[body][3:]))
        print(f"{body.lower()}_de441_vs_de440s_position_delta_km={position_delta:.12g}")
        print(f"{body.lower()}_de441_vs_de440s_velocity_delta_km_s={velocity_delta:.12g}")
    if not np.all(np.isfinite(de441["LUNASIGHT_SURFACE_OBSERVER"])):
        raise AssertionError("Lunar surface observer state is not finite under DE441.")
    print("de441_sun_earth_moon_coverage=PASS")
    print("lunar_surface_observer_compatibility=PASS")
    print("solar_gravitational_deflection=NOT_COMPUTED")
    print("horizons_reproduction=NOT_COMPUTED")
    print("status=PASS")
    spice.kclear()


if __name__ == "__main__":
    main()
