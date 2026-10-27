#!/usr/bin/env python3
"""Fetch a 1-second JPL Horizons observer ephemeris around a LunaSight event.

Uses Windows' trusted certificate store through truststore while retaining TLS
certificate verification. Requires: py -m pip install truststore
Run: py .\\fetch_lunasight_event_window.py
"""
from __future__ import annotations

# Inject Windows trust store BEFORE importing urllib.request / SSL consumers.
import truststore
truststore.inject_into_ssl()

import csv
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE_URL = "https://ssd.jpl.nasa.gov/api/horizons.api"
PARAMS = {
    "format": "text",
    "COMMAND": "'399'",
    "OBJ_DATA": "'YES'",
    "MAKE_EPHEM": "'YES'",
    "EPHEM_TYPE": "'OBSERVER'",
    "CENTER": "'coord@301'",
    "COORD_TYPE": "'GEODETIC'",
    "SITE_COORD": "'200,-88.45,0'",
    "START_TIME": "'2026-11-01 07:40:00'",
    "STOP_TIME": "'2026-11-01 07:41:00'",
    "STEP_SIZE": "'60'",
    "TIME_TYPE": "'UT'",
    "TIME_DIGITS": "'SECONDS'",
    "QUANTITIES": "'4,20,13'",
    "RANGE_UNITS": "'KM'",
    "CSV_FORMAT": "'YES'",
    "APPARENT": "'AIRLESS'",
    "ELEV_CUT": "'-90'",
    "SKIP_DAYLT": "'NO'",
}


def main() -> int:
    out_dir = Path(__file__).resolve().parent
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    raw_path = out_dir / f"lunasight_event_raw_{stamp}.txt"
    csv_path = out_dir / f"lunasight_event_rows_{stamp}.csv"
    url = BASE_URL + "?" + urllib.parse.urlencode(PARAMS, safe="',:@")
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "LunaSight-Scientific-Validation/0.2 (JPL Horizons API client)"},
    )

    print("Requesting JPL Horizons observer ephemeris at 1-second cadence (unitless STEP_SIZE=60)...")
    print("Target: Earth (399); observer: 200 E, -88.45 deg, 0 km on Moon (301)")
    print("UTC interval: 2026-11-01 07:40:00 through 07:41:00; step 1 second")
    print("TLS verification remains enabled; truststore uses the Windows trust store.")
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            body = response.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print("ERROR: Could not retrieve the JPL Horizons response.", file=sys.stderr)
        print(f"Details: {exc}", file=sys.stderr)
        print("No data file has been fabricated.", file=sys.stderr)
        return 2

    raw_path.write_text(body, encoding="utf-8")
    if "API ERROR" in body or "INPUT ERROR" in body or '"error"' in body.lower():
        print(f"Horizons returned a possible API/input error. Inspect: {raw_path}", file=sys.stderr)
        print(body[:3000], file=sys.stderr)
        return 3
    if "$$SOE" not in body or "$$EOE" not in body:
        print(f"Expected $$SOE/$$EOE markers missing. Raw response saved: {raw_path}", file=sys.stderr)
        print(body[:3000], file=sys.stderr)
        return 4

    block = body.split("$$SOE", 1)[1].split("$$EOE", 1)[0]
    lines = [line for line in block.splitlines() if line.strip()]
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow([
            "time_utc", "solar_presence", "interfering_body_presence",
            "azimuth_apparent_deg", "elevation_apparent_deg", "range_km",
            "range_rate_km_s", "angular_diameter_arcsec",
        ])
        for line in lines:
            fields = next(csv.reader([line]))
            # Horizons output has an empty field after the timestamp in this layout.
            fields = [value.strip() for value in fields]
            if len(fields) >= 9:
                fields = [fields[0], *fields[2:9]]
            writer.writerow(fields)

    print("SUCCESS: response retrieved from JPL Horizons.")
    print(f"Raw response: {raw_path}")
    print(f"Data rows:    {csv_path}")
    print(f"Rows found:   {len(lines)} (expected 61 inclusive samples)")
    print("Verify the raw header and row count before scientific use.")
    print("The 1-second cadence narrows event timing but does not alone guarantee a 1-second physical accuracy.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
