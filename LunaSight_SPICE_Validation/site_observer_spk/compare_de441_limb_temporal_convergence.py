"""Compare complete 5-second and sharded 1-second DE441 limb sweeps.

Shard boundaries intentionally overlap by one epoch. Duplicate rows are
compared numerically under explicit, field-specific tolerances; the first row
is retained only after every compared field passes.
"""
from __future__ import annotations

import argparse
import csv
import glob
import math
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
from scipy.optimize import linear_sum_assignment

REQUIRED_COLUMNS = {
    "utc", "azimuth_index", "h",
    "tangency_residual", "surface_residual", "independent_reference_error",
    "point_fixed_x_km", "point_fixed_y_km", "point_fixed_z_km",
    "source_dir_x", "source_dir_y", "source_dir_z",
    "observer_dir_x", "observer_dir_y", "observer_dir_z",
}
EXPECTED_START = datetime.fromisoformat("2026-11-02T14:12:00")
EXPECTED_DURATION_SECONDS = 240
BRANCH_COUNT = 96

# These are overlap-consistency tolerances, not scientific convergence limits.
# They are deliberately field-specific and are checked only between duplicate
# rows produced independently by adjacent shards.
OVERLAP_TOLERANCES = {
    "h": 1.0e-12,
    "tangency_residual": 1.0e-12,
    "surface_residual": 1.0e-12,
    "independent_reference_error": 1.0e-18,
    "point_fixed_x_km": 1.0e-8,
    "point_fixed_y_km": 1.0e-8,
    "point_fixed_z_km": 1.0e-8,
    "source_dir_x": 1.0e-12,
    "source_dir_y": 1.0e-12,
    "source_dir_z": 1.0e-12,
    "observer_dir_x": 1.0e-12,
    "observer_dir_y": 1.0e-12,
    "observer_dir_z": 1.0e-12,
}


def vector(row: dict[str, str], prefix: str) -> np.ndarray:
    suffix = "_km" if prefix == "point_fixed" else ""
    return np.array([float(row[f"{prefix}_{axis}{suffix}"]) for axis in "xyz"], dtype=float)


def angular_difference(a: np.ndarray, b: np.ndarray) -> float:
    a = a / np.linalg.norm(a)
    b = b / np.linalg.norm(b)
    return float(np.arctan2(np.linalg.norm(np.cross(a, b)), np.clip(np.dot(a, b), -1.0, 1.0)))


def read_csv(path: Path) -> dict[tuple[str, int], dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or ())
        if missing:
            raise AssertionError(f"{path}: missing required CSV columns: {sorted(missing)}")
        result = {}
        for row in reader:
            key = (row["utc"], int(row["azimuth_index"]))
            if key in result:
                raise AssertionError(f"{path}: duplicate epoch/branch row {key}")
            result[key] = row
        return result


def merge_fine(paths: list[Path]) -> tuple[dict, dict]:
    if len(paths) != 4:
        raise AssertionError(f"Expected exactly four 1-second shard CSVs; found {len(paths)}")
    merged: dict[tuple[str, int], dict[str, str]] = {}
    overlap_max = {column: 0.0 for column in OVERLAP_TOLERANCES}
    overlap_count = 0
    for path in sorted(paths):
        shard = read_csv(path)
        if not shard:
            raise AssertionError(f"{path}: empty shard")
        for key, row in shard.items():
            if key not in merged:
                merged[key] = row
                continue
            previous = merged[key]
            failures = []
            for column, tolerance in OVERLAP_TOLERANCES.items():
                try:
                    left, right = float(previous[column]), float(row[column])
                except (KeyError, TypeError, ValueError) as exc:
                    raise AssertionError(f"Overlap {key}: invalid numeric field {column}") from exc
                if not (math.isfinite(left) and math.isfinite(right)):
                    raise AssertionError(f"Overlap {key}: non-finite value in {column}")
                delta = abs(left - right)
                overlap_max[column] = max(overlap_max[column], delta)
                if delta > tolerance:
                    failures.append(f"{column}: delta={delta:.17g} tolerance={tolerance:.17g}")
            if failures:
                raise AssertionError(f"Overlapping shard geometry disagrees at {key}: " + "; ".join(failures))
            overlap_count += 1
            # Retain the first copy only after the duplicate has passed validation.
    return merged, {
        "duplicate_branch_rows": overlap_count,
        **{f"max_abs_delta_{key}": value for key, value in overlap_max.items()},
    }


def validate_grid(data: dict[tuple[str, int], dict[str, str]], step: int, label: str) -> None:
    expected_epochs = {
        (EXPECTED_START + timedelta(seconds=offset)).isoformat(timespec="milliseconds")
        for offset in range(0, EXPECTED_DURATION_SECONDS + 1, step)
    }
    actual_epochs = {utc for utc, _ in data}
    if actual_epochs != expected_epochs:
        missing = sorted(expected_epochs - actual_epochs)[:5]
        extra = sorted(actual_epochs - expected_epochs)[:5]
        raise AssertionError(f"{label}: epoch coverage mismatch; missing={missing}, extra={extra}")
    expected_indices = set(range(BRANCH_COUNT))
    for utc in sorted(expected_epochs):
        actual = {index for epoch, index in data if epoch == utc}
        if actual != expected_indices:
            raise AssertionError(f"{label}: incomplete branch set at {utc}: {sorted(actual)}")


def compare(coarse_path: Path, fine_paths: list[Path], output: Path) -> None:
    coarse = read_csv(coarse_path)
    fine, overlap_report = merge_fine(fine_paths)
    validate_grid(coarse, 5, "5-second reference")
    validate_grid(fine, 1, "1-second merged shards")

    coarse_epochs = defaultdict(dict)
    fine_epochs = defaultdict(dict)
    for (utc, index), row in coarse.items():
        coarse_epochs[utc][index] = row
    for (utc, index), row in fine.items():
        fine_epochs[utc][index] = row

    common = sorted(set(coarse_epochs) & set(fine_epochs))
    rows = []
    max_direct_point = max_direct_source = max_direct_observer = max_abs_h = 0.0
    max_nearest_point = 0.0
    identity_mismatches = 0

    for utc in common:
        c, f = coarse_epochs[utc], fine_epochs[utc]
        indices = sorted(range(BRANCH_COUNT))
        cp = np.array([vector(c[i], "point_fixed") for i in indices])
        fp = np.array([vector(f[i], "point_fixed") for i in indices])
        cost = np.linalg.norm(cp[:, None, :] - fp[None, :, :], axis=2)
        rr, cc = linear_sum_assignment(cost)
        max_nearest_point = max(max_nearest_point, float(np.max(cost[rr, cc])))
        identity_mismatches += int(np.count_nonzero(rr != cc))
        nearest_for_coarse = {int(r): int(col) for r, col in zip(rr, cc)}

        for i in indices:
            cr, fr = c[i], f[i]
            point_delta = float(np.linalg.norm(vector(cr, "point_fixed") - vector(fr, "point_fixed")))
            source_delta = angular_difference(vector(cr, "source_dir"), vector(fr, "source_dir"))
            observer_delta = angular_difference(vector(cr, "observer_dir"), vector(fr, "observer_dir"))
            h_delta = abs(float(cr["h"]) - float(fr["h"]))
            max_direct_point = max(max_direct_point, point_delta)
            max_direct_source = max(max_direct_source, source_delta)
            max_direct_observer = max(max_direct_observer, observer_delta)
            max_abs_h = max(max_abs_h, h_delta)
            mapped = nearest_for_coarse[i]
            rows.append((utc, i, point_delta, source_delta, observer_delta, h_delta,
                         int(mapped != i), float(cost[i, mapped])))

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(("utc", "azimuth_index", "earth_fixed_contact_delta_km",
                         "source_direction_delta_rad", "observer_direction_delta_rad",
                         "tangent_parameter_abs_delta", "nearest_assignment_index_changed",
                         "nearest_assigned_contact_distance_km"))
        writer.writerows(rows)

    overlap_path = output.with_name(output.stem + "_overlap_report.csv")
    with overlap_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(("metric", "max_abs_delta", "absolute_tolerance"))
        writer.writerow(("duplicate_branch_rows", overlap_report["duplicate_branch_rows"], ""))
        for column, tolerance in OVERLAP_TOLERANCES.items():
            writer.writerow((column, overlap_report[f"max_abs_delta_{column}"], tolerance))

    print("phase=DE441_LIMB_TEMPORAL_RESOLUTION_CONVERGENCE")
    print("coarse_step_seconds=5")
    print("fine_step_seconds=1")
    print(f"coarse_epoch_count={len(coarse_epochs)}")
    print(f"fine_epoch_count={len(fine_epochs)}")
    print(f"fine_shard_count={len(fine_paths)}")
    print(f"common_epoch_count={len(common)}")
    print(f"common_branch_comparison_count={len(rows)}")
    print(f"max_direct_index_contact_delta_km={max_direct_point:.12g}")
    print(f"max_nearest_assigned_contact_distance_km={max_nearest_point:.12g}")
    print(f"max_direct_index_source_direction_delta_rad={max_direct_source:.12g}")
    print(f"max_direct_index_observer_direction_delta_rad={max_direct_observer:.12g}")
    print(f"max_tangent_parameter_abs_delta={max_abs_h:.12g}")
    print(f"nearest_assignment_nonidentity_count={identity_mismatches}")
    print(f"shard_overlap_duplicate_rows={overlap_report['duplicate_branch_rows']}")
    for column in OVERLAP_TOLERANCES:
        print(f"shard_overlap_max_abs_delta_{column}={overlap_report[f'max_abs_delta_{column}']:.12g}")
    print("shard_overlap_validation=PASS")
    print("complete_one_second_epoch_and_branch_coverage=PASS")
    print("direct_index_branch_correspondence=REPORTED")
    print("nearest_assignment_is_diagnostic_not_relabeling=YES")
    print("overlap_tolerances=EXPLICIT_FIELD_SPECIFIC_ABSOLUTE")
    print(f"comparison_csv={output}")
    print(f"overlap_report_csv={overlap_path}")
    print("status=PASS")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--coarse", type=Path, default=Path("de441_limb_continuity_5s.csv"))
    parser.add_argument("--fine-glob", default="de441_limb_continuity_1s_shard_*.csv")
    parser.add_argument("--output", type=Path, default=Path("de441_limb_convergence_comparison.csv"))
    args = parser.parse_args()
    paths = [Path(item) for item in sorted(glob.glob(args.fine_glob))]
    compare(args.coarse, paths, args.output)


if __name__ == "__main__":
    main()
