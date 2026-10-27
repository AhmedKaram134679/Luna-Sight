#!/usr/bin/env python3
"""Fetch a wide JPL Horizons window and refine Earth limb/horizon crossings.

Windows prerequisite: py -m pip install truststore
Run: py .\\fetch_lunasight_limb_events.py
"""
from __future__ import annotations

import truststore
truststore.inject_into_ssl()

import csv
import io
import math
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE_URL = "https://ssd.jpl.nasa.gov/api/horizons.api"
COMMON = {
    "format": "text",
    "COMMAND": "'399'",
    "OBJ_DATA": "'YES'",
    "MAKE_EPHEM": "'YES'",
    "EPHEM_TYPE": "'OBSERVER'",
    "CENTER": "'coord@301'",
    "COORD_TYPE": "'GEODETIC'",
    "SITE_COORD": "'200,-88.45,0'",
    "TIME_TYPE": "'UT'",
    "TIME_DIGITS": "'SECONDS'",
    "QUANTITIES": "'4,20,13'",
    "RANGE_UNITS": "'KM'",
    "CSV_FORMAT": "'YES'",
    "APPARENT": "'AIRLESS'",
    "ELEV_CUT": "'-90'",
    "SKIP_DAYLT": "'NO'",
}
COARSE_START = datetime(2026, 11, 1, 7, 30, 0)
COARSE_STOP = datetime(2026, 11, 3, 7, 30, 0)  # 48 hours, inclusive


def fmt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def fetch(start: datetime, stop: datetime, step: str, label: str, out_dir: Path) -> tuple[str, list[dict[str, str]]]:
    params = dict(COMMON)
    params.update({
        "START_TIME": "'" + fmt(start) + "'",
        "STOP_TIME": "'" + fmt(stop) + "'",
        "STEP_SIZE": "'" + step + "'",
    })
    url = BASE_URL + "?" + urllib.parse.urlencode(params, safe="',:@")
    request = urllib.request.Request(url, headers={"User-Agent": "LunaSight-Scientific-Validation/0.3"})
    print(f"Requesting {label}: {fmt(start)} to {fmt(stop)} UTC, step={step}")
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            body = response.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"Request failed ({label}): {exc}") from exc

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    raw_path = out_dir / f"{label}_raw_{stamp}.txt"
    raw_path.write_text(body, encoding="utf-8")
    if "$$SOE" not in body or "$$EOE" not in body or "API ERROR" in body or "INPUT ERROR" in body:
        raise RuntimeError(f"Unexpected Horizons response for {label}. Raw response saved: {raw_path}\n" + body[:2500])

    block = body.split("$$SOE", 1)[1].split("$$EOE", 1)[0]
    records: list[dict[str, str]] = []
    for line in block.splitlines():
        if not line.strip():
            continue
        fields = [v.strip() for v in next(csv.reader([line]))]
        # Horizons observer CSV is timestamp, solar marker, interfering-body marker,
        # azimuth, elevation, range, range-rate, angular diameter.
        if len(fields) < 8:
            raise RuntimeError(f"Malformed data row ({len(fields)} fields) in {raw_path}: {line}")
        timestamp = fields[0]
        try:
            # Horizons may omit seconds entirely for coarse cadences even when
            # TIME_DIGITS=SECONDS is requested. Accept both valid timestamp forms.
            dt = None
            for time_format in (
                "%Y-%b-%d %H:%M:%S.%f",
                "%Y-%b-%d %H:%M:%S",
                "%Y-%b-%d %H:%M",
            ):
                try:
                    dt = datetime.strptime(timestamp, time_format)
                    break
                except ValueError:
                    continue
            if dt is None:
                raise ValueError(f"Unsupported Horizons timestamp format: {timestamp!r}")
            az, elev, rng, rate, diam = map(float, fields[3:8])
        except (ValueError, IndexError) as exc:
            raise RuntimeError(f"Could not parse Horizons row in {raw_path}: {line}") from exc
        records.append({
            "time_utc": dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            "solar_presence": fields[1],
            "interfering_body_presence": fields[2],
            "azimuth_apparent_deg": f"{az:.9f}",
            "elevation_apparent_deg": f"{elev:.9f}",
            "range_km": f"{rng:.7f}",
            "range_rate_km_s": f"{rate:.7f}",
            "angular_diameter_arcsec": f"{diam:.6f}",
        })

    csv_path = out_dir / f"{label}_rows_{stamp}.csv"
    cols = ["time_utc", "solar_presence", "interfering_body_presence", "azimuth_apparent_deg", "elevation_apparent_deg", "range_km", "range_rate_km_s", "angular_diameter_arcsec"]
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=cols)
        writer.writeheader()
        writer.writerows(records)
    print(f"  Raw: {raw_path}")
    print(f"  CSV: {csv_path}")
    print(f"  Rows parsed: {len(records)}")
    return body, records


def limb_heights(row: dict[str, str]) -> tuple[float, float]:
    center = float(row["elevation_apparent_deg"])
    radius = float(row["angular_diameter_arcsec"]) / 7200.0
    return center - radius, center + radius  # lower and upper limb, respectively


def crossing_brackets(rows: list[dict[str, str]]) -> dict[str, tuple[datetime, datetime]]:
    found: dict[str, tuple[datetime, datetime]] = {}
    previous = None
    for row in rows:
        dt = datetime.fromisoformat(row["time_utc"])
        lower, upper = limb_heights(row)
        current = {"lower_limb": lower, "upper_limb": upper}
        if previous:
            for key in current:
                a, b = previous[1][key], current[key]
                if a == 0 or a * b < 0:
                    # Keep the first crossing of each type in this 48-hour window.
                    if key not in found:
                        found[key] = (previous[0], dt)
        previous = (dt, current)
    return found


def main() -> int:
    out_dir = Path(__file__).resolve().parent
    print("LunaSight / JPL Horizons — Earth disk limb event finder")
    print("Target Earth (399); observer Moon (301), 200 E, -88.45 deg, 0 km")
    print("Important: this tool calculates geometric limb-height crossings from Horizons center elevation and angular diameter.")
    print("It does not model local terrain, rocks, or an irregular lunar horizon.\n")
    try:
        _, coarse = fetch(COARSE_START, COARSE_STOP, "1 m", "lunasight_48h_coarse", out_dir)
        expected = 48 * 60 + 1
        print(f"Coarse-window row count: {len(coarse)} (expected {expected} for 1-minute cadence)")
        if len(coarse) < 100:
            raise RuntimeError("Too few samples in coarse response; refusing to infer event times.")
        brackets = crossing_brackets(coarse)
        if not brackets:
            print("No limb/horizon crossing bracket was found in this 48-hour interval.")
            print("Do not extrapolate. Widen the interval and rerun.")
            return 5

        print("\nCoarse crossing brackets (UTC):")
        for key, (a, b) in brackets.items():
            print(f"  {key}: {a.isoformat()} to {b.isoformat()}")

        for key, (a, b) in brackets.items():
            # Request a 1-second grid across the exact bracketing minute.
            minute_start = a.replace(second=0, microsecond=0)
            minute_stop = minute_start + timedelta(minutes=1)
            _, fine = fetch(minute_start, minute_stop, "60", f"lunasight_{key}_1sec", out_dir)
            if len(fine) != 61:
                print(f"WARNING: expected 61 one-second samples for {key}, got {len(fine)}")
            values = [(datetime.fromisoformat(r["time_utc"]), limb_heights(r)[0 if key == "lower_limb" else 1]) for r in fine]
            bracket = None
            for i in range(1, len(values)):
                if values[i-1][1] == 0 or values[i-1][1] * values[i][1] < 0:
                    bracket = (values[i-1], values[i])
                    break
            print(f"\nFine result — {key}:")
            if not bracket:
                print("  No sign change in the 1-second window; retain only the coarse bracket and investigate settings/data.")
                continue
            (t0, h0), (t1, h1) = bracket
            # Linear interpolation between adjacent one-second Horizons samples.
            fraction = -h0 / (h1 - h0) if h1 != h0 else math.nan
            estimate = t0 + (t1 - t0) * fraction
            print(f"  Last sample on first side: {t0.isoformat()} limb_height={h0:+.10f} deg")
            print(f"  First sample on other side: {t1.isoformat()} limb_height={h1:+.10f} deg")
            print(f"  Linear interpolation estimate: {estimate.isoformat(timespec='milliseconds')} UTC")
            print("  This is an interpolation estimate, not a claim of millisecond physical accuracy.")

        print("\nCheck each raw response header and CSV before accepting the result. No crossing is reported unless a sign change is bracketed in the returned samples.")
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
