"""Independent weak-field point-mass light-deflection reference tests.

This module is deliberately separate from the event/limb solvers. It models a
static monopole and integrates the first-order transverse change of a photon
propagating along an unperturbed straight line. It is valid only when the
entire ray remains outside the gravitating body and GM/(b*c^2) is small.

It is NOT an Earth interior model, an ellipsoidal gravity model, a complete
finite-distance astrometric model, or a replacement for Horizons/IAU SOFA.
No result from this module is applied to a LunaSight crossing root.
"""
from __future__ import annotations

import math

C_KM_S = 299792.458
GM_SUN_KM3_S2 = 1.32712440018e11
GM_EARTH_KM3_S2 = 3.98600435436e5
R_SUN_KM = 695700.0
R_EARTH_EQUATORIAL_KM = 6378.137
ARCSEC_PER_RAD = 180.0 * 3600.0 / math.pi


def point_mass_transverse_deflection_rad(
    gm_km3_s2: float,
    impact_parameter_km: float,
    source_z_km: float,
    observer_z_km: float,
    *,
    c_km_s: float = C_KM_S,
) -> float:
    """Return signed first-order transverse photon-direction change (radians).

    Coordinates put the point mass at the origin and the unperturbed photon
    path at (b, 0, z), propagating from source_z to observer_z. The returned
    sign is negative along +x for positive b, matching the transverse
    acceleration toward the mass:
        d(n_x)/dz = -2*GM/c^2 * b/(b^2+z^2)^(3/2).

    The source must precede the observer along the propagation direction.
    """
    values = (gm_km3_s2, impact_parameter_km, source_z_km, observer_z_km, c_km_s)
    if not all(math.isfinite(value) for value in values):
        raise ValueError("All inputs must be finite.")
    if gm_km3_s2 < 0.0:
        raise ValueError("GM must be non-negative.")
    if impact_parameter_km <= 0.0:
        raise ValueError("Impact parameter must be positive.")
    if observer_z_km <= source_z_km:
        raise ValueError("Observer must lie downstream of the source.")
    if c_km_s <= 0.0:
        raise ValueError("Light speed must be positive.")
    if gm_km3_s2 == 0.0:
        return 0.0

    source_factor = source_z_km / math.hypot(impact_parameter_km, source_z_km)
    observer_factor = observer_z_km / math.hypot(impact_parameter_km, observer_z_km)
    return (
        -2.0 * gm_km3_s2
        / (c_km_s * c_km_s * impact_parameter_km)
        * (observer_factor - source_factor)
    )


def asymptotic_grazing_deflection_arcsec(gm_km3_s2: float, impact_parameter_km: float) -> float:
    """Return the |source|,|observer| -> infinity monopole limit, in arcsec."""
    if not math.isfinite(gm_km3_s2) or gm_km3_s2 < 0.0:
        raise ValueError("GM must be finite and non-negative.")
    if not math.isfinite(impact_parameter_km) or impact_parameter_km <= 0.0:
        raise ValueError("Impact parameter must be finite and positive.")
    return (
        4.0 * gm_km3_s2
        / (C_KM_S * C_KM_S * impact_parameter_km)
        * ARCSEC_PER_RAD
    )


def _run_tests() -> None:
    # Independent numerical quadrature of the differential equation.
    from scipy.integrate import quad

    gm = GM_SUN_KM3_S2
    b = R_SUN_KM
    source_z = -3.0 * b
    observer_z = 8.0 * b
    actual = point_mass_transverse_deflection_rad(gm, b, source_z, observer_z)
    integral, error = quad(
        lambda z: -2.0 * gm / (C_KM_S * C_KM_S)
        * b / ((b * b + z * z) ** 1.5),
        source_z,
        observer_z,
        epsabs=1.0e-18,
        epsrel=1.0e-12,
    )
    assert abs(actual - integral) <= max(5.0e-15, 5.0 * error), (
        f"finite-path analytic/quadrature mismatch: {actual} vs {integral}"
    )

    zero = point_mass_transverse_deflection_rad(0.0, b, source_z, observer_z)
    assert zero == 0.0, f"zero-GM case is not zero: {zero}"

    solar = asymptotic_grazing_deflection_arcsec(GM_SUN_KM3_S2, R_SUN_KM)
    assert abs(solar - 1.751) < 0.002, f"solar grazing reference out of range: {solar}"

    earth = asymptotic_grazing_deflection_arcsec(
        GM_EARTH_KM3_S2, R_EARTH_EQUATORIAL_KM
    )
    assert abs(earth - 0.0005737) < 0.000002, (
        f"Earth exterior-monopole grazing scale out of range: {earth}"
    )

    # Finite endpoints must produce less deflection than the two-sided
    # asymptotic limit, with the expected sign and monotonicity.
    finite_abs = abs(actual)
    asymptotic = solar / ARCSEC_PER_RAD
    assert actual < 0.0, "deflection sign is not toward the mass"
    assert 0.0 < finite_abs < asymptotic, (
        f"finite path should be below asymptotic limit: {finite_abs}, {asymptotic}"
    )

    # Increasing the source/observer distances approaches the asymptotic limit.
    near_infinite = point_mass_transverse_deflection_rad(
        gm, b, -1.0e7 * b, 1.0e7 * b
    )
    assert abs(abs(near_infinite) - asymptotic) / asymptotic < 1.0e-12

    print("phase=INDEPENDENT_STATIC_POINT_MASS_DEFLECTION_TESTS")
    print(f"finite_path_analytic_rad={actual:.15e}")
    print(f"finite_path_quadrature_rad={integral:.15e}")
    print(f"finite_path_quadrature_error_estimate_rad={error:.3e}")
    print(f"solar_asymptotic_grazing_arcsec={solar:.9f}")
    print(f"earth_exterior_monopole_grazing_arcsec={earth:.9f}")
    print("earth_model_scope=EXTERIOR_SPHERICAL_MONOPOLE_ONLY")
    print("earth_interior_model=NOT_PROVIDED")
    print("moving_deflector_and_retarded_gravity=NOT_MODELED")
    print("stellar_aberration_or_light_time_ordering=NOT_MODELED")
    print("crossing_roots_modified=NO")
    print("status=PASS")


if __name__ == "__main__":
    _run_tests()
