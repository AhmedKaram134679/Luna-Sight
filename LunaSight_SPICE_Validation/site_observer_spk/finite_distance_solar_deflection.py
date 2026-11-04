"""Finite-distance solar monopole light-deflection reference model.

The model integrates the first-order PPN (gamma=1) transverse change of a
photon direction along the unperturbed finite straight segment from source
(emission) to observer (reception), for a static spherical point mass.
It is a standalone validation model, not a claim of exact Horizons parity:
moving/retarded deflectors, higher-order terms, and Horizons-specific numerical
conventions are outside its scope. It must not be applied to event roots until
the independent reference checks and DE441 comparison are complete.
"""
from __future__ import annotations

import math
from typing import Iterable

import numpy as np
from scipy.integrate import quad

from point_mass_light_deflection import (
    ARCSEC_PER_RAD,
    C_KM_S,
    GM_SUN_KM3_S2,
    R_SUN_KM,
    point_mass_transverse_deflection_rad,
)

VECTOR_TOL = 2.0e-13


def _vector3(value: Iterable[float], name: str) -> np.ndarray:
    vector = np.asarray(tuple(value), dtype=float)
    if vector.shape != (3,) or not np.all(np.isfinite(vector)):
        raise ValueError(f"{name} must contain exactly three finite coordinates.")
    return vector


def finite_distance_deflection(
    source_position_km: Iterable[float],
    observer_position_km: Iterable[float],
    deflector_position_km: Iterable[float],
    *,
    gm_km3_s2: float = GM_SUN_KM3_S2,
    c_km_s: float = C_KM_S,
) -> dict[str, np.ndarray | float]:
    """Return the finite-segment photon-direction deflection.

    All positions must be in one inertial frame and at one common epoch. The
    source-to-observer unperturbed propagation direction is n. The returned
    delta_n is the first-order change in photon propagation direction. The
    apparent sky direction (observer toward source) is therefore -unit(n+delta_n).

    The function rejects a zero-length ray and invalid physical parameters.
    It does not silently accept a ray whose closest approach lies outside the
    finite source-observer segment as a solar-grazing test.
    """
    source = _vector3(source_position_km, "source_position_km")
    observer = _vector3(observer_position_km, "observer_position_km")
    deflector = _vector3(deflector_position_km, "deflector_position_km")
    if not math.isfinite(gm_km3_s2) or gm_km3_s2 < 0.0:
        raise ValueError("GM must be finite and non-negative.")
    if not math.isfinite(c_km_s) or c_km_s <= 0.0:
        raise ValueError("Light speed must be finite and positive.")

    ray = observer - source
    distance = float(np.linalg.norm(ray))
    if distance <= 0.0:
        raise ValueError("Source and observer positions must differ.")
    n = ray / distance

    source_from_mass = source - deflector
    observer_from_mass = observer - deflector
    z_source = float(np.dot(source_from_mass, n))
    z_observer = float(np.dot(observer_from_mass, n))
    impact_vector = source_from_mass - z_source * n
    impact = float(np.linalg.norm(impact_vector))
    if impact <= 0.0:
        raise ValueError("Unperturbed ray passes through the point-mass singularity.")
    if z_observer <= z_source:
        raise RuntimeError("Invalid source-to-observer path orientation.")
    if not (z_source <= 0.0 <= z_observer):
        raise ValueError("Deflector's closest-approach plane lies outside the finite ray segment.")

    source_radius = float(np.linalg.norm(source_from_mass))
    observer_radius = float(np.linalg.norm(observer_from_mass))
    if source_radius <= 0.0 or observer_radius <= 0.0:
        raise ValueError("Source and observer cannot coincide with the deflector.")
    source_factor = z_source / source_radius
    observer_factor = z_observer / observer_radius
    delta_n = (
        -2.0 * gm_km3_s2
        / (c_km_s * c_km_s * impact)
        * (observer_factor - source_factor)
        * (impact_vector / impact)
    )
    apparent = -(n + delta_n)
    apparent_norm = float(np.linalg.norm(apparent))
    if apparent_norm <= 0.0 or not math.isfinite(apparent_norm):
        raise RuntimeError("Deflected apparent direction is invalid.")
    apparent /= apparent_norm
    return {
        "geometric_propagation_direction": n,
        "propagation_direction_change": delta_n,
        "geometric_apparent_direction": -n,
        "deflected_apparent_direction": apparent,
        "impact_parameter_km": impact,
        "source_longitudinal_coordinate_km": z_source,
        "observer_longitudinal_coordinate_km": z_observer,
        "finite_path_deflection_rad": float(np.linalg.norm(delta_n)),
        "finite_path_deflection_arcsec": float(np.linalg.norm(delta_n) * ARCSEC_PER_RAD),
    }


def _assert_close(actual: float, expected: float, tolerance: float, label: str) -> None:
    if abs(actual - expected) > tolerance:
        raise AssertionError(
            f"{label}: actual={actual:.16e}, expected={expected:.16e}, "
            f"tolerance={tolerance:.3e}"
        )


def run_reference_tests() -> None:
    # Analytic finite-endpoint solution independently agrees with direct
    # quadrature of the first-order transverse geodesic equation.
    b = 2.0 * R_SUN_KM
    z_source = -3.0 * b
    z_observer = 8.0 * b
    analytic = point_mass_transverse_deflection_rad(
        GM_SUN_KM3_S2, b, z_source, z_observer
    )
    integral, quad_error = quad(
        lambda z: -2.0 * GM_SUN_KM3_S2 / (C_KM_S * C_KM_S)
        * b / ((b * b + z * z) ** 1.5),
        z_source,
        z_observer,
        epsabs=1.0e-18,
        epsrel=1.0e-12,
    )
    _assert_close(analytic, integral, max(5.0e-15, 5.0 * quad_error),
                  "finite-endpoint quadrature")

    # Vector finite-distance implementation must reduce to the scalar result.
    source = np.array([b, 0.0, z_source])
    observer = np.array([b, 0.0, z_observer])
    result = finite_distance_deflection(source, observer, np.zeros(3))
    vector_delta = np.asarray(result["propagation_direction_change"])
    _assert_close(float(vector_delta[0]), analytic, 5.0e-15,
                  "vector/scalar transverse deflection")
    _assert_close(float(vector_delta[1]), 0.0, 1.0e-15,
                  "vector transverse y component")
    _assert_close(float(vector_delta[2]), 0.0, 1.0e-15,
                  "vector longitudinal component")

    # Direction convention and path-reversal test for a static monopole.
    # With b pointing away from the mass, the photon propagation direction
    # changes toward the mass (-b), while the apparent observer-to-source
    # direction changes away from the mass (+b). Reversing source/observer
    # reverses n, but must preserve these physical transverse changes.
    reversed = finite_distance_deflection(observer, source, np.zeros(3))
    impact_direction = np.array([1.0, 0.0, 0.0])
    propagation_change = np.asarray(result["propagation_direction_change"])
    reversed_propagation_change = np.asarray(
        reversed["propagation_direction_change"]
    )
    apparent_change = (
        np.asarray(result["deflected_apparent_direction"])
        - np.asarray(result["geometric_apparent_direction"])
    )
    reversed_apparent_change = (
        np.asarray(reversed["deflected_apparent_direction"])
        - np.asarray(reversed["geometric_apparent_direction"])
    )
    if not float(np.dot(propagation_change, impact_direction)) < 0.0:
        raise AssertionError("Photon propagation deflection has the wrong sign.")
    if not float(np.dot(apparent_change, impact_direction)) > 0.0:
        raise AssertionError("Apparent observer-to-source deflection has the wrong sign.")
    if not np.allclose(
        propagation_change, reversed_propagation_change, rtol=0.0, atol=VECTOR_TOL
    ):
        raise AssertionError("Propagation transverse change is not invariant under path reversal.")
    # Compare only the transverse component: normalization introduces a
    # second-order longitudinal component whose sign changes with n reversal.
    forward_apparent_transverse = float(np.dot(apparent_change, impact_direction))
    reverse_apparent_transverse = float(
        np.dot(reversed_apparent_change, impact_direction)
    )
    _assert_close(
        forward_apparent_transverse,
        reverse_apparent_transverse,
        VECTOR_TOL,
        "apparent transverse change under path reversal",
    )

    # Published finite-distance PPN expression (gamma=1):
    # Delta_alpha = (1+gamma) GM/(b c^2) * (cos(beta)-cos(delta)),
    # with sin(beta)=b/r_observer and sin(delta)=b/r_source.
    # Here cos(beta)=z_observer/r_observer and cos(delta)=z_source/r_source
    # because the closest-approach plane lies between source and observer.
    source_radius = float(np.linalg.norm(source))
    observer_radius = float(np.linalg.norm(observer))
    beta_cos = math.sqrt(1.0 - (b / observer_radius) ** 2)
    delta_cos = -math.sqrt(1.0 - (b / source_radius) ** 2)
    published_finite_angle = (
        2.0 * GM_SUN_KM3_S2 / (b * C_KM_S * C_KM_S)
        * (beta_cos - delta_cos)
    )
    _assert_close(
        float(result["finite_path_deflection_rad"]),
        published_finite_angle,
        5.0e-15,
        "published finite-distance PPN expression",
    )

    # A translated and rotated geometry must preserve the deflection magnitude.
    angle = 0.731
    rotation = np.array([
        [math.cos(angle), -math.sin(angle), 0.0],
        [math.sin(angle), math.cos(angle), 0.0],
        [0.0, 0.0, 1.0],
    ])
    rotated = finite_distance_deflection(
        rotation @ source, rotation @ observer, np.zeros(3)
    )
    _assert_close(
        float(rotated["finite_path_deflection_rad"]),
        float(result["finite_path_deflection_rad"]),
        VECTOR_TOL,
        "rotation invariance",
    )

    # Asymptotic solar grazing benchmark, with the solar radius as impact.
    solar_limit = 4.0 * GM_SUN_KM3_S2 / (C_KM_S * C_KM_S * R_SUN_KM) * ARCSEC_PER_RAD
    if not 1.750 < solar_limit < 1.753:
        raise AssertionError(f"Solar grazing limit outside 1.751-arcsec reference: {solar_limit}")

    # Finite endpoints remain below the asymptotic bound.
    finite_arcsec = abs(analytic) * ARCSEC_PER_RAD
    if not 0.0 < finite_arcsec < solar_limit:
        raise AssertionError("Finite-distance deflection violates its asymptotic bound.")

    # The closest-approach parameter is geometric and translation invariant.
    shift = np.array([1.0e8, -2.0e8, 3.0e8])
    shifted = finite_distance_deflection(source + shift, observer + shift, shift)
    _assert_close(
        float(shifted["finite_path_deflection_rad"]),
        float(result["finite_path_deflection_rad"]),
        VECTOR_TOL,
        "translation invariance",
    )

    print("phase=FINITE_DISTANCE_SOLAR_DEFLECTION_REFERENCE")
    print("model=STATIC_POINT_MASS_FIRST_ORDER_PPN_GAMMA_1")
    print(f"finite_path_analytic_deflection_arcsec={finite_arcsec:.12g}")
    print(f"finite_path_quadrature_deflection_arcsec={abs(integral) * ARCSEC_PER_RAD:.12g}")
    print(f"quadrature_error_estimate_rad={quad_error:.6e}")
    print(f"asymptotic_solar_grazing_deflection_arcsec={solar_limit:.12g}")
    print("finite_endpoint_case=PASS")
    print("vector_scalar_consistency=PASS")
    print("propagation_vs_apparent_direction_sign=PASS")
    print("source_observer_path_reversal=PASS")
    print("published_finite_distance_ppn_expression=PASS")
    print("translation_invariance=PASS")
    print("horizons_reproduction=NOT_RUN")
    print("de441_ephemeris_comparison=BLOCKED_UNTIL_DE441_KERNEL_AVAILABLE")
    print("event_roots_modified=NO")
    print("status=PASS")


if __name__ == "__main__":
    run_reference_tests()
