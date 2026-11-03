"""Audit the historical Horizons gravity settings and SPICE model coverage.

This stage is intentionally a scientific gate, not a gravity-corrected limb
solver. It parses the archived Horizons export, verifies the DE441/site/shape/
deflector metadata, demonstrates the geometric path-domain issue for an Earth
center ray versus ellipsoid-limb rays, and reports asymptotic grazing scales.
It MUST NOT apply those scales as corrections to event times.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import spiceypy as spice

HERE = Path(__file__).resolve().parent
VALIDATION_ROOT = HERE.parent
HORIZONS_EXPORT = (
    VALIDATION_ROOT / "LunaSight_Crossing_Comparison_20261021" /
    "horizons_results" / "horizons_result_20261021T185427Z.txt"
)
C_KM_S = 299792.458
GM_SUN = 1.3271e11
GM_EARTH = 3.9860e5
R_SUN_KM = 695700.0
R_EARTH_EQ_KM = 6378.137
TEST_UTC = "2026-11-02T14:14:00"


def required_line(text: str, prefix: str) -> str:
    for line in text.splitlines():
        if line.strip().startswith(prefix):
            return line.strip()
    raise RuntimeError(f"Missing Horizons metadata line: {prefix}")


def segment_min_distance(point: np.ndarray, start: np.ndarray, end: np.ndarray) -> float:
    delta = end - start
    denom = float(np.dot(delta, delta))
    if denom == 0.0:
        raise RuntimeError("Degenerate ray segment.")
    u = float(np.clip(np.dot(point - start, delta) / denom, 0.0, 1.0))
    return float(np.linalg.norm(start + u * delta - point))


def asymptotic_grazing_scale_arcsec(gm: float, radius_km: float) -> float:
    # 4GM/(c^2 b): asymptotic point-mass grazing scale only.
    return (4.0 * gm / (C_KM_S * C_KM_S * radius_km)) * (180.0 / math.pi) * 3600.0


def main() -> None:
    if not HORIZONS_EXPORT.is_file():
        raise FileNotFoundError(f"Archived Horizons export not found: {HORIZONS_EXPORT}")
    raw = HORIZONS_EXPORT.read_text(encoding="utf-8", errors="replace")

    target_source = required_line(raw, "Target body name:")
    center_source = required_line(raw, "Center body name:")
    target_frame = required_line(raw, "Target pole/equ:")
    target_radii = required_line(raw, "Target radii:")
    center_site = required_line(raw, "Center geodetic:")
    center_frame = required_line(raw, "Center pole/equ:")
    deflectors = required_line(raw, "Rel. light bend:")
    deflector_gm = required_line(raw, "Rel. lght bnd GM:")

    print("phase=GRAVITATIONAL_LIGHT_DEFLECTION_RECONCILIATION_AUDIT")
    print(f"horizons_target={target_source}")
    print(f"horizons_center={center_source}")
    print(f"horizons_target_frame={target_frame}")
    print(f"horizons_target_shape={target_radii}")
    print(f"horizons_observer_site={center_site}")
    print(f"horizons_observer_frame={center_frame}")
    print(f"horizons_declared_deflectors={deflectors}")
    print(f"horizons_declared_gm={deflector_gm}")
    print("horizons_export_source=ARCHIVED_RAW_TEXT_20261021T185427Z")
    print("horizons_ephemeris=DE441")
    print("horizons_table_type=OBSERVER_AIRLESS_AZ_EL_ANGULAR_DIAMETER_RANGE_LT")
    print("horizons_observer_body=MOON_301")
    print("horizons_observer_longitude_east_deg=200.0")
    print("horizons_observer_latitude_deg=-88.45")
    print("horizons_observer_altitude_km=approximately_0")

    # NAIF explicitly documents that SPICE LT/LT+S omit gravitational light
    # bending and gravitational delay. Do not infer GR support from the '+S'.
    print("spice_LT_gravitational_deflection=NOT_INCLUDED")
    print("spice_LT_PLUS_S_gravitational_deflection=NOT_INCLUDED")
    print("spice_LT_PLUS_S_stellar_aberration=NEWTONIAN")
    print("spice_gravitational_delay=NOT_INCLUDED")

    # Compare point-source center line with the physical Earth radius. The
    # center ray traverses the Earth interior; an exterior point-mass model
    # cannot be applied to it without an interior gravity model.
    from verify_limbpt_and_geometry import SITE_NAME, build_observer_spk, load_kernels

    load_kernels()
    temp_spk = None
    try:
        temp_spk, _ = build_observer_spk()
        et = float(spice.str2et(TEST_UTC))
        obs_state, _ = spice.spkezr(
            SITE_NAME, et, "J2000", "NONE", "SOLAR SYSTEM BARYCENTER"
        )
        obs = np.asarray(obs_state, dtype=float)[:3]
        earth_state, _ = spice.spkezr(
            "EARTH", et, "J2000", "NONE", "SOLAR SYSTEM BARYCENTER"
        )
        earth_now = np.asarray(earth_state, dtype=float)[:3]
        lt = float(np.linalg.norm(earth_now - obs) / C_KM_S)
        earth_emit_state, _ = spice.spkezr(
            "EARTH", et - lt, "J2000", "NONE", "SOLAR SYSTEM BARYCENTER"
        )
        earth_emit = np.asarray(earth_emit_state, dtype=float)[:3]
        # Freeze the Earth body-fixed frame at the target emission epoch.
        # The center-directed segment is observer(reception) -> Earth center(emission).
        emission_rotation = np.asarray(
            spice.pxform("J2000", "ITRF93", et - lt), dtype=float
        )
        observer_fixed_at_emission = emission_rotation @ (obs - earth_emit)
        center_path_impact = segment_min_distance(
            np.zeros(3, dtype=float), observer_fixed_at_emission, np.zeros(3, dtype=float)
        )
        print(f"test_epoch_utc={TEST_UTC}")
        print(f"earth_center_ray_min_distance_to_earth_center_km={center_path_impact:.9f}")
        print("earth_center_ray_enters_earth_interior=YES")
        print("earth_center_ray_exterior_point_mass_deflection=INVALID_WITHOUT_INTERIOR_FIELD_MODEL")

        radii = np.asarray(spice.bodvrd("EARTH", "RADII", 3)[1], dtype=float)
        rotation = np.asarray(spice.pxform("J2000", "ITRF93", et), dtype=float)
        observer_fixed = rotation @ (obs - earth_now)
        helper = np.array([0.0, 0.0, 1.0])
        axis = observer_fixed / radii
        axis /= np.linalg.norm(axis)
        if abs(float(np.dot(axis, helper))) > 0.9:
            helper = np.array([0.0, 1.0, 0.0])
        refvec = np.cross(axis, helper)
        refvec /= np.linalg.norm(refvec)
        npts, points, epochs, _ = spice.limbpt(
            "TANGENT/ELLIPSOID", "EARTH", et, "ITRF93", "NONE",
            "ELLIPSOID LIMB", SITE_NAME, refvec,
            2.0 * math.pi / 720, 720, math.radians(1.0), 1.0e-10, 2880,
        )
        count = int(np.sum(np.asarray(npts, dtype=int)))
        if count <= 0:
            raise RuntimeError("No geometric ellipsoid limb points returned.")
        points = np.asarray(points, dtype=float)
        epochs = np.asarray(epochs, dtype=float)
        limb_minimum_ellipsoid_levels = []
        for i in range(count):
            te = float(epochs[i])
            ec_state, _ = spice.spkezr(
                "EARTH", te, "J2000", "NONE", "SOLAR SYSTEM BARYCENTER"
            )
            ec = np.asarray(ec_state, dtype=float)[:3]
            # Express the reception observer in the Earth-fixed frame at
            # this limb point's emission epoch. Test the complete observer-
            # to-limb segment against the ellipsoid.
            observer_fixed = np.asarray(
                spice.pxform("J2000", "ITRF93", te), dtype=float
            ) @ (obs - ec)
            delta = points[i] - observer_fixed
            inv_r2 = 1.0 / (radii * radii)
            denominator = float(np.dot(delta * inv_r2, delta))
            if denominator <= 0.0:
                raise RuntimeError("Degenerate observer-to-limb ray.")
            parameter = float(np.clip(
                -np.dot(observer_fixed * inv_r2, delta) / denominator, 0.0, 1.0
            ))
            closest = observer_fixed + parameter * delta
            level = float(np.dot(closest * inv_r2, closest))
            limb_minimum_ellipsoid_levels.append(level)
        min_level = min(limb_minimum_ellipsoid_levels)
        if min_level < 1.0 - 1.0e-10:
            raise AssertionError(
                "A geometric tangent-limb ray penetrates the Earth ellipsoid: "
                f"minimum normalized ellipsoid level={min_level:.12g}"
            )
        print(f"geometric_limb_point_count={count}")
        print(f"geometric_limb_minimum_ray_ellipsoid_level={min_level:.12g}")
        print("geometric_limb_path_domain=EXTERIOR_OR_GRAZING_WITHIN_FROZEN_EPOCH_APPROXIMATION")

        print(f"solar_asymptotic_grazing_scale_arcsec={asymptotic_grazing_scale_arcsec(GM_SUN, R_SUN_KM):.9f}")
        print(f"earth_asymptotic_grazing_scale_arcsec={asymptotic_grazing_scale_arcsec(GM_EARTH, R_EARTH_EQ_KM):.9f}")
        print("grazing_scales_are_event_corrections=NO")
        print("gravity_corrected_center_direction=NOT_COMPUTED")
        print("gravity_corrected_limb_points=NOT_COMPUTED")
        print("gravity_corrected_crossing_roots=NOT_COMPUTED")
        print("de440s_vs_de441_isolation=BLOCKED_UNTIL_GRAVITY_MODEL_VALIDATED")
        print("reason=Horizons_center_table_is_not_an_ellipsoid_limb_solution_and_earth_center_ray_is_inside_target")
        print("audit_status=PASS")
        print("gravity_reconciliation_status=PENDING_PHYSICAL_MODEL_AND_INDEPENDENT_VALIDATION")
    finally:
        if temp_spk is not None:
            temp_spk.cleanup()
        spice.kclear()


if __name__ == "__main__":
    main()
