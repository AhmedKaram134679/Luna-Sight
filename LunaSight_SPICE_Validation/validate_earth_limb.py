"""LunaSight: independent estimate of Earth's apparent upper-limb crossing.

This is a research/validation script, not yet a fully matched reproduction of
JPL Horizons. It uses SPICE ephemerides, a fixed site on the Moon, a triaxial
ellipsoid tangent-limb construction, and a numerical zero-crossing search.

Important limitations:
- The lunar orientation uses the NAIF MOON_ME frame with the matching DE440
  lunar FK and binary PCK. This is closer to Horizons MEAN_ME, but is not by
  itself proof that every Horizons setting has been reproduced.
- The script uses geometric light-time iteration for Earth's center; it does
  not model a separate retarded emission time for every limb point.
- Stellar aberration is not applied.
- The Moon's shape is whatever radii are provided by the loaded PCK. A PCK may
  provide equal lunar radii, which is a spherical approximation.
- The event is the maximum elevation of the modeled Earth limb crossing zero.
  Compare with Horizons only after aligning frames and apparent-place settings.

Install:
  py -m venv .venv
  .\\.venv\\Scripts\\python.exe -m pip install --upgrade pip
  .\\.venv\\Scripts\\python.exe -m pip install spiceypy numpy scipy

Run:
  .\\.venv\\Scripts\\python.exe .\validate_earth_limb.py
"""
from __future__ import annotations

import csv
import math
import urllib.request
from pathlib import Path
from typing import Callable

import numpy as np
import spiceypy as spice
from scipy.optimize import minimize_scalar


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent
KERNEL_DIR = ROOT / "kernels"
RESULTS_DIR = ROOT / "results"
KERNEL_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

OBSERVER_LONGITUDE_DEG = 200.0
OBSERVER_LATITUDE_DEG = -88.45
OBSERVER_ALTITUDE_KM = 0.0

SEARCH_START_UTC = "2026-11-02T14:12:30"
SEARCH_STOP_UTC = "2026-11-02T14:16:00"
SAMPLE_STEP_SECONDS = 1.0

HORIZONS_REFERENCE_UTC = "2026-11-02T14:15:20"
HORIZONS_INTERPOLATED_UTC = "2026-11-02T14:15:20.333"

MOON_FRAME = "MOON_ME"
EARTH_FRAME = "ITRF93"
SPEED_OF_LIGHT_KM_S = 299792.458

KERNELS = {
    "naif0012.tls": "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/lsk/naif0012.tls",
    "pck00011.tpc": "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/pck/pck00011.tpc",
    "de440s.bsp": "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/planets/de440s.bsp",
    # High-accuracy lunar orientation data and its required frame kernel.
    "moon_pa_de440_200625.bpc": "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/pck/moon_pa_de440_200625.bpc",
    "moon_de440_220930.tf": "https://naif.jpl.nasa.gov/pub/naif/pds/wgc/kernels/fk/moon_de440_220930.tf",
    # High-accuracy Earth orientation and its ITRF93 frame association.
    "earth_latest_high_prec.bpc": "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/pck/earth_latest_high_prec.bpc",
    "earth_assoc_itrf93.tf": "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/fk/planets/earth_assoc_itrf93.tf",
}


# ---------------------------------------------------------------------------
# Kernel downloads and loading
# ---------------------------------------------------------------------------
def download_kernel(filename: str, url: str) -> Path:
    destination = KERNEL_DIR / filename
    if destination.exists() and destination.stat().st_size > 0:
        print(f"[KERNEL] Already present: {filename}")
        return destination

    temporary = destination.with_suffix(destination.suffix + ".part")
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "LunaSight-SPICE-Validation/1.0"},
    )
    print(f"[DOWNLOAD] {url}")
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            with temporary.open("wb") as output:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    output.write(chunk)
        if not temporary.exists() or temporary.stat().st_size == 0:
            raise RuntimeError(f"Downloaded kernel is empty: {filename}")
        temporary.replace(destination)
        print(f"[OK] Downloaded {filename} ({destination.stat().st_size:,} bytes)")
        return destination
    except Exception:
        if temporary.exists():
            temporary.unlink()
        raise


def load_kernels() -> None:
    for filename, url in KERNELS.items():
        path = download_kernel(filename, url)
        spice.furnsh(str(path))
        print(f"[SPICE] Loaded {filename}")

    # Fail early if the required frames/constants are unavailable.
    if spice.namfrm(MOON_FRAME) == 0:
        raise RuntimeError(f"SPICE frame is unavailable: {MOON_FRAME}")
    if spice.namfrm(EARTH_FRAME) == 0:
        raise RuntimeError(f"SPICE frame is unavailable: {EARTH_FRAME}")
    spice.bodvrd("MOON", "RADII", 3)
    spice.bodvrd("EARTH", "RADII", 3)


# ---------------------------------------------------------------------------
# Vector and coordinate helpers
# ---------------------------------------------------------------------------
def normalized(vector: np.ndarray) -> np.ndarray:
    length = float(np.linalg.norm(vector))
    if not math.isfinite(length) or length <= 0.0:
        raise ValueError("Cannot normalize a zero or invalid vector.")
    return vector / length


def body_position_j2000(body: str, et: float) -> np.ndarray:
    """Body-center position in J2000, relative to the solar-system barycenter."""
    position, _ = spice.spkpos(
        body, et, "J2000", "NONE", "SOLAR SYSTEM BARYCENTER"
    )
    return np.asarray(position, dtype=float)


def triaxial_surface_point_and_normal(
    longitude_rad: float,
    latitude_rad: float,
    altitude_km: float,
    radii_km: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Return a geodetic point and its outward normal on a triaxial ellipsoid.

    Longitude/latitude define the direction of the ellipsoid normal, not the
    radial direction from its center. Altitude is measured along that normal.
    This avoids calling georec(), which supports a rotational ellipsoid only.
    """
    a, b, c = (float(v) for v in radii_km)
    if min(a, b, c) <= 0.0:
        raise ValueError(f"Invalid body radii: {radii_km}")

    normal = np.array(
        [
            math.cos(latitude_rad) * math.cos(longitude_rad),
            math.cos(latitude_rad) * math.sin(longitude_rad),
            math.sin(latitude_rad),
        ],
        dtype=float,
    )
    normal = normalized(normal)

    # For a surface point p on x^2/a^2 + y^2/b^2 + z^2/c^2 = 1,
    # the unnormalized surface normal is (x/a^2, y/b^2, z/c^2).
    denominator = math.sqrt(
        (a * normal[0]) ** 2
        + (b * normal[1]) ** 2
        + (c * normal[2]) ** 2
    )
    surface = np.array(
        [
            a * a * normal[0] / denominator,
            b * b * normal[1] / denominator,
            c * c * normal[2] / denominator,
        ],
        dtype=float,
    )
    point = surface + altitude_km * normal
    return point, normal


def elevation_degrees(line_of_sight: np.ndarray, local_up: np.ndarray) -> float:
    direction = normalized(line_of_sight)
    up = normalized(local_up)
    sine_elevation = float(np.clip(np.dot(direction, up), -1.0, 1.0))
    return math.degrees(math.asin(sine_elevation))


# ---------------------------------------------------------------------------
# Observer state
# ---------------------------------------------------------------------------
def observer_state(et_reception: float) -> tuple[np.ndarray, np.ndarray]:
    """Return observer position and local up vector in J2000 coordinates."""
    moon_radii = np.asarray(spice.bodvrd("MOON", "RADII", 3)[1], dtype=float)
    longitude = math.radians(OBSERVER_LONGITUDE_DEG)
    latitude = math.radians(OBSERVER_LATITUDE_DEG)

    site_fixed, local_up_fixed = triaxial_surface_point_and_normal(
        longitude, latitude, OBSERVER_ALTITUDE_KM, moon_radii
    )

    moon_center = body_position_j2000("MOON", et_reception)
    moon_fixed_to_j2000 = np.asarray(
        spice.pxform(MOON_FRAME, "J2000", et_reception), dtype=float
    )

    observer_j2000 = moon_center + moon_fixed_to_j2000 @ site_fixed
    local_up_j2000 = normalized(moon_fixed_to_j2000 @ local_up_fixed)
    return observer_j2000, local_up_j2000


# ---------------------------------------------------------------------------
# Earth limb geometry
# ---------------------------------------------------------------------------
def maximum_earth_limb_elevation(et_reception: float) -> tuple[float, float]:
    """Return highest modeled Earth-limb elevation (degrees) and center light time.

    Earth is modeled as a triaxial ellipsoid using PCK radii. The tangent
    ellipsoid is transformed to a unit sphere, where its tangent circle can be
    parameterized and searched for the maximum elevation.
    """
    observer_j2000, local_up_j2000 = observer_state(et_reception)
    earth_radii = np.asarray(spice.bodvrd("EARTH", "RADII", 3)[1], dtype=float)
    if np.any(earth_radii <= 0.0):
        raise RuntimeError(f"Invalid Earth radii from PCK: {earth_radii}")

    # Iterate center light time. This is a first-order apparent geometry model.
    earth_now = body_position_j2000("EARTH", et_reception)
    light_time = float(np.linalg.norm(observer_j2000 - earth_now)) / SPEED_OF_LIGHT_KM_S
    et_emission = et_reception - light_time
    for _ in range(12):
        earth_emission = body_position_j2000("EARTH", et_emission)
        distance = float(np.linalg.norm(observer_j2000 - earth_emission))
        new_light_time = distance / SPEED_OF_LIGHT_KM_S
        new_emission = et_reception - new_light_time
        if abs(new_emission - et_emission) < 1e-9:
            light_time = new_light_time
            et_emission = new_emission
            break
        light_time = new_light_time
        et_emission = new_emission

    earth_center_j2000 = body_position_j2000("EARTH", et_emission)
    j2000_to_earth_fixed = np.asarray(
        spice.pxform("J2000", EARTH_FRAME, et_emission), dtype=float
    )
    earth_fixed_to_j2000 = np.asarray(
        spice.pxform(EARTH_FRAME, "J2000", et_emission), dtype=float
    )

    observer_relative_earth_fixed = j2000_to_earth_fixed @ (
        observer_j2000 - earth_center_j2000
    )
    scaled_observer = observer_relative_earth_fixed / earth_radii
    scaled_distance = float(np.linalg.norm(scaled_observer))
    if not math.isfinite(scaled_distance) or scaled_distance <= 1.0:
        raise RuntimeError(
            "Observer is inside/on the Earth ellipsoid; check frames and kernels."
        )

    # In unit-sphere coordinates, the tangent circle satisfies
    # dot(scaled_observer, y) = 1, with |y| = 1.
    axis = scaled_observer / scaled_distance
    circle_center = axis / scaled_distance
    circle_radius = math.sqrt(max(0.0, 1.0 - 1.0 / scaled_distance**2))

    helper = np.array([0.0, 0.0, 1.0])
    if abs(float(np.dot(axis, helper))) > 0.9:
        helper = np.array([0.0, 1.0, 0.0])
    basis_u = normalized(np.cross(axis, helper))
    basis_v = normalized(np.cross(axis, basis_u))

    def point_elevation(theta: float) -> float:
        unit_sphere_point = circle_center + circle_radius * (
            basis_u * math.cos(theta) + basis_v * math.sin(theta)
        )
        earth_fixed_point = unit_sphere_point * earth_radii
        limb_point_j2000 = earth_center_j2000 + (
            earth_fixed_to_j2000 @ earth_fixed_point
        )
        return elevation_degrees(
            limb_point_j2000 - observer_j2000,
            local_up_j2000,
        )

    # Coarse scan, followed by a bounded local maximization.
    sample_count = 720
    angles = np.linspace(0.0, 2.0 * math.pi, sample_count, endpoint=False)
    elevations = np.array([point_elevation(float(a)) for a in angles])
    best_index = int(np.argmax(elevations))
    best_angle = float(angles[best_index])
    half_window = 2.0 * math.pi / sample_count

    optimum = minimize_scalar(
        lambda angle: -point_elevation(float(angle)),
        bounds=(best_angle - half_window, best_angle + half_window),
        method="bounded",
        options={"xatol": 1e-11},
    )
    if not optimum.success:
        raise RuntimeError("Optimization of the Earth limb failed.")

    return -float(optimum.fun), light_time


# ---------------------------------------------------------------------------
# Event search and output
# ---------------------------------------------------------------------------
def bisect_crossing(
    function: Callable[[float], float],
    left: float,
    right: float,
    tolerance_seconds: float = 0.01,
) -> float:
    f_left = function(left)
    f_right = function(right)
    if f_left == 0.0:
        return left
    if f_right == 0.0:
        return right
    if f_left * f_right > 0.0:
        raise ValueError("The interval does not bracket a zero crossing.")

    while right - left > tolerance_seconds:
        middle = 0.5 * (left + right)
        f_middle = function(middle)
        if f_middle == 0.0:
            return middle
        if f_left * f_middle < 0.0:
            right = middle
            f_right = f_middle
        else:
            left = middle
            f_left = f_middle
    return 0.5 * (left + right)


def find_crossings() -> dict[str, object]:
    start_et = float(spice.str2et(SEARCH_START_UTC))
    stop_et = float(spice.str2et(SEARCH_STOP_UTC))
    if stop_et <= start_et:
        raise ValueError("Search stop time must be after search start time.")
    if SAMPLE_STEP_SECONDS <= 0.0:
        raise ValueError("SAMPLE_STEP_SECONDS must be positive.")

    count = int(math.floor((stop_et - start_et) / SAMPLE_STEP_SECONDS))
    sample_ets = [start_et + i * SAMPLE_STEP_SECONDS for i in range(count + 1)]
    if sample_ets[-1] < stop_et - 1e-7:
        sample_ets.append(stop_et)

    samples: list[dict[str, float | str]] = []
    print("\n[CALCULATION] Sampling highest Earth-limb elevation...")
    for index, et in enumerate(sample_ets):
        elevation, light_time = maximum_earth_limb_elevation(et)
        utc = spice.et2utc(et, "ISOC", 3)
        samples.append({
            "et": et,
            "utc": utc,
            "upper_limb_elevation_deg": elevation,
            "earth_center_light_time_s": light_time,
        })
        if index % 30 == 0 or index == len(sample_ets) - 1:
            print(f"  {utc} | upper limb = {elevation:+.9f} deg")

    csv_path = RESULTS_DIR / "earth_limb_samples.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=[
            "utc", "upper_limb_elevation_deg", "earth_center_light_time_s"
        ])
        writer.writeheader()
        for row in samples:
            writer.writerow({
                "utc": row["utc"],
                "upper_limb_elevation_deg": f'{float(row["upper_limb_elevation_deg"]):.12f}',
                "earth_center_light_time_s": f'{float(row["earth_center_light_time_s"]):.9f}',
            })
    print(f"[OUTPUT] Samples saved: {csv_path}")

    brackets: list[tuple[float, float]] = []
    for previous, current in zip(samples, samples[1:]):
        f0 = float(previous["upper_limb_elevation_deg"])
        f1 = float(current["upper_limb_elevation_deg"])
        if f0 == 0.0:
            brackets.append((float(previous["et"]), float(previous["et"])))
        elif f0 * f1 < 0.0:
            brackets.append((float(previous["et"]), float(current["et"])))
    if samples and float(samples[-1]["upper_limb_elevation_deg"]) == 0.0:
        final_et = float(samples[-1]["et"])
        brackets.append((final_et, final_et))

    if not brackets:
        first = samples[0]
        last = samples[-1]
        direction = (
            "decreasing" if float(last["upper_limb_elevation_deg"]) < float(first["upper_limb_elevation_deg"])
            else "increasing"
        )
        print("\n[NO CROSSING] No sign change was found in the sampled interval.")
        print(f"  First sample: {first['utc']} | {float(first['upper_limb_elevation_deg']):+.12f} deg")
        print(f"  Last sample:  {last['utc']} | {float(last['upper_limb_elevation_deg']):+.12f} deg")
        print(f"  Trend over interval: {direction}")
        print("  The event is not bracketed by this model/window; no crossing time will be fabricated.")
        return {"csv_path": str(csv_path), "crossings": []}

    def event_function(et: float) -> float:
        return maximum_earth_limb_elevation(et)[0]

    crossings: list[dict[str, str]] = []
    for left, right in brackets:
        crossing_et = left if left == right else bisect_crossing(
            event_function, left, right, tolerance_seconds=0.01
        )
        crossings.append({"utc": spice.et2utc(crossing_et, "ISOC", 3)})

    return {"csv_path": str(csv_path), "crossings": crossings}


def write_summary(crossings: list[dict[str, str]], csv_path: str) -> Path:
    summary_path = RESULTS_DIR / "validation_summary.txt"
    moon_radii = np.asarray(spice.bodvrd("MOON", "RADII", 3)[1], dtype=float)
    earth_radii = np.asarray(spice.bodvrd("EARTH", "RADII", 3)[1], dtype=float)
    with summary_path.open("w", encoding="utf-8") as file:
        file.write("LunaSight - Earth upper-limb crossing validation\n")
        file.write("================================================\n")
        file.write(f"Observer longitude east: {OBSERVER_LONGITUDE_DEG} deg\n")
        file.write(f"Observer latitude: {OBSERVER_LATITUDE_DEG} deg\n")
        file.write(f"Observer altitude: {OBSERVER_ALTITUDE_KM} km\n")
        file.write(f"Moon frame: {MOON_FRAME}\n")
        file.write(f"Earth frame: {EARTH_FRAME}\n")
        file.write(f"Moon radii from PCK (km): {moon_radii.tolist()}\n")
        file.write(f"Earth radii from PCK (km): {earth_radii.tolist()}\n")
        file.write(f"Search start UTC: {SEARCH_START_UTC}\n")
        file.write(f"Search stop UTC: {SEARCH_STOP_UTC}\n")
        file.write(f"Horizons displayed reference: {HORIZONS_REFERENCE_UTC} UTC\n")
        file.write(f"Horizons interpolation estimate: {HORIZONS_INTERPOLATED_UTC} UTC\n")
        for index, crossing in enumerate(crossings, start=1):
            file.write(f"SPICE modeled crossing {index}: {crossing['utc']} UTC\n")
        file.write(f"Samples CSV: {csv_path}\n")
        file.write("\nLimitations:\n")
        file.write("- Uses NAIF MOON_ME (DE440-related ME frame); verify exact equivalence with Horizons MEAN_ME settings.\n")
        file.write("- Uses ITRF93 with the downloaded high-accuracy Earth binary PCK.\n")
        file.write("- Center light-time iteration; no stellar aberration.\n")
        file.write("- One center emission epoch is used for the whole limb.\n")
        file.write("- Shape uses radii in the loaded PCK; lunar radii may be equal.\n")
        file.write("- Do not treat as an apples-to-apples Horizons comparison yet.\n")
    return summary_path


def main() -> None:
    print("=" * 72)
    print("LunaSight - Earth Upper Limb Crossing Validation")
    print("=" * 72)
    print(f"Observer longitude: {OBSERVER_LONGITUDE_DEG} deg E")
    print(f"Observer latitude:  {OBSERVER_LATITUDE_DEG} deg")
    print(f"Observer altitude:  {OBSERVER_ALTITUDE_KM} km")
    print(f"Moon frame:         {MOON_FRAME}")
    print(f"Earth frame:        {EARTH_FRAME}")
    print(f"Search start:       {SEARCH_START_UTC} UTC")
    print(f"Search stop:        {SEARCH_STOP_UTC} UTC")

    try:
        load_kernels()
        start_et = float(spice.str2et(SEARCH_START_UTC))
        stop_et = float(spice.str2et(SEARCH_STOP_UTC))
        for body in ("MOON", "EARTH"):
            for et in (start_et, stop_et):
                body_position_j2000(body, et)  # confirms SPK coverage
        print("\n[OK] Required bodies and epochs are available.")

        result = find_crossings()
        crossings = result["crossings"]
        print("\n" + "=" * 72)
        print("MODELED CROSSING RESULTS")
        print("=" * 72)
        for index, crossing in enumerate(crossings, start=1):
            print(f"Crossing {index}: {crossing['utc']} UTC")
        print("\nHorizons reference (from the previously recorded table):")
        print(f"  Displayed result: {HORIZONS_REFERENCE_UTC} UTC")
        print(f"  Interpolation estimate: {HORIZONS_INTERPOLATED_UTC} UTC")
        summary_path = write_summary(crossings, str(result["csv_path"]))
        print(f"\n[OUTPUT] Summary saved: {summary_path}")
        print("\n[IMPORTANT] This is not yet a matched-settings Horizons comparison.")
        print("Review the PCK radii, frame definitions, and apparent-place corrections before")
        print("using the computed time as a validated LunaSight reference value.")
    finally:
        spice.kclear()


if __name__ == "__main__":
    main()
