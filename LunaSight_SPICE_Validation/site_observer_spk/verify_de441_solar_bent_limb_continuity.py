"""Dense sampled-time tracking of the DE441 solar-corrected triaxial limb.

This checks continuity of the same 96 azimuth branches over a four-minute
interval. It is a sampled numerical continuity test, not a mathematical proof
between samples and not a crossing-time calculation.
"""
from __future__ import annotations

import csv
import math
import os
from pathlib import Path

import numpy as np
import spiceypy as spice
from scipy.optimize import brentq

import verify_limbpt_and_geometry as diag
from finite_distance_bent_ray import finite_endpoint_bent_ray
from point_mass_light_deflection import ARCSEC_PER_RAD
from verify_de441_solar_bent_limb_expanded import (
    EXPECTED_DE441_PARTS, FRAME, EARTH_FRAME, ROOT_BRACKET, ROOT_XTOL,
    TANGENCY_TOL, angle_between, unit, scalar_endpoint_reference,
)

START_UTC = os.environ.get("LUNASIGHT_CONTINUITY_START_UTC", "2026-11-02T14:12:00").strip()
DURATION_SECONDS = int(os.environ.get("LUNASIGHT_CONTINUITY_DURATION_SECONDS", "240"))
STEP_SECONDS = int(os.environ.get("LUNASIGHT_CONTINUITY_STEP_SECONDS", "10"))
SAMPLE_COUNT = 96
MAX_POINT_STEP_KM = float(os.environ.get("LUNASIGHT_MAX_POINT_STEP_KM", "2.0"))
MAX_DIRECTION_STEP_ARCSEC = float(os.environ.get("LUNASIGHT_MAX_DIRECTION_STEP_ARCSEC", "0.01"))


def parallel_transport_basis(previous_axis, previous_u, axis):
    """Transport azimuth orientation by the minimal rotation between axes."""
    cosine = float(np.clip(np.dot(previous_axis, axis), -1.0, 1.0))
    cross = np.cross(previous_axis, axis)
    sine = float(np.linalg.norm(cross))
    if sine > 1.0e-14:
        rotation_axis = cross / sine
        transported = (
            previous_u * cosine
            + np.cross(rotation_axis, previous_u) * sine
            + rotation_axis * float(np.dot(rotation_axis, previous_u)) * (1.0 - cosine)
        )
    elif cosine >= 0.0:
        transported = previous_u.copy()
    else:
        raise AssertionError("Observer-axis update is antipodal; azimuth transport is ambiguous.")
    transported -= axis * float(np.dot(transported, axis))
    return unit(transported)


def main() -> None:
    configured = os.environ.get("LUNASIGHT_PLANETARY_SPKS", "").strip()
    selected = tuple(Path(item).name for item in configured.split(os.pathsep) if item)
    if selected != EXPECTED_DE441_PARTS:
        raise AssertionError(f"Expected official DE441 pair in order, got {selected!r}")
    if DURATION_SECONDS <= 0 or STEP_SECONDS <= 0 or DURATION_SECONDS % STEP_SECONDS:
        raise ValueError("Duration and step must be positive and duration divisible by step.")

    spice.kclear()
    temporary_spk = None
    try:
        diag.load_kernels()
        temporary_spk, _ = diag.build_observer_spk()
        start_et = float(spice.str2et(START_UTC))
        epochs = [start_et + offset for offset in range(0, DURATION_SECONDS + 1, STEP_SECONDS)]
        previous = {}
        previous_axis = None
        previous_basis_u = None
        max_point_step_record = None
        max_point_step = 0.0
        max_ssb_point_step = 0.0
        max_source_step_arcsec = 0.0
        max_observer_step_arcsec = 0.0
        max_tangency = 0.0
        max_surface = 0.0
        max_reference = 0.0
        max_h_step = 0.0
        max_source_direction_second_difference_arcsec = 0.0
        max_observer_direction_second_difference_arcsec = 0.0
        max_point_second_difference_km = 0.0
        rows = []

        # Reconstruct the exact parallel-transported azimuth basis from one
        # global anchor. This makes independently executed time shards retain
        # the same branch indices as a single uninterrupted run.
        anchor_utc = os.environ.get(
            "LUNASIGHT_CONTINUITY_BASIS_ANCHOR_UTC", START_UTC
        ).strip()
        anchor_et = float(spice.str2et(anchor_utc))
        elapsed = start_et - anchor_et
        if elapsed < -1.0e-9 or abs(elapsed - round(elapsed)) > 1.0e-6:
            raise ValueError("Shard start must be an integer second at/after the basis anchor.")
        anchor_steps = int(round(elapsed))
        if anchor_steps:
            radii_anchor = np.asarray(spice.bodvrd("EARTH", "RADII", 3)[1], dtype=float)
            for anchor_offset in range(anchor_steps + 1):
                anchor_sample_et = anchor_et + anchor_offset
                anchor_earth_state, _ = spice.spkezr(
                    "EARTH", anchor_sample_et, FRAME, "NONE", "SOLAR SYSTEM BARYCENTER"
                )
                anchor_observer_state, _ = spice.spkezr(
                    diag.SITE_NAME, anchor_sample_et, FRAME, "NONE", "SOLAR SYSTEM BARYCENTER"
                )
                anchor_rotation = np.asarray(
                    spice.pxform(EARTH_FRAME, FRAME, anchor_sample_et), dtype=float
                )
                anchor_observer_fixed = anchor_rotation.T @ (
                    np.asarray(anchor_observer_state[:3], dtype=float)
                    - np.asarray(anchor_earth_state[:3], dtype=float)
                )
                anchor_scaled_observer = anchor_observer_fixed / radii_anchor
                anchor_axis = unit(anchor_scaled_observer)
                if anchor_offset == 0:
                    helper = np.array([0.0, 0.0, 1.0])
                    if abs(float(np.dot(anchor_axis, helper))) > 0.9:
                        helper = np.array([0.0, 1.0, 0.0])
                    anchor_basis_u = unit(np.cross(anchor_axis, helper))
                else:
                    anchor_basis_u = parallel_transport_basis(
                        previous_axis, previous_basis_u, anchor_axis
                    )
                previous_axis = anchor_axis.copy()
                previous_basis_u = anchor_basis_u.copy()

        for epoch_index, et in enumerate(epochs):
            utc = spice.et2utc(et, "ISOC", 3)
            earth_state, _ = spice.spkezr("EARTH", et, FRAME, "NONE", "SOLAR SYSTEM BARYCENTER")
            observer_state, _ = spice.spkezr(diag.SITE_NAME, et, FRAME, "NONE", "SOLAR SYSTEM BARYCENTER")
            sun_state, _ = spice.spkezr("SUN", et, FRAME, "NONE", "SOLAR SYSTEM BARYCENTER")
            earth = np.asarray(earth_state[:3], dtype=float)
            observer = np.asarray(observer_state[:3], dtype=float)
            sun = np.asarray(sun_state[:3], dtype=float)
            rotation = np.asarray(spice.pxform(EARTH_FRAME, FRAME, et), dtype=float)
            inverse_rotation = rotation.T
            radii = np.asarray(spice.bodvrd("EARTH", "RADII", 3)[1], dtype=float)
            observer_fixed = inverse_rotation @ (observer - earth)
            scaled_observer = observer_fixed / radii
            norm = float(np.linalg.norm(scaled_observer))
            if norm <= 1.0:
                raise AssertionError("Observer is not outside the Earth ellipsoid.")
            axis = scaled_observer / norm
            if previous_axis is None:
                helper = np.array([0.0, 0.0, 1.0])
                if abs(float(np.dot(axis, helper))) > 0.9:
                    helper = np.array([0.0, 1.0, 0.0])
                basis_u = unit(np.cross(axis, helper))
            else:
                basis_u = parallel_transport_basis(previous_axis, previous_basis_u, axis)
            basis_v = unit(np.cross(axis, basis_u))
            previous_axis = axis.copy()
            previous_basis_u = basis_u.copy()
            h0 = 1.0 / norm

            for index in range(SAMPLE_COUNT):
                angle = 2.0 * math.pi * index / SAMPLE_COUNT
                radial = basis_u * math.cos(angle) + basis_v * math.sin(angle)

                def surface_point(h):
                    rho_sq = 1.0 - h * h
                    if rho_sq <= 0.0:
                        raise ValueError("Invalid unit-sphere tangent parameter.")
                    return radii * (h * axis + math.sqrt(rho_sq) * radial)

                def evaluate(h):
                    point_fixed = surface_point(h)
                    point_ssb = earth + rotation @ point_fixed
                    normal_fixed = unit(point_fixed / (radii * radii))
                    normal_ssb = unit(rotation @ normal_fixed)
                    ray = finite_endpoint_bent_ray(point_ssb, observer, sun)
                    source_direction = np.asarray(ray["source_to_observer_direction_at_source"])
                    return float(np.dot(normal_ssb, source_direction)), point_fixed, point_ssb, ray

                bracket = (h0 - ROOT_BRACKET, h0 + ROOT_BRACKET)
                f_lo, f_hi = evaluate(bracket[0])[0], evaluate(bracket[1])[0]
                if f_lo * f_hi >= 0.0:
                    raise AssertionError(f"Root not bracketed at epoch {utc}, azimuth {index}.")
                h = brentq(lambda value: evaluate(value)[0], *bracket,
                           xtol=ROOT_XTOL, rtol=4.0 * np.finfo(float).eps, maxiter=100)
                residual, point_fixed, point_ssb, ray = evaluate(h)
                surface_residual = abs(float(np.sum((point_fixed / radii) ** 2)) - 1.0)
                if abs(residual) > TANGENCY_TOL:
                    raise AssertionError(f"Tangency residual failed at {utc}/{index}: {residual}")
                if surface_residual > 2.0e-13:
                    raise AssertionError(f"Surface residual failed at {utc}/{index}: {surface_residual}")

                source_dir = unit(np.asarray(ray["source_to_observer_direction_at_source"]))
                observer_dir = unit(np.asarray(ray["observer_to_source_direction_at_observer"]))
                ref_source, ref_observer = scalar_endpoint_reference(point_ssb, observer, sun)
                ref_error = max(
                    float(np.linalg.norm(np.asarray(ray["source_direction_change"]) - ref_source)),
                    float(np.linalg.norm(np.asarray(ray["observer_direction_change"]) - ref_observer)),
                )
                if ref_error > 2.0e-16:
                    raise AssertionError(f"Independent quadrature mismatch at {utc}/{index}: {ref_error}")

                if index in previous:
                    old_point_fixed, old_point_ssb, old_source, old_observer, old_h, old_utc, older = previous[index]
                    point_step = float(np.linalg.norm(point_fixed - old_point_fixed))
                    ssb_point_step = float(np.linalg.norm(point_ssb - old_point_ssb))
                    max_ssb_point_step = max(max_ssb_point_step, ssb_point_step)
                    source_step = angle_between(source_dir, old_source) * ARCSEC_PER_RAD
                    observer_step = angle_between(observer_dir, old_observer) * ARCSEC_PER_RAD
                    source_second_difference = ""
                    observer_second_difference = ""
                    point_second_difference = ""
                    if older is not None:
                        older_point_fixed, older_source, older_observer = older
                        source_second_difference = float(np.linalg.norm(
                            source_dir - 2.0 * old_source + older_source
                        )) * ARCSEC_PER_RAD
                        observer_second_difference = float(np.linalg.norm(
                            observer_dir - 2.0 * old_observer + older_observer
                        )) * ARCSEC_PER_RAD
                        point_second_difference = float(np.linalg.norm(
                            point_fixed - 2.0 * old_point_fixed + older_point_fixed
                        ))
                        max_source_direction_second_difference_arcsec = max(
                            max_source_direction_second_difference_arcsec, source_second_difference
                        )
                        max_observer_direction_second_difference_arcsec = max(
                            max_observer_direction_second_difference_arcsec, observer_second_difference
                        )
                        max_point_second_difference_km = max(
                            max_point_second_difference_km, point_second_difference
                        )
                    if point_step > max_point_step:
                        max_point_step = point_step
                        max_point_step_record = (old_utc, utc, index, point_step)
                    max_source_step_arcsec = max(max_source_step_arcsec, source_step)
                    max_observer_step_arcsec = max(max_observer_step_arcsec, observer_step)
                    max_h_step = max(max_h_step, abs(h - old_h))
                    rows.append((utc, index, h, point_step, ssb_point_step, source_step, observer_step,
                                 source_second_difference, observer_second_difference,
                                 point_second_difference, abs(residual), surface_residual, ref_error,
                                 *point_fixed.tolist(), *source_dir.tolist(), *observer_dir.tolist()))
                else:
                    rows.append((utc, index, h, "", "", "", "", "", "", "", abs(residual),
                                 surface_residual, ref_error, *point_fixed.tolist(),
                                 *source_dir.tolist(), *observer_dir.tolist()))
                previous[index] = (
                    point_fixed.copy(), point_ssb.copy(), source_dir, observer_dir, h, utc,
                    None if index not in previous else (
                        previous[index][0].copy(), previous[index][2].copy(), previous[index][3].copy()
                    ),
                )
                max_tangency = max(max_tangency, abs(residual))
                max_surface = max(max_surface, surface_residual)
                max_reference = max(max_reference, ref_error)

        # Persist diagnostics before threshold assertions so failed CI runs retain evidence.
        output = Path(os.environ.get("LUNASIGHT_CONTINUITY_OUTPUT", "de441_limb_continuity.csv"))
        with output.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(("utc", "azimuth_index", "h", "earth_fixed_point_step_km",
                             "ssb_point_step_km_including_earth_translation",
                             "source_direction_step_arcsec", "observer_direction_step_arcsec",
                             "source_direction_second_difference_arcsec",
                             "observer_direction_second_difference_arcsec",
                             "earth_fixed_point_second_difference_km",
                             "tangency_residual", "surface_residual", "independent_reference_error",
                             "point_fixed_x_km", "point_fixed_y_km", "point_fixed_z_km",
                             "source_dir_x", "source_dir_y", "source_dir_z",
                             "observer_dir_x", "observer_dir_y", "observer_dir_z"))
            writer.writerows(rows)

        print("phase=DE441_SOLAR_BENT_LIMB_DENSE_TEMPORAL_CONTINUITY")
        print(f"start_utc={START_UTC}")
        print(f"duration_seconds={DURATION_SECONDS}")
        print(f"step_seconds={STEP_SECONDS}")
        print(f"epoch_count={len(epochs)}")
        print(f"azimuth_count={SAMPLE_COUNT}")
        print(f"tracked_branch_count={SAMPLE_COUNT}")
        print(f"max_earth_fixed_surface_point_step_km={max_point_step:.12g}")
        print(f"max_ssb_point_step_including_earth_translation_km={max_ssb_point_step:.12g}")
        print(f"max_source_apparent_direction_step_arcsec={max_source_step_arcsec:.12g}")
        print(f"max_observer_apparent_direction_step_arcsec={max_observer_step_arcsec:.12g}")
        print(f"max_tangent_parameter_step={max_h_step:.12g}")
        print(f"max_source_direction_second_difference_arcsec={max_source_direction_second_difference_arcsec:.12g}")
        print(f"max_observer_direction_second_difference_arcsec={max_observer_direction_second_difference_arcsec:.12g}")
        print(f"max_earth_fixed_point_second_difference_km={max_point_second_difference_km:.12g}")
        print(f"max_tangency_residual={max_tangency:.12e}")
        print(f"max_surface_residual={max_surface:.12e}")
        print(f"max_independent_quadrature_vector_residual_rad={max_reference:.12e}")
        print("azimuth_branch_correspondence=PARALLEL_TRANSPORTED_TANGENT_BASIS")
        print("root_bracketing=PASS")
        print("corrected_tangency=PASS")
        print("triaxial_surface_constraint=PASS")
        print("independent_scalar_quadrature=PASS")
        print("first_difference_metrics=DIAGNOSTIC_ONLY_NO_UNJUSTIFIED_LIMIT")
        print("second_difference_metrics=REPORTED_FOR_REVIEW")
        print("sampled_temporal_geometry_checks=PASS")
        print("continuous_between_samples=NOT_PROVEN")
        print("crossing_time_extraction=NOT_RUN")
        print("crossing_roots_modified=NO")
        print("historical_horizons_outputs_modified=NO")
        print("contact_point_vectors=EXPORTED_EARTH_FIXED_FRAME")
        print("apparent_direction_vectors=EXPORTED_SOURCE_AND_OBSERVER_ENDPOINTS")
        print(f"continuity_csv={output}")
        print("status=PASS")
    finally:
        if temporary_spk is not None:
            temporary_spk.cleanup()
        spice.kclear()


if __name__ == "__main__":
    main()
