"""Download a matched-window JPL Horizons observer table for LunaSight.

This captures Earth as seen from the user-defined lunar surface site:
longitude 200 deg east, latitude -88.45 deg, altitude 0 km.
It saves the raw JSON response, plain-text result, and parsed CSV rows.

Official API documentation:
https://ssd-api.jpl.nasa.gov/doc/horizons.html

Important:
- This is an observer-table reference for Earth center observables (azimuth,
  elevation, angular diameter, range, and one-way light time).
- It does NOT directly provide the modeled ellipsoid upper-limb elevation.
  The limb must be derived separately using a declared shape/limb model.
- Confirm the response header identifies the intended observer site and time
  settings before using it as a reference.
"""
from __future__ import annotations

import csv
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
OUT = BASE / "horizons_results"
OUT.mkdir(parents=True, exist_ok=True)

API = "https://ssd.jpl.nasa.gov/api/horizons.api"
START = "2026-11-02 14:12:30"
STOP = "2026-11-02 14:16:00"
STEP_INTERVALS = 210  # 210 seconds / 210 intervals = one-second samples

PARAMS = {
    "format": "json",
    "COMMAND": "'399'",
    "OBJ_DATA": "'YES'",
    "MAKE_EPHEM": "'YES'",
    "EPHEM_TYPE": "'OBSERVER'",
    "CENTER": "'coord@301'",
    "COORD_TYPE": "'GEODETIC'",
    "SITE_COORD": "'200,-88.45,0'",
    "START_TIME": f"'{START}'",
    "STOP_TIME": f"'{STOP}'",
    "STEP_SIZE": f"'{STEP_INTERVALS}'",
    "TIME_TYPE": "'UT'",
    "TIME_DIGITS": "'SECONDS'",
    "QUANTITIES": "'4,13,20,21'",
    "APPARENT": "'AIRLESS'",
    "RANGE_UNITS": "'KM'",
    "CSV_FORMAT": "'YES'",
    "EXTRA_PREC": "'YES'",
    "SKIP_DAYLT": "'NO'",
    "ELEV_CUT": "'-90'",
}

def request_horizons() -> dict:
    query = urllib.parse.urlencode(PARAMS, safe="'@,:+-")
    url = f"{API}?{query}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "LunaSight-Scientific-Validation/1.0"},
    )
    with urllib.request.urlopen(req, timeout=120) as response:
        raw = response.read().decode("utf-8", errors="replace")
    stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    raw_path = OUT / f"horizons_raw_{stamp}.json"
    raw_path.write_text(raw, encoding="utf-8")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Horizons response was not valid JSON. Raw response saved to {raw_path}"
        ) from exc
    if payload.get("error"):
        raise RuntimeError(
            f"Horizons API error: {payload['error']}. Raw response: {raw_path}"
        )
    result = payload.get("result", "")
    if "$$SOE" not in result or "$$EOE" not in result:
        raise RuntimeError(
            "Horizons response did not contain $$SOE/$$EOE ephemeris markers. "
            f"Inspect {raw_path}; check whether CENTER/SITE_COORD were accepted."
        )
    text_path = OUT / f"horizons_result_{stamp}.txt"
    text_path.write_text(result, encoding="utf-8")
    rows = parse_result(result)
    csv_path = OUT / f"horizons_rows_{stamp}.csv"
    if not rows:
        raise RuntimeError(
            f"No ephemeris rows could be parsed. Raw response saved to {raw_path}; "
            f"result saved to {text_path}."
        )
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"[OK] Raw JSON: {raw_path}")
    print(f"[OK] Horizons result: {text_path}")
    print(f"[OK] Parsed CSV: {csv_path}")
    print(f"[OK] Parsed rows: {len(rows)}")
    print("Inspect the saved result header to confirm site, quantities, time scale, and step.")
    print("This table is not itself an upper-limb event solution.")
    return payload

def parse_result(result: str) -> list[dict[str, str]]:
    block = result.split("$$SOE", 1)[1].split("$$EOE", 1)[0]
    rows: list[dict[str, str]] = []
    for line in block.splitlines():
        line = line.strip()
        if not line:
            continue
        # Horizons CSV lines usually have the date as the first field, followed by
        # a record marker and quantity fields. Keep original columns until headers
        # are confirmed from the response metadata.
        fields = next(csv.reader([line], skipinitialspace=True))
        rows.append({f"field_{i+1}": value.strip() for i, value in enumerate(fields)})
    return rows

if __name__ == "__main__":
    try:
        request_horizons()
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)
