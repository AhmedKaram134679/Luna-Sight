"""Finite-endpoint first-order bent-ray reference for a static point mass.

The model solves the first-order boundary-value problem with both source and
observer positions held fixed. It returns the local propagation directions at
both endpoints, rather than treating the integrated direction change for a
fixed initial ray as the endpoint direction of a ray joining the same points.

This is a standalone mathematical reference. It does not model a moving or
retarded deflector, a distributed solar interior, higher-order post-Newtonian
terms, stellar aberration, or Horizons-specific conventions. The deflector
position and both endpoints must be supplied in one inertial frame at one
common reference epoch. It is not yet connected to DE441 or the lunar limb
solver and must not be used to alter crossing roots.
"""
from __future__ import annotations

import math
from typing import Iterable

import numpy as np
from scipy.integrate import quad_vec

from point_mass_light_deflection import (
    ARCSEC_PER_RAD,
    C_KM_S,
    GM_SUN_KM3_S2,
)


def _vector3(value: Iterable[float], name: str) -> np.ndarray:
    vector = np.asarray(tuple(value), dtype=float)
    if vector.shape != (3,) or not np.all(np.isfinite(vector)):
        raise ValueError(f"{name} must contain exactly three finite coordinates.")
    return vector


def _unit(vector: np.ndarray, name: str) -> np.ndarray:
    norm = float(np.linalg.norm(vector))
    if not math.isfinite(norm) or norm <= 0.0:
        raise ValueError(f"{name} must have a finite, positive norm.")
    return vector / norm


def finite_endpoint_bent_ray(
    source_position_km: Iterable[float],
    observer_position_km: Iterable[float],
    deflector_position_km: Iterable[float],
    *,
    gm_km3_s2: float = GM_SUN_KM3_S2,
    c_km_s: float = C_KM_S,
    integration_epsabs: float = 1.0e-18,
    integration_epsrel: float = 2.0e-12,
) -> dict[str, np.ndarray | float]:
    """Solve the first-order static-monopole ray with fixed finite endpoints.

    Let l run from 0 at the source to L at the observer and let n be the
    unperturbed source-to-observer unit vector. The first-order transverse
    acceleration along the unperturbed segment is

        f(l) = -2 GM/c^2 * b / |source + n*l - deflector|^3,

    where b is the constant impact vector perpendicular to n. The transverse
    perturbation y obeys y''=f with y(0)=y(L)=0. Consequently,

        y'(0) = -1/L * integral_0^L (L-l) f(l) dl
        y'(L) = y'(0) + integral_0^L f(l) dl.

    The returned endpoint directions are normalized n+y'(0) and n+y'(L).
    They are local ray directions at the source and observer, respectively.
    """
    source = _vector3(source_position_km, "source_position_km")
    observer = _vector3(observer_position_km, "observer_position_km")
    deflector = _vector3(deflector_position_km, "deflector_position_km")
    if not math.isfinite(gm_km3_s2) or gm_km3_s2 < 0.0:
        raise ValueError("GM must be finite and non-negative.")
    if not math.isfinite(c_km_s) or c_km_s <= 0.0:
        raise ValueError("Light speed must be finite and positive.")
    if not math.isfinite(integration_epsabs) or integration_epsabs <= 0.0:
        raise ValueError("Absolute integration tolerance must be finite and positive.")
    if not math.isfinite(integration_epsrel) or integration_epsrel <= 0.0:
        raise ValueError("Relative integration tolerance must be finite and positive.")

    segment = observer - source
    length = float(np.linalg.norm(segment))
    if length <= 0.0:
        raise ValueError("Source and observer positions must differ.")
    n = segment / length
    relative_source = source - deflector
    longitudinal_source = float(np.dot(relative_source, n))
    impact_vector = relative_source - longitudinal_source * n
    impact = float(np.linalg.norm(impact_vector))
    if impact <= 0.0:
        raise ValueError("Unperturbed segment passes through the point-mass singularity.")

    if gm_km3_s2 == 0.0:
        zero = np.zeros(3, dtype=float)
        return {
            "geometric_direction": n,
            "source_direction_change": zero.copy(),
            "observer_direction_change": zero.copy(),
            "source_to_observer_direction_at_source": n.copy(),
            "source_to_observer_direction_at_observer": n.copy(),
            "observer_to_source_direction_at_observer": -n.copy(),
            "segment_length_km": length,
            "impact_parameter_km": impact,
            "transverse_displacement_closure_km": 0.0,
            "source_direction_change_arcsec": 0.0,
            "observer_direction_change_arcsec": 0.0,
        }

    coefficient = -2.0 * gm_km3_s2 / (c_km_s * c_km_s)

    def transverse_acceleration(distance: float) -> np.ndarray:
        relative = relative_source + n * distance
        radius = float(np.linalg.norm(relative))
        if radius <= 0.0:
            raise ValueError("Ray intersects the point-mass singularity.")
        return coefficient * impact_vector / (radius * radius * radius)

    def weighted_integrand(distance: float) -> np.ndarray:
        force = transverse_acceleration(distance)
        return np.concatenate((force, ((length - distance) / length) * force))

    integrals, endpoint_integral_error = quad_vec(
        weighted_integrand, 0.0, length,
        epsabs=integration_epsabs, epsrel=integration_epsrel,
    )
    total_direction_change = np.asarray(integrals[:3], dtype=float)
    weighted_direction_change = np.asarray(integrals[3:], dtype=float)
    source_change = -weighted_direction_change
    observer_change = source_change + total_direction_change

    # Verify the fixed-endpoint boundary condition independently from the
    # analytic endpoint construction by integrating the transverse position.
    def displacement_integrand(distance: float) -> np.ndarray:
        partial, _ = quad_vec(
            transverse_acceleration, 0.0, distance,
            epsabs=integration_epsabs, epsrel=integration_epsrel,
        )
        return source_change + np.asarray(partial, dtype=float)

    closure, closure_integral_error = quad_vec(
        displacement_integrand, 0.0, length,
        epsabs=max(integration_epsabs, 1.0e-14),
        epsrel=max(integration_epsrel, 1.0e-12),
    )
    closure_norm = float(np.linalg.norm(closure))
    if closure_norm > max(1.0e-8, length * 1.0e-10):
        raise RuntimeError(
            f"Fixed-endpoint transverse closure failed: {closure_norm:.6e} km"
        )

    source_direction = _unit(n + source_change, "source endpoint direction")
    observer_direction = _unit(n + observer_change, "observer endpoint direction")
    return {
        "geometric_direction": n,
        "source_direction_change": source_change,
        "observer_direction_change": observer_change,
        "source_to_observer_direction_at_source": source_direction,
        "source_to_observer_direction_at_observer": observer_direction,
        "observer_to_source_direction_at_observer": -observer_direction,
        "segment_length_km": length,
        "impact_parameter_km": impact,
        "transverse_displacement_closure_km": closure_norm,
        "endpoint_integral_error_estimate": float(endpoint_integral_error),
        "closure_integral_error_estimate_km": float(closure_integral_error),
        "source_direction_change_arcsec": float(
            np.linalg.norm(source_change) * ARCSEC_PER_RAD
        ),
        "observer_direction_change_arcsec": float(
            np.linalg.norm(observer_change) * ARCSEC_PER_RAD
        ),
    }


def run_reference_tests() -> None:
    from scipy.integrate import quad

    gm = GM_SUN_KM3_S2
    c = C_KM_S
    impact = 2.0e6
    z_source = -3.0 * impact
    z_observer = 8.0 * impact
    source = np.array([impact, 0.0, z_source])
    observer = np.array([impact, 0.0, z_observer])
    mass = np.zeros(3)
    result = finite_endpoint_bent_ray(source, observer, mass)

    # Independent scalar quadrature of the force and its endpoint weighting.
    coefficient = -2.0 * gm / (c * c)
    force = lambda z: coefficient * impact / (impact * impact + z * z) ** 1.5
    total, total_error = quad(force, z_source, z_observer, epsabs=1.0e-18, epsrel=1.0e-12)
    path_length = z_observer - z_source
    # Integrate over dimensionless u in [0, 1]. Both independent endpoint
    # references are angular integrals (radians), with separately scaled errors.
    weighted, weighted_error = quad(
        lambda u: (1.0 - u) * force(z_source + path_length * u),
        0.0, 1.0, epsabs=1.0e-25, epsrel=2.0e-13,
    )
    total, total_error = quad(
        lambda u: path_length * force(z_source + path_length * u),
        0.0, 1.0, epsabs=1.0e-25, epsrel=2.0e-13,
    )
    expected_source = -weighted
    expected_observer = expected_source + total
    actual_source = float(np.asarray(result["source_direction_change"])[0])
    actual_observer = float(np.asarray(result["observer_direction_change"])[0])
    source_reference_error_rad = weighted_error
    tolerance = max(2.0e-14, 8.0 * (total_error + source_reference_error_rad))
    if abs(actual_source - expected_source) > tolerance:
        raise AssertionError("Source endpoint direction disagrees with independent quadrature.")
    if abs(actual_observer - expected_observer) > tolerance:
        raise AssertionError("Observer endpoint direction disagrees with independent quadrature.")

    # Tightening production tolerances must converge to the independent scalar reference.
    tight = finite_endpoint_bent_ray(
        source, observer, mass, integration_epsabs=1.0e-24,
        integration_epsrel=2.0e-14,
    )
    tight_source = float(np.asarray(tight["source_direction_change"])[0])
    tight_observer = float(np.asarray(tight["observer_direction_change"])[0])
    if abs(tight_source - expected_source) > max(5.0e-14, 16.0 * source_reference_error_rad):
        raise AssertionError("Tight source endpoint result failed independent convergence check.")
    if abs(tight_observer - expected_observer) > max(5.0e-14, 16.0 * total_error):
        raise AssertionError("Tight observer endpoint result failed independent convergence check.")

    # Symmetric endpoints around closest approach have equal and opposite
    # first-order endpoint corrections for this static monopole geometry.
    symmetric_source = np.array([impact, 0.0, -4.0 * impact])
    symmetric_observer = np.array([impact, 0.0, 4.0 * impact])
    symmetric = finite_endpoint_bent_ray(symmetric_source, symmetric_observer, mass)
    symmetric_source_change = np.asarray(symmetric["source_direction_change"])
    symmetric_observer_change = np.asarray(symmetric["observer_direction_change"])
    if not np.allclose(symmetric_source_change, -symmetric_observer_change,
                       rtol=0.0, atol=2.0e-14):
        raise AssertionError("Symmetric endpoint directions do not have equal/opposite corrections.")

    # A fixed-endpoint ray must return to the prescribed observer position.
    if float(result["transverse_displacement_closure_km"]) > 1.0e-8:
        raise AssertionError("Fixed-endpoint transverse displacement does not close.")

    # Zero mass must recover the straight segment at both endpoints.
    zero = finite_endpoint_bent_ray(source, observer, mass, gm_km3_s2=0.0)
    if not np.array_equal(zero["source_to_observer_direction_at_source"],
                          zero["source_to_observer_direction_at_observer"]):
        raise AssertionError("Zero-GM endpoint directions are not identical.")
    if np.linalg.norm(zero["source_direction_change"]) != 0.0:
        raise AssertionError("Zero-GM source correction is nonzero.")

    # Reversing endpoints swaps the local endpoint directions with sign
    # reversal, while preserving the physical observer-to-source convention.
    reverse = finite_endpoint_bent_ray(observer, source, mass)
    reverse_source = np.asarray(reverse["source_to_observer_direction_at_source"])
    reverse_observer = np.asarray(reverse["source_to_observer_direction_at_observer"])
    forward_source = np.asarray(result["source_to_observer_direction_at_source"])
    forward_observer = np.asarray(result["source_to_observer_direction_at_observer"])
    if not np.allclose(reverse_source, -forward_observer, rtol=0.0, atol=2.0e-13):
        raise AssertionError("Path reversal did not swap the observer endpoint direction.")
    if not np.allclose(reverse_observer, -forward_source, rtol=0.0, atol=2.0e-13):
        raise AssertionError("Path reversal did not swap the source endpoint direction.")

    # Rotations/translations must not change the endpoint correction magnitudes.
    angle = 0.731
    rotation = np.array([
        [math.cos(angle), -math.sin(angle), 0.0],
        [math.sin(angle), math.cos(angle), 0.0],
        [0.0, 0.0, 1.0],
    ])
    shift = np.array([1e7, -2e7, 3e7])
    rotated = finite_endpoint_bent_ray(
        rotation @ source, rotation @ observer, rotation @ mass
    )
    translated = finite_endpoint_bent_ray(
        source + shift, observer + shift, mass + shift
    )
    for label, candidate in (("rotation", rotated), ("translation", translated)):
        if abs(float(candidate["source_direction_change_arcsec"])
               - float(result["source_direction_change_arcsec"])) > 2.0e-10:
            raise AssertionError(f"{label} invariance failed for source endpoint.")
        if abs(float(candidate["observer_direction_change_arcsec"])
               - float(result["observer_direction_change_arcsec"])) > 2.0e-10:
            raise AssertionError(f"{label} invariance failed for observer endpoint.")

    print("phase=FINITE_ENDPOINT_BENT_RAY_REFERENCE")
    print("model=STATIC_POINT_MASS_FIRST_ORDER_PPN_GAMMA_1_FIXED_ENDPOINTS")
    print(f"source_endpoint_direction_change_arcsec={result['source_direction_change_arcsec']:.12g}")
    print(f"observer_endpoint_direction_change_arcsec={result['observer_direction_change_arcsec']:.12g}")
    print(f"independent_source_quadrature_error_rad={source_reference_error_rad:.6e}")
    print(f"independent_observer_quadrature_error_rad={total_error:.6e}")
    print(f"production_endpoint_integral_error_estimate={result['endpoint_integral_error_estimate']:.6e}")
    print(f"tight_endpoint_integral_error_estimate={tight['endpoint_integral_error_estimate']:.6e}")
    print(f"independent_source_reference_error_rad={source_reference_error_rad:.6e}")
    print(f"independent_observer_reference_error_rad={total_error:.6e}")
    print("tight_tolerance_convergence=PASS")
    print("symmetric_endpoint_geometry=PASS")
    print(f"transverse_displacement_closure_km={result['transverse_displacement_closure_km']:.6e}")
    print("endpoint_direction_reference=PASS")
    print("fixed_endpoint_boundary_conditions=PASS")
    print("zero_gm_limit=PASS")
    print("path_reversal=PASS")
    print("rotation_translation_invariance=PASS")
    print("de441_ephemeris_comparison=NOT_RUN")
    print("limb_tangency_application=NOT_RUN")
    print("crossing_roots_modified=NO")
    print("status=PASS")


if __name__ == "__main__":
    run_reference_tests()
