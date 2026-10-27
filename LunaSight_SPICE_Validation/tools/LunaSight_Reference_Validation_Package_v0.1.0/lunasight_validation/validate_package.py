#!/usr/bin/env python3
"""Offline sanity checks for the supplied LunaSight Horizons exports.

This script does not calculate or certify the final Earth-limb event time.
It verifies input presence, parses the Angular Size series, and checks a
simple angular-diameter magnitude against a spherical approximation.
Run: python validate_package.py
"""
from pathlib import Path
import re, math, json, hashlib

BASE = Path(__file__).resolve().parent
RAW = BASE / "raw_sources"
ANGULAR_FILE = RAW / "New Text Document(1).txt"
STATE_FILE = RAW / "نص ملصق (3).txt"
RANGE_FILE = RAW / "نص ملصق(6).txt"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def angular_samples(text: str):
    # Match rows formatted as YYYY-MM-DD hh:mm:ss.ffffff UTC followed by a
    # numeric angular size on the next non-empty line.
    lines = [x.strip() for x in text.splitlines()]
    out = {}
    for i, line in enumerate(lines):
        if re.fullmatch(r"2026-11-\d{2} \d{2}:\d{2}:\d{2}\.\d+ UTC", line):
            for nxt in lines[i+1:i+4]:
                try:
                    value = float(nxt)
                    out[line.replace('.000000','')] = value
                    break
                except ValueError:
                    continue
    return out


def main():
    missing = [str(p) for p in (ANGULAR_FILE, STATE_FILE, RANGE_FILE) if not p.exists()]
    if missing:
        raise SystemExit("FAIL: missing source files: " + ", ".join(missing))
    angular_text = ANGULAR_FILE.read_text(encoding='utf-8-sig', errors='replace')
    state_text = STATE_FILE.read_text(encoding='utf-8-sig', errors='replace')
    range_text = RANGE_FILE.read_text(encoding='utf-8-sig', errors='replace')
    samples = angular_samples(angular_text)
    key = '2026-11-01 07:40:00 UTC'
    if key not in samples:
        raise SystemExit(f"FAIL: required angular sample not found: {key}")
    value = samples[key]
    # Sanity-only approximation, not a matched high-precision reference.
    earth_equatorial_radius_km = 6378.137
    representative_range_km = 370911.80881
    predicted_diameter_deg = 2.0 * math.degrees(math.asin(earth_equatorial_radius_km / representative_range_km))
    delta = abs(value - predicted_diameter_deg)
    checks = {
        "source_files_present": True,
        "angular_sample_count": len(samples),
        "angular_value_at_2026_11_01_0740_deg": value,
        "spherical_sanity_diameter_deg": round(predicted_diameter_deg, 8),
        "absolute_difference_deg_sanity_only": round(delta, 8),
        "angular_export_kernel_v0070": 'solar_system_v0070.tm' in angular_text,
        "fixed_point_state_metadata_present": 'Observer type' in state_text and 'Fixed point' in state_text and 'MOON_ME' in state_text,
        "range_export_kernel_v0071": 'solar_system_v0071.tm' in range_text,
        "validation_status": "UNVERIFIED — model semantics and matched event data are still required",
        "source_sha256": {
            p.name: sha256(p) for p in (ANGULAR_FILE, STATE_FILE, RANGE_FILE)
        }
    }
    # This test is intentionally a diagnostic, not a scientific pass/fail on event time.
    if not checks['angular_export_kernel_v0070']:
        raise SystemExit('FAIL: expected v0070 kernel metadata not found in Angular Size export')
    if not checks['fixed_point_state_metadata_present']:
        raise SystemExit('FAIL: expected fixed-point observer metadata not found')
    if not checks['range_export_kernel_v0071']:
        raise SystemExit('FAIL: expected v0071 kernel metadata not found in range export')
    (BASE / 'validation_run.json').write_text(json.dumps(checks, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(checks, indent=2, ensure_ascii=False))
    print("\nPASS: package integrity and diagnostic checks completed.")
    print("NOT A PASS: final Earth-limb event time remains unverified.")

if __name__ == '__main__':
    main()
