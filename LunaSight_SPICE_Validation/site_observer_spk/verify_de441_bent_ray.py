"""Bind the fixed-endpoint bent-ray reference to DE441 states.

This stage uses one common reception/reference epoch and inertial J2000
coordinates for the Earth-center source, the lunar surface observer, and the
solar point-mass deflector. The Sun is the only deflector in this stage.
The model is static at the common epoch: body motion during photon flight,
retarded gravity, Earth gravity, limb tangency, and crossing-root updates are
intentionally excluded.
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
from scipy.integrate import quad
import spiceypy as spice

import verify_limbpt_and_geometry as diag
from finite_distance_bent_ray import finite_endpoint_bent_ray
from point_mass_light_deflection import ARCSEC_PER_RAD, C_KM_S, GM_SUN_KM3_S2

TEST_UTC = "2026-11-02T14:14:00"
FRAME = "J2000"
ABCORR = "NONE"
OBSERVER_CENTER = "SOLAR SYSTEM BARYCENTER"
EXPECTED_DE441_PARTS = ("de441_part-1.bsp", "de441_part-2.bsp")
QUADRATURE_EPSABS = 1.0e-22
QUADRATURE_EPSREL = 2.0e-13


def _state(body: str, et: float) -> np.ndarray:
    state, light_time = spice.spkezr(
        body, et, FRAME, ABCORR, OBSERVER_CENTER
    )
    vector = np.asarray(state, dtype=float)
    if vector.shape != (6,) or not np.all(np.isfinite(vector)):
        raise AssertionError(f"{body} DE441 state is not a finite 6-vector.")
    if not np.isfinite(light_time):
        raise AssertionError(f"{body} SPICE light-time output is not finite.")
    return vector


def _independent_endpoint_quadrature(
    source: np.ndarray,
    observer: np.ndarray,
    deflector: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, float, float]:
    """Independent scalar-component quadrature of the fixed-endpoint BVP."""
    segment = observer - source
    length = float(np.linalg.norm(segment))
    if not np.isfinite(length) or length <= 0.0:
        raise AssertionError("DE441 source-observer segment is degenerate.")
    direction = segment / length
    relative_source = source - deflector
    longitudinal_source = float(np.dot(relative_source, direction))
    impact_vector = relative_source - longitudinal_source * direction
    impact = float(np.linalg.norm(impact_vector))
    if not np.isfinite(impact) or impact <= 0.0:
        raise AssertionError("DE441 ray intersects the solar point-mass singularity.")

    coefficient = -2.0 * GM_SUN_KM3_S2 / (C_KM_S * C_KM_S)

    def force(u: float) -> np.ndarray:
        distance = length * u
        relative = relative_source + direction * distance
        radius = float(np.linalg.norm(relative))
        if radius <= 0.0:
            raise AssertionError("Quadrature encountered the solar singularity.")
        return coefficient * impact_vector / (radius ** 3)

    source_change = np.zeros(3, dtype=float)
    total_change = np.zeros(3, dtype=float)
    source_error = 0.0
    total_error = 0.0
    for axis in range(3):
        weighted_value, weighted_error = quad(
            lambda u: length * (1.0 - u) * force(u)[axis],
            0.0, 1.0, epsabs=QUADRATURE_EPSABS,
            epsrel=QUADRATURE_EPSREL, limit=300,
        )
        total_value, total_component_error = quad(
            lambda u: length * force(u)[axis],
            0.0, 1.0, epsabs=QUADRATURE_EPSABS,
            epsrel=QUADRATURE_EPSREL, limit=300,
        )
        source_change[axis] = -weighted_value
        total_change[axis] = total_value
        source_error += weighted_error
        total_error += total_component_error
    observer_change = source_change + total_change
    return source_change, observer_change, source_error, total_error


def main() -> None:
    configured = os.environ.get("LUNASIGHT_PLANETARY_SPKS", "").strip()
    selected = tuple(Path(item).name for item in configured.split(os.pathsep) if item)
    if selected != EXPECTED_DE441_PARTS:
        raise AssertionError(
            "This validation must use exactly the official DE441 pair in order; "
            f"selected={selected!r}"
        )

    spice.kclear()
    diag.load_kernels()
    et = float(spice.str2et(TEST_UTC))
    source_state = _state("EARTH", et)
    deflector_state = _state("SUN", et)

    temporary_spk, _ = diag.build_observer_spk()
    try:
        observer_state = _state(diag.SITE_NAME, et)
    finally:
        temporary_spk.cleanup()

    source = source_state[:3]
    observer = observer_state[:3]
    sun = deflector_state[:3]
    if not all(np.all(np.isfinite(item)) for item in (source, observer, sun)):
        raise AssertionError("One or more DE441 position vectors are non-finite.")

    production = finite_endpoint_bent_ray(source, observer, sun)
    reference_source, reference_observer, source_error, observer_error = (
        _independent_endpoint_quadrature(source, observer, sun)
    )
    actual_source = np.asarray(production["source_direction_change"], dtype=float)
    actual_observer = np.asarray(production["observer_direction_change"], dtype=float)

    source_residual = float(np.linalg.norm(actual_source - reference_source))
    observer_residual = float(np.linalg.norm(actual_observer - reference_observer))
    source_tolerance = max(2.0e-18, 16.0 * source_error)
    observer_tolerance = max(2.0e-18, 16.0 * observer_error)
    if source_residual > source_tolerance:
        raise AssertionError(
            "DE441 source endpoint differs from independent scalar quadrature: "
            f"{source_residual:.6e} > {source_tolerance:.6e} rad"
        )
    if observer_residual > observer_tolerance:
        raise AssertionError(
            "DE441 observer endpoint differs from independent scalar quadrature: "
            f"{observer_residual:.6e} > {observer_tolerance:.6e} rad"
        )

    # The direction convention must remain source-to-observer at the source,
    # and observer-to-source must be the negation of propagation at reception.
    source_direction = np.asarray(
        production["source_to_observer_direction_at_source"], dtype=float
    )
    observer_propagation = np.asarray(
        production["source_to_observer_direction_at_observer"], dtype=float
    )
    observer_apparent = np.asarray(
        production["observer_to_source_direction_at_observer"], dtype=float
    )
    if not np.isclose(np.linalg.norm(source_direction), 1.0, rtol=0.0, atol=2e-13):
        raise AssertionError("Source endpoint direction is not unit length.")
    if not np.isclose(np.linalg.norm(observer_propagation), 1.0, rtol=0.0, atol=2e-13):
        raise AssertionError("Observer endpoint propagation direction is not unit length.")
    if not np.allclose(observer_apparent, -observer_propagation, rtol=0.0, atol=2e-14):
        raise AssertionError("Observer-to-source direction sign convention is invalid.")

    print("phase=DE441_FIXED_ENDPOINT_BENT_RAY_BINDING")
    print(f"reference_epoch_utc={TEST_UTC}")
    print(f"spice_et_seconds_past_j2000_tdb={et:.9f}")
    print(f"ephemeris={';'.join(selected)}")
    print(f"reference_frame={FRAME}")
    print(f"aberration_correction={ABCORR}")
    print(f"state_center={OBSERVER_CENTER}")
    print("position_units=km")
    print("velocity_units=km/s")
    print("source_body=EARTH_CENTER")
    print(f"source_position_j2000_km={','.join(f'{v:.12g}' for v in source)}")
    print(f"source_velocity_j2000_km_s={','.join(f'{v:.12g}' for v in source_state[3:])}")
    print(f"observer_body={diag.SITE_NAME}")
    print(f"observer_position_j2000_km={','.join(f'{v:.12g}' for v in observer)}")
    print(f"observer_velocity_j2000_km_s={','.join(f'{v:.12g}' for v in observer_state[3:])}")
    print("deflector_body=SUN")
    print(f"deflector_position_j2000_km={','.join(f'{v:.12g}' for v in sun)}")
    print(f"deflector_velocity_j2000_km_s={','.join(f'{v:.12g}' for v in deflector_state[3:])}")
    print("state_epoch_policy=ALL_POSITIONS_AT_ONE_COMMON_EPOCH")
    print("deflector_motion_during_flight=NOT_MODELED")
    print(f"segment_length_km={production['segment_length_km']:.12g}")
    print(f"solar_impact_parameter_km={production['impact_parameter_km']:.12g}")
    print(f"source_endpoint_direction_change_arcsec={production['source_direction_change_arcsec']:.12g}")
    print(f"observer_endpoint_direction_change_arcsec={production['observer_direction_change_arcsec']:.12g}")
    print(f"independent_source_reference_error_rad={source_error:.6e}")
    print(f"independent_observer_reference_error_rad={observer_error:.6e}")
    print(f"source_endpoint_residual_rad={source_residual:.6e}")
    print(f"observer_endpoint_residual_rad={observer_residual:.6e}")
    print(f"transverse_displacement_closure_km={production['transverse_displacement_closure_km']:.6e}")
    print("coordinate_frame_and_units=PASS")
    print("endpoint_direction_conventions=PASS")
    print("independent_scalar_quadrature=PASS")
    print("solar_deflector_only=PASS")
    print("earth_gravity=NOT_MODELED")
    print("limb_tangency_application=NOT_RUN")
    print("crossing_roots_modified=NO")
    print("status=PASS")
    spice.kclear()


if __name__ == "__main__":
    main()
