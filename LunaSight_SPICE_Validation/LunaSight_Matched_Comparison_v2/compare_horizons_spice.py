"""LunaSight diagnostic comparison: Horizons reference rows vs SPICE.

This is a diagnostic, not a final event-validation product.
"""
from __future__ import annotations

import csv
import math
import urllib.request
from pathlib import Path

import numpy as np
import spiceypy as spice
from scipy.optimize import minimize_scalar

ROOT = Path(__file__).resolve().parent
KERNEL_DIR = ROOT / "kernels"
RESULTS_DIR = ROOT / "results"
KERNEL_DIR.mkdir(exist_ok=True)
RESULTS_DIR.mkdir(exist_ok=True)

SITE_LON_DEG = 200.0
SITE_LAT_DEG = -88.45
SITE_ALT_KM = 0.0
MOON_FRAME = "MOON_ME"
EARTH_FRAME = "ITRF93"
C_KM_S = 299792.458

# Values transcribed from the previously supplied Horizons table.
# Elevation is apparent, airless; diameter is angular diameter in arcseconds.
HORIZONS = [
    ("2026-11-02T14:12:30", -0.970998305, 7013.649),
    ("2026-11-02T14:13:00", -0.971544587, 7013.626),
    ("2026-11-02T14:14:00", -0.972637156, 7013.581),
    ("2026-11-02T14:15:00", -0.973729732, 7013.536),
    ("2026-11-02T14:15:20", -0.974093926, 7013.520),
    ("2026-11-02T14:15:21", -0.974112136, 7013.520),
    ("2026-11-02T14:16:00", -0.974822316, 7013.490),
]

KERNELS = {
    "naif0012.tls": "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/lsk/naif0012.tls",
    "pck00011.tpc": "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/pck/pck00011.tpc",
    "de440s.bsp": "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/planets/de440s.bsp",
    "moon_pa_de440_200625.bpc": "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/pck/moon_pa_de440_200625.bpc",
    "moon_de440_220930.tf": "https://naif.jpl.nasa.gov/pub/naif/pds/wgc/kernels/fk/moon_de440_220930.tf",
    "earth_latest_high_prec.bpc": "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/pck/earth_latest_high_prec.bpc",
    "earth_assoc_itrf93.tf": "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/fk/planets/earth_assoc_itrf93.tf",
}

def load_kernels():
    for name, url in KERNELS.items():
        path = KERNEL_DIR / name
        if not path.exists() or path.stat().st_size == 0:
            tmp = path.with_suffix(path.suffix + ".part")
            req = urllib.request.Request(url, headers={"User-Agent": "LunaSight-Matched-Compare/2.0"})
            print(f"[DOWNLOAD] {name}")
            try:
                with urllib.request.urlopen(req, timeout=90) as response, tmp.open("wb") as out:
                    shutil_copyfileobj(response, out)
                if tmp.stat().st_size == 0:
                    raise RuntimeError(f"Empty kernel: {name}")
                tmp.replace(path)
            except Exception:
                if tmp.exists():
                    tmp.unlink()
                raise
        spice.furnsh(str(path))
    if spice.namfrm(MOON_FRAME) == 0 or spice.namfrm(EARTH_FRAME) == 0:
        raise RuntimeError("Required SPICE frame unavailable; check FK/PCK kernel set.")
    spice.bodvrd("MOON", "RADII", 3)
    spice.bodvrd("EARTH", "RADII", 3)

def shutil_copyfileobj(src, dst):
    while True:
        chunk = src.read(1024 * 1024)
        if not chunk:
            break
        dst.write(chunk)

def unit(v):
    n = float(np.linalg.norm(v))
    if not math.isfinite(n) or n <= 0:
        raise ValueError("Invalid zero/nonfinite vector.")
    return np.asarray(v, dtype=float) / n

def body_pos(body, et):
    p, _ = spice.spkpos(body, et, "J2000", "NONE", "SOLAR SYSTEM BARYCENTER")
    return np.asarray(p, dtype=float)

def surface_point_normal(lon_deg, lat_deg, alt, radii):
    a, b, c = map(float, radii)
    lon, lat = math.radians(lon_deg), math.radians(lat_deg)
    n = unit(np.array([math.cos(lat)*math.cos(lon), math.cos(lat)*math.sin(lon), math.sin(lat)]))
    den = math.sqrt((a*n[0])**2 + (b*n[1])**2 + (c*n[2])**2)
    p = np.array([a*a*n[0]/den, b*b*n[1]/den, c*c*n[2]/den]) + alt*n
    return p, n

def observer_state(et):
    mr = np.asarray(spice.bodvrd("MOON", "RADII", 3)[1], dtype=float)
    site_fixed, up_fixed = surface_point_normal(SITE_LON_DEG, SITE_LAT_DEG, SITE_ALT_KM, mr)
    moon = body_pos("MOON", et)
    rot = np.asarray(spice.pxform(MOON_FRAME, "J2000", et), dtype=float)
    return moon + rot @ site_fixed, unit(rot @ up_fixed)

def observer_velocity(et):
    # Centered finite difference includes orbital and rotational velocity of the site.
    dt = 0.25
    p0, _ = observer_state(et - dt)
    p1, _ = observer_state(et + dt)
    return (p1 - p0) / (2.0 * dt)

def elev(vec, up):
    return math.degrees(math.asin(float(np.clip(np.dot(unit(vec), unit(up)), -1, 1))))

def apparent_center(et, correction):
    obs, up = observer_state(et)
    vel = observer_velocity(et)
    # Earth center as target, Moon's system barycenter as intermediary is avoided:
    # calculate retarded target position, then apply stellar aberration using site velocity.
    if correction == "NONE":
        target = body_pos("EARTH", et)
    else:
        lt = float(np.linalg.norm(body_pos("EARTH", et) - obs)) / C_KM_S
        te = et - lt
        for _ in range(20):
            target = body_pos("EARTH", te)
            new_lt = float(np.linalg.norm(target - obs)) / C_KM_S
            new_te = et - new_lt
            if abs(new_te - te) < 1e-10:
                te = new_te
                break
            te = new_te
        target = body_pos("EARTH", te)
    direction = target - obs
    if correction == "LT+S":
        direction = np.asarray(spice.stelab(direction, vel), dtype=float)
    return elev(direction, up)

def max_limb_elevation(et, correction):
    obs, up = observer_state(et)
    vel = observer_velocity(et)
    er = np.asarray(spice.bodvrd("EARTH", "RADII", 3)[1], dtype=float)
    # Iterate center light time first to establish the approximate retarded epoch.
    now = body_pos("EARTH", et)
    lt = float(np.linalg.norm(now - obs)) / C_KM_S
    te_center = et - lt
    for _ in range(20):
        ec = body_pos("EARTH", te_center)
        new_lt = float(np.linalg.norm(ec - obs)) / C_KM_S
        new_te = et - new_lt
        if abs(new_te - te_center) < 1e-10:
            te_center = new_te
            break
        te_center = new_te
    earth_center = body_pos("EARTH", te_center)

    def point_el(theta):
        # Tangent locus for ellipsoid: p^T Q^-1 p = 1 and normal dot (observer-p)=0.
        # Parameterize the tangent circle after scaling the observer to a unit sphere.
        j2e = np.asarray(spice.pxform("J2000", EARTH_FRAME, te_center), dtype=float)
        e2j = np.asarray(spice.pxform(EARTH_FRAME, "J2000", te_center), dtype=float)
        obs_ef = j2e @ (obs - earth_center)
        scaled = obs_ef / er
        dist = float(np.linalg.norm(scaled))
        if dist <= 1:
            raise RuntimeError("Observer inside Earth ellipsoid; frame/kernel mismatch.")
        axis = scaled / dist
        cc = axis / dist
        cr = math.sqrt(max(0.0, 1 - 1/(dist*dist)))
        helper = np.array([0., 0., 1.])
        if abs(float(np.dot(axis, helper))) > .9:
            helper = np.array([0., 1., 0.])
        u = unit(np.cross(axis, helper))
        v = unit(np.cross(axis, u))
        y = cc + cr * (u*math.cos(theta) + v*math.sin(theta))
        p_ef = y * er
        # Each limb point gets its own retarded time based on its observer distance.
        p_j = earth_center + e2j @ p_ef
        if correction != "NONE":
            te = et - float(np.linalg.norm(p_j - obs)) / C_KM_S
            for _ in range(12):
                rot_e2j = np.asarray(spice.pxform(EARTH_FRAME, "J2000", te), dtype=float)
                # Hold ellipsoid-fixed coordinates for the physical surface point.
                p_j = body_pos("EARTH", te) + rot_e2j @ p_ef
                new_te = et - float(np.linalg.norm(p_j - obs)) / C_KM_S
                if abs(new_te - te) < 1e-9:
                    te = new_te
                    break
                te = new_te
        direction = p_j - obs
        if correction == "LT+S":
            direction = np.asarray(spice.stelab(direction, vel), dtype=float)
        return elev(direction, up)

    # The tangent curve itself is defined using the center-retarded ellipsoid.
    # Per-point retarding is then applied to surface points; this is a diagnostic
    # approximation, not an exact apparent contour solution.
    grid = np.linspace(0, 2*math.pi, 720, endpoint=False)
    vals = np.array([point_el(float(t)) for t in grid])
    i = int(np.argmax(vals))
    step = 2*math.pi/720
    opt = minimize_scalar(lambda t: -point_el(float(t)), bounds=(grid[i]-step, grid[i]+step),
                          method="bounded", options={"xatol": 1e-10})
    if not opt.success:
        raise RuntimeError("Limb maximum optimization failed.")
    return -float(opt.fun)

def main():
    load_kernels()
    rows = []
    try:
        for utc, h_el, diameter in HORIZONS:
            et = float(spice.str2et(utc))
            radius_deg = diameter / 7200.0
            h_upper = h_el + radius_deg
            row = {
                "utc": utc,
                "horizons_center_elevation_deg": h_el,
                "horizons_diameter_arcsec": diameter,
                "horizons_upper_limb_estimate_deg": h_upper,
            }
            for mode in ("NONE", "LT", "LT+S"):
                center = apparent_center(et, mode)
                limb = max_limb_elevation(et, mode)
                row[f"spice_center_elevation_deg_{mode.lower().replace('+','_')}"] = center
                row[f"center_delta_arcsec_{mode.lower().replace('+','_')}"] = (center - h_el)*3600
                row[f"spice_limb_elevation_deg_{mode.lower().replace('+','_')}"] = limb
                row[f"limb_delta_arcsec_vs_horizons_estimate_{mode.lower().replace('+','_')}"] = (limb - h_upper)*3600
            rows.append(row)
            print(f"[{utc}] Horizons center={h_el:+.9f} deg; upper estimate={h_upper:+.9f} deg")
            print("  center delta arcsec: " + ", ".join(
                f"{m}={(row['center_delta_arcsec_'+m.lower().replace('+','_')]):+.3f}"
                for m in ("NONE", "LT", "LT+S")
            ))
            print("  limb delta arcsec:   " + ", ".join(
                f"{m}={(row['limb_delta_arcsec_vs_horizons_estimate_'+m.lower().replace('+','_')]):+.3f}"
                for m in ("NONE", "LT", "LT+S")
            ))
        out_csv = RESULTS_DIR / "matched_comparison.csv"
        with out_csv.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        out_txt = RESULTS_DIR / "matched_comparison_summary.txt"
        with out_txt.open("w", encoding="utf-8") as f:
            f.write("LunaSight — matched diagnostic comparison\n")
            f.write("========================================\n")
            f.write("Reference data: user-provided Horizons rows (not live-refetched).\n")
            f.write(f"Site: lon={SITE_LON_DEG} E, lat={SITE_LAT_DEG}, alt={SITE_ALT_KM} km\n")
            f.write(f"Moon frame: {MOON_FRAME}; Earth frame: {EARTH_FRAME}\n")
            f.write("Modes: NONE (geometric), LT (light-time), LT+S (light-time + stellar aberration)\n")
            f.write("Limb: ellipsoid tangent-locus approximation, with per-point retarded time and optional stellar aberration.\n")
            f.write("Caution: not a rigorous exact apparent-contour solver; compare modes and inspect residuals.\n\n")
            for row in rows:
                f.write(f"{row['utc']}\n")
                for mode in ("none", "lt", "lt_s"):
                    f.write(f"  center_delta_arcsec_{mode}: {row['center_delta_arcsec_'+mode]:+.6f}\n")
                    f.write(f"  limb_delta_arcsec_{mode}: {row['limb_delta_arcsec_vs_horizons_estimate_'+mode]:+.6f}\n")
        print(f"\n[OUTPUT] {out_csv}")
        print(f"[OUTPUT] {out_txt}")
        print("[IMPORTANT] This is diagnostic only; do not designate an event time as validated yet.")
    finally:
        spice.kclear()

if __name__ == "__main__":
    main()
