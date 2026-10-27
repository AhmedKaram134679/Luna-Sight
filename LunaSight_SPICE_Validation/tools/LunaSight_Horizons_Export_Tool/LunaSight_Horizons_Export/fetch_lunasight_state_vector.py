#!/usr/bin/env python3
"""Fetch a JPL Horizons observer ephemeris for the LunaSight lunar reference site.

Uses only Python's standard library. Run on a machine with internet access:
    py fetch_lunasight_state_vector.py

The script saves the complete raw Horizons response and the rows between $$SOE/$$EOE.
It deliberately preserves the original response for scientific auditability.
"""
from __future__ import annotations

import csv
import sys
import urllib.error
import urllib.parse
import truststore
truststore.inject_into_ssl()
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE_URL = "https://ssd.jpl.nasa.gov/api/horizons.api"
PARAMS = {
    "format": "text",
    "COMMAND": "'399'",                 # Earth center
    "OBJ_DATA": "'YES'",
    "MAKE_EPHEM": "'YES'",
    "EPHEM_TYPE": "'OBSERVER'",
    "CENTER": "'coord@301'",           # User-defined observer site on Moon (301)
    "COORD_TYPE": "'GEODETIC'",
    "SITE_COORD": "'200,-88.45,0'",     # East longitude, latitude, altitude km
    "START_TIME": "'2026-11-01 07:10'",
    "STOP_TIME": "'2026-11-01 08:10'",
    "STEP_SIZE": "'1 m'",
    "TIME_TYPE": "'UT'",
    "TIME_DIGITS": "'SECONDS'",
    "QUANTITIES": "'4,20,13'",          # Apparent AZ/EL, range/range-rate, angular diameter
    "RANGE_UNITS": "'KM'",
    "CSV_FORMAT": "'YES'",
    "APPARENT": "'AIRLESS'",
    "ELEV_CUT": "'-90'",
    "SKIP_DAYLT": "'NO'",
    "OBJ_DATA": "'YES'",
}


def main() -> int:
    out_dir = Path(__file__).resolve().parent
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    raw_path = out_dir / f"lunasight_horizons_raw_{stamp}.txt"
    csv_path = out_dir / f"lunasight_horizons_rows_{stamp}.csv"
    url = BASE_URL + "?" + urllib.parse.urlencode(PARAMS, safe="',:@")
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "LunaSight-Scientific-Validation/0.1 (JPL Horizons API client)"},
    )

    print("Requesting JPL Horizons observer ephemeris...")
    print("Target: Earth (399)")
    print("Observer: geodetic site at 200 E, -88.45, 0 km on Moon (301)")
    print("UTC interval: 2026-11-01 07:10 through 08:10; step 1 minute")
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            body = response.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print("ERROR: Could not reach JPL Horizons API from this computer.", file=sys.stderr)
        print(f"Details: {exc}", file=sys.stderr)
        print("Check internet access and retry. No data file has been fabricated.", file=sys.stderr)
        return 2

    raw_path.write_text(body, encoding="utf-8")
    if "API ERROR" in body or "INPUT ERROR" in body or "\"error\"" in body.lower():
        print(f"Horizons response may contain an error. Inspect: {raw_path}", file=sys.stderr)
        print(body[:3000], file=sys.stderr)
        return 3

    if "$$SOE" not in body or "$$EOE" not in body:
        print(f"Response saved but expected data markers were not found: {raw_path}", file=sys.stderr)
        print("Inspect the raw response before using any values.", file=sys.stderr)
        return 4

    data_block = body.split("$$SOE", 1)[1].split("$$EOE", 1)[0].strip()
    lines = [line for line in data_block.splitlines() if line.strip()]
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        for line in lines:
            writer.writerow(next(csv.reader([line])))

    print("SUCCESS: response retrieved from JPL Horizons.")
    print(f"Raw response: {raw_path}")
    print(f"Data rows:    {csv_path}")
    print(f"Rows found:   {len(lines)}")
    print("Review the raw header to confirm the observer coordinates, time scale, and model details.")
    print("Do not treat this as an exact reproduction of another software's MOON_ME model unless frames and corrections are reconciled.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
