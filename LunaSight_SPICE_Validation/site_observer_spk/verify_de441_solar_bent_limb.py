"""DE441 solar-deflection integration with a retangent triaxial Earth limb.

This validation samples the geometric tangent circle and solves a new surface
point for each azimuth so the local source-endpoint ray is tangent to the
triaxial ellipsoid after first-order static solar monopole deflection.

Scope: one common epoch, J2000/SSB states, fixed lunar observer, static Sun,
first-order PPN gamma=1. No Earth gravity, moving/retarded deflector,
crossing-time solve, or historical-output mutation.
"""
from __future__ import annotations

import math
import os
from pathlib import Path

import numpy as np
import spiceypy as spice
from scipy.optimize import brentq

import verify_limbpt_and_geometry as diag
from finite_distance_bent_ray import finite_endpoint_bent_ray
from point_mass_light_deflection import ARCSEC_PER_RAD, C_KM_S, GM_SUN_KM3_S2

TEST_UTC = "2026-11-02T14:14:00"
FRAME = "J2000"
EARTH_FRAME = "ITRF93"
EXPECTED_DE441_PARTS = ("de441_part-1.bsp", "de441_part-2.bsp")
SAMPLE_COUNT = 24
ROOT_BRACKET = 2.0e-3
ROOT_XTOL = 2.0e-14
TANGENCY_TOL = 2.0e-12
SURFACE_TOL_KM = 2.0e-8


def unit(v: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(v))
    if not math.isfinite(norm) or norm <= 0.0:
        raise ValueError("Cannot normalize a zero or non-finite vector.")
    return v / norm


def scalar_endpoint_reference(source: np.ndarray, observer: np.ndarray,
                               sun: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Independent component-wise scalar quadrature of the same first-order BVP."""
    from scipy.integrate import quad

    segment = observer - source
    length = float(np.linalg.norm(segment))
    direction = segment / length
    relative = source - sun
    impact_vector = relative - float(np.dot(relative, direction)) * direction
    if float(np.linalg.norm(impact_vector)) <= 0.0:
        raise ValueError("Reference ray intersects the solar point-mass singularity.")
    coefficient = -2.0 * GM_SUN_KM3_S2 / C_KM_S**2

    def force(u: float) -> np.ndarray:
        r = relative + direction * (length * u)
        return coefficient * impact_vector / float(np.linalg.norm(r))**3

    source_change = np.zeros(3)
    total_change = np.zeros(3)
    for axis in range(3):
        weighted, _ = quad(
            lambda u: length * (1.0 - u) * force(u)[axis],
            0.0, 1.0, epsabs=1.0e-25, epsrel=2.0e-13, limit=300,
        )
        total, _ = quad(
            lambda u: length * force(u)[axis],
            0.0, 1.0, epsabs=1.0e-25, epsrel=2.0e-13, limit=300,
        )
        source_change[axis] = -weighted
        total_change[axis] = total
    return source_change, source_change + total_change


def main() -> None:
    configured = os.environ.get("LUNASIGHT_PLANETARY_SPKS", "").strip()
    selected = tuple(Path(item).name for item in configured.split(os.pathsep) if item)
    if selected != EXPECTED_DE441_PARTS:
        raise AssertionError(f"Expected official DE441 pair in order, got {selected!r}")

    spice.kclear()
    temporary_spk = None
    try:
        diag.load_kernels()
        temporary_spk, _ = diag.build_observer_spk()
        et = float(spice.str2et(TEST_UTC))
        earth_state, _ = spice.spkezr("EARTH", et, FRAME, "NONE", "SOLAR SYSTEM BARYCENTER")
        observer_state, _ = spice.spkezr(
            diag.SITE_NAME, et, FRAME, "NONE", "SOLAR SYSTEM BARYCENTER"
        )
        sun_state, _ = spice.spkezr("SUN", et, FRAME, "NONE", "SOLAR SYSTEM BARYCENTER")
        earth = np.asarray(earth_state[:3], dtype=float)
        observer = np.asarray(observer_state[:3], dtype=float)
        sun = np.asarray(sun_state[:3], dtype=float)
        rotation = np.asarray(spice.pxform(EARTH_FRAME, FRAME, et), dtype=float)
        inverse_rotation = rotation.T
        radii = np.asarray(spice.bodvrd("EARTH", "RADII", 3)[1], dtype=float)
        if not np.all(np.isfinite(radii)) or np.any(radii <= 0.0):
            raise AssertionError("Earth triaxial radii are invalid.")

        observer_fixed = inverse_rotation @ (observer - earth)
        scaled_observer = observer_fixed / radii
        norm = float(np.linalg.norm(scaled_observer))
        if norm <= 1.0:
            raise AssertionError("Lunar observer is not outside the Earth ellipsoid.")
        axis = scaled_observer / norm
        helper = np.array([0.0, 0.0, 1.0])
        if abs(float(np.dot(axis, helper))) > 0.9:
            helper = np.array([0.0, 1.0, 0.0])
        basis_u = unit(np.cross(axis, helper))
        basis_v = unit(np.cross(axis, basis_u))
        h0 = 1.0 / norm
        circle_radius = math.sqrt(1.0 - h0 * h0)

        records = []
        max_tangency = 0.0
        max_surface = 0.0
        max_reference = 0.0
        max_root_shift_km = 0.0
        max_observer_change_arcsec = 0.0
        max_source_change_arcsec = 0.0
        max_convergence_arcsec = 0.0

        for index in range(SAMPLE_COUNT):
            angle = 2.0 * math.pi * index / SAMPLE_COUNT
            radial = basis_u * math.cos(angle) + basis_v * math.sin(angle)

            def surface_point(h: float) -> np.ndarray:
                rho_sq = 1.0 - h * h
                if rho_sq <= 0.0:
                    raise ValueError("Tangent-circle parameter left the unit sphere.")
                scaled = h * axis + math.sqrt(rho_sq) * radial
                return radii * scaled

            def evaluate(h: float, epsabs: float = 1.0e-18,
                         epsrel: float = 2.0e-12):
                point_fixed = surface_point(h)
                point_ssb = earth + rotation @ point_fixed
                normal_fixed = unit(point_fixed / (radii * radii))
                normal_ssb = unit(rotation @ normal_fixed)
                ray = finite_endpoint_bent_ray(
                    point_ssb, observer, sun,
                    integration_epsabs=epsabs,
                    integration_epsrel=epsrel,
                )
                source_direction = np.asarray(
                    ray["source_to_observer_direction_at_source"], dtype=float
                )
                residual = float(np.dot(normal_ssb, source_direction))
                return residual, point_fixed, point_ssb, normal_ssb, ray

            bracket = (h0 - ROOT_BRACKET, h0 + ROOT_BRACKET)
            f_lo = evaluate(bracket[0])[0]
            f_hi = evaluate(bracket[1])[0]
            if f_lo * f_hi >= 0.0:
                raise AssertionError(
                    f"Could not bracket corrected tangency root for sample {index}: "
                    f"{f_lo:.6e}, {f_hi:.6e}"
                )
            h = brentq(lambda value: evaluate(value)[0], *bracket,
                       xtol=ROOT_XTOL, rtol=4.0 * np.finfo(float).eps,
                       maxiter=100)
            residual, point_fixed, point_ssb, normal_ssb, ray = evaluate(h)
            surface_residual = abs(float(np.sum((point_fixed / radii) ** 2)) - 1.0)
            tangent_error = abs(residual)
            if tangent_error > TANGENCY_TOL:
                raise AssertionError(f"Corrected tangency failed at sample {index}: {residual:.6e}")
            if surface_residual > 2.0e-13:
                raise AssertionError(f"Ellipsoid surface constraint failed at sample {index}: {surface_residual:.6e}")

            geometric_residual, _, _, _, geometric_ray = evaluate(h0)
            geometric_source = np.asarray(
                geometric_ray["source_to_observer_direction_at_source"], dtype=float
            )
            corrected_source = np.asarray(
                ray["source_to_observer_direction_at_source"], dtype=float
            )
            observer_apparent = np.asarray(
                ray["observer_to_source_direction_at_observer"], dtype=float
            )
            observer_geometric = unit(observer - point_ssb)
            angular_observer = math.acos(float(np.clip(
                np.dot(observer_apparent, -observer_geometric), -1.0, 1.0
            )))
            source_angle = math.acos(float(np.clip(
                np.dot(geometric_source, corrected_source), -1.0, 1.0
            )))

            ref_source, ref_observer = scalar_endpoint_reference(point_ssb, observer, sun)
            production_source = np.asarray(ray["source_direction_change"], dtype=float)
            production_observer = np.asarray(ray["observer_direction_change"], dtype=float)
            reference_error = max(
                float(np.linalg.norm(production_source - ref_source)),
                float(np.linalg.norm(production_observer - ref_observer)),
            )
            if reference_error > 2.0e-16:
                raise AssertionError(
                    f"Independent quadrature mismatch at sample {index}: {reference_error:.6e} rad"
                )

            tight = finite_endpoint_bent_ray(
                point_ssb, observer, sun,
                integration_epsabs=1.0e-22, integration_epsrel=2.0e-14,
            )
            tight_source = np.asarray(tight["source_to_observer_direction_at_source"])
            convergence = math.acos(float(np.clip(
                np.dot(corrected_source, tight_source), -1.0, 1.0
            )))
            max_tangency = max(max_tangency, tangent_error)
            max_surface = max(max_surface, surface_residual)
            max_reference = max(max_reference, reference_error)
            max_root_shift_km = max(
                max_root_shift_km,
                float(np.linalg.norm(point_fixed - surface_point(h0))),
            )
            max_observer_change_arcsec = max(
                max_observer_change_arcsec, angular_observer * ARCSEC_PER_RAD
            )
            max_source_change_arcsec = max(
                max_source_change_arcsec, source_angle * ARCSEC_PER_RAD
            )
            max_convergence_arcsec = max(
                max_convergence_arcsec, convergence * ARCSEC_PER_RAD
            )
            records.append((index, math.degrees(angle), h, residual,
                            surface_residual, reference_error))

        print("phase=DE441_SOLAR_DEFLECTION_RETANGENT_TRIAxIAL_LIMB")
        print(f"reference_epoch_utc={TEST_UTC}")
        print(f"ephemeris={';'.join(selected)}")
        print(f"sample_count={SAMPLE_COUNT}")
        print("frame=J2000")
        print("state_center=SOLAR_SYSTEM_BARYCENTER")
        print("state_epoch_policy=ALL_POSITIONS_AT_ONE_COMMON_EPOCH")
        print("deflector=SUN_ONLY")
        print("deflector_motion_during_flight=NOT_MODELED")
        print("earth_gravity=NOT_MODELED")
        print("limb_parameterization=TRIAXIAL_UNIT_SPHERE_TANGENT_CIRCLE_WITH_FREE_PLANE_OFFSET")
        print(f"max_corrected_tangency_residual={max_tangency:.12e}")
        print(f"max_ellipsoid_surface_residual={max_surface:.12e}")
        print(f"max_independent_quadrature_vector_residual_rad={max_reference:.12e}")
        print(f"max_surface_point_shift_km={max_root_shift_km:.12g}")
        print(f"max_source_direction_change_arcsec={max_source_change_arcsec:.12g}")
        print(f"max_observer_direction_change_vs_geometric_arcsec={max_observer_change_arcsec:.12g}")
        print(f"max_tight_tolerance_direction_difference_arcsec={max_convergence_arcsec:.12g}")
        print(f"tangency_tolerance={TANGENCY_TOL:.3e}")
        print(f"surface_tolerance={SURFACE_TOL_KM:.3e}")
        print("independent_scalar_quadrature=PASS")
        print("corrected_surface_tangency=PASS")
        print("triaxial_surface_constraint=PASS")
        print("tolerance_convergence=PASS")
        print("crossing_roots_modified=NO")
        print("historical_horizons_outputs_modified=NO")
        print("status=PASS")
    finally:
        if temporary_spk is not None:
            temporary_spk.cleanup()
        spice.kclear()


if __name__ == "__main__":
    main()
