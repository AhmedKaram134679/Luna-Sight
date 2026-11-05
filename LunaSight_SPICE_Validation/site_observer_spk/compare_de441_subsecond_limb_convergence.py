"""Compare complete 1s, 0.5s, and 0.25s DE441 limb sweeps.

Only common epochs are compared. Direct transported branch indices are primary;
Hungarian nearest-point assignment is diagnostic and never relabels branches.
The report measures sampled resolution stability, not continuous-time proof.
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

START = datetime.fromisoformat("2026-11-02T14:12:00")
DURATION = 240
BRANCHES = 96
REQUIRED = {
    "utc", "azimuth_index", "h", "tangency_residual", "surface_residual",
    "independent_reference_error", "point_fixed_x_km", "point_fixed_y_km",
    "point_fixed_z_km", "source_dir_x", "source_dir_y", "source_dir_z",
    "observer_dir_x", "observer_dir_y", "observer_dir_z",
}
OVERLAP_TOLERANCES = {
    "h": 1e-12, "tangency_residual": 1e-12, "surface_residual": 1e-12,
    "independent_reference_error": 1e-18,
    "point_fixed_x_km": 1e-8, "point_fixed_y_km": 1e-8, "point_fixed_z_km": 1e-8,
    "source_dir_x": 1e-12, "source_dir_y": 1e-12, "source_dir_z": 1e-12,
    "observer_dir_x": 1e-12, "observer_dir_y": 1e-12, "observer_dir_z": 1e-12,
}


def read(path: Path) -> dict:
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        missing = REQUIRED - set(reader.fieldnames or ())
        if missing:
            raise AssertionError(f"{path}: missing columns {sorted(missing)}")
        rows = {}
        for row in reader:
            key = (row["utc"], int(row["azimuth_index"]))
            if key in rows:
                raise AssertionError(f"{path}: duplicate row {key}")
            for name in REQUIRED - {"utc", "azimuth_index"}:
                value = float(row[name])
                if not math.isfinite(value):
                    raise AssertionError(f"{path}: non-finite {name} at {key}")
            rows[key] = row
        if not rows:
            raise AssertionError(f"{path}: empty data")
        return rows


def merge_shards(paths: list[Path], expected_count: int, label: str) -> tuple[dict, int]:
    if len(paths) != 4:
        raise AssertionError(f"{label}: expected 4 shard files, got {len(paths)}")
    merged, overlaps = {}, 0
    for path in sorted(paths):
        for key, row in read(path).items():
            old = merged.get(key)
            if old is None:
                merged[key] = row
                continue
            for column, tolerance in OVERLAP_TOLERANCES.items():
                delta = abs(float(old[column]) - float(row[column]))
                if delta > tolerance:
                    raise AssertionError(f"{label}: overlap mismatch {key} {column}={delta} > {tolerance}")
            overlaps += 1
    if len(merged) == 0:
        raise AssertionError(f"{label}: no merged rows")
    return merged, overlaps


def validate_grid(data: dict, step: float, label: str) -> int:
    count = round(DURATION / step) + 1
    expected = {
        (START + timedelta(seconds=i * step)).isoformat(timespec="milliseconds")
        for i in range(count)
    }
    actual = {utc for utc, _ in data}
    if actual != expected:
        raise AssertionError(
            f"{label}: epoch grid mismatch; expected={len(expected)} actual={len(actual)} "
            f"missing={sorted(expected-actual)[:3]} extra={sorted(actual-expected)[:3]}"
        )
    branches = set(range(BRANCHES))
    for utc in expected:
        found = {branch for epoch, branch in data if epoch == utc}
        if found != branches:
            raise AssertionError(f"{label}: branch coverage failure at {utc}")
    return len(expected)


def vec(row: dict, prefix: str) -> np.ndarray:
    suffix = "_km" if prefix == "point_fixed" else ""
    value = np.array([float(row[f"{prefix}_{axis}{suffix}"]) for axis in "xyz"])
    return value


def angle(a: np.ndarray, b: np.ndarray) -> float:
    a = a / np.linalg.norm(a)
    b = b / np.linalg.norm(b)
    return float(np.arctan2(np.linalg.norm(np.cross(a, b)), np.clip(np.dot(a, b), -1.0, 1.0)))


def compare_pair(coarse: dict, fine: dict, label: str) -> dict:
    coarse_epochs, fine_epochs = defaultdict(dict), defaultdict(dict)
    for (utc, branch), row in coarse.items():
        coarse_epochs[utc][branch] = row
    for (utc, branch), row in fine.items():
        fine_epochs[utc][branch] = row
    common = sorted(set(coarse_epochs) & set(fine_epochs))
    expected_common = round(DURATION / (2 if label == "1s_vs_0.5s" else 4)) + 1
    if len(common) != expected_common:
        raise AssertionError(f"{label}: expected {expected_common} common epochs, got {len(common)}")
    point_deltas, source_deltas, observer_deltas = [], [], []
    h_deltas, assignment_changes = [], 0
    detail = []
    for utc in common:
        c, f = coarse_epochs[utc], fine_epochs[utc]
        cp = np.array([vec(c[i], "point_fixed") for i in range(BRANCHES)])
        fp = np.array([vec(f[i], "point_fixed") for i in range(BRANCHES)])
        cost = np.linalg.norm(cp[:, None, :] - fp[None, :, :], axis=2)
        rr, cc = linear_sum_assignment(cost)
        assignment_changes += int(np.count_nonzero(rr != cc))
        for i in range(BRANCHES):
            pd = float(np.linalg.norm(vec(c[i], "point_fixed") - vec(f[i], "point_fixed")))
            sd = angle(vec(c[i], "source_dir"), vec(f[i], "source_dir"))
            od = angle(vec(c[i], "observer_dir"), vec(f[i], "observer_dir"))
            hd = abs(float(c[i]["h"]) - float(f[i]["h"]))
            point_deltas.append(pd); source_deltas.append(sd); observer_deltas.append(od); h_deltas.append(hd)
            detail.append((label, utc, i, pd, sd, od, hd, int(rr[i] != cc[i]), float(cost[i, cc[i]])))
    def stats(values):
        a = np.asarray(values, dtype=float)
        return float(np.max(a)), float(np.quantile(a, 0.99)), float(np.median(a))
    pmax, p99, pmed = stats(point_deltas)
    smax, s99, smed = stats(source_deltas)
    omax, o99, omed = stats(observer_deltas)
    hmax, _, _ = stats(h_deltas)
    return {
        "comparison": label, "common_epochs": len(common),
        "branch_comparisons": len(detail),
        "max_contact_delta_km": pmax, "p99_contact_delta_km": p99, "median_contact_delta_km": pmed,
        "max_source_direction_delta_rad": smax, "p99_source_direction_delta_rad": s99,
        "median_source_direction_delta_rad": smed,
        "max_observer_direction_delta_rad": omax, "p99_observer_direction_delta_rad": o99,
        "median_observer_direction_delta_rad": omed, "max_tangent_parameter_delta": hmax,
        "nearest_assignment_identity_changes": assignment_changes, "detail": detail,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--one-second", type=Path, required=True)
    parser.add_argument("--half-glob", required=True)
    parser.add_argument("--quarter-glob", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    one = read(args.one_second)
    half_paths = [Path(x) for x in sorted(glob.glob(args.half_glob))]
    quarter_paths = [Path(x) for x in sorted(glob.glob(args.quarter_glob))]
    half, half_overlap = merge_shards(half_paths, 481, "0.5-second")
    quarter, quarter_overlap = merge_shards(quarter_paths, 961, "0.25-second")
    counts = {
        "1s": validate_grid(one, 1.0, "1-second"),
        "0.5s": validate_grid(half, 0.5, "0.5-second"),
        "0.25s": validate_grid(quarter, 0.25, "0.25-second"),
    }
    a = compare_pair(one, half, "1s_vs_0.5s")
    b = compare_pair(half, quarter, "0.5s_vs_0.25s")
    output = args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(("comparison", "common_epochs", "branch_comparisons",
                         "max_contact_delta_km", "p99_contact_delta_km", "median_contact_delta_km",
                         "max_source_direction_delta_rad", "p99_source_direction_delta_rad",
                         "median_source_direction_delta_rad", "max_observer_direction_delta_rad",
                         "p99_observer_direction_delta_rad", "median_observer_direction_delta_rad",
                         "max_tangent_parameter_delta", "nearest_assignment_identity_changes"))
        for item in (a, b):
            writer.writerow(tuple(item[k] for k in (
                "comparison", "common_epochs", "branch_comparisons", "max_contact_delta_km",
                "p99_contact_delta_km", "median_contact_delta_km", "max_source_direction_delta_rad",
                "p99_source_direction_delta_rad", "median_source_direction_delta_rad",
                "max_observer_direction_delta_rad", "p99_observer_direction_delta_rad",
                "median_observer_direction_delta_rad", "max_tangent_parameter_delta",
                "nearest_assignment_identity_changes")))
    detail_path = output.with_name(output.stem + "_detail.csv")
    with detail_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(("comparison", "utc", "azimuth_index", "contact_delta_km",
                         "source_direction_delta_rad", "observer_direction_delta_rad",
                         "tangent_parameter_abs_delta", "nearest_assignment_index_changed",
                         "nearest_assigned_contact_distance_km"))
        writer.writerows(a["detail"] + b["detail"])

    print("phase=DE441_SUBSECOND_TEMPORAL_CONVERGENCE")
    for label, count in counts.items():
        print(f"{label}_epoch_count={count}")
        print(f"{label}_branch_count={BRANCHES}")
        print(f"{label}_complete_grid_and_branch_coverage=PASS")
    print(f"half_second_shard_count={len(half_paths)}")
    print(f"quarter_second_shard_count={len(quarter_paths)}")
    print(f"half_second_overlap_duplicate_rows={half_overlap}")
    print(f"quarter_second_overlap_duplicate_rows={quarter_overlap}")
    for item in (a, b):
        prefix = item["comparison"]
        for key in ("common_epochs", "branch_comparisons", "max_contact_delta_km",
                    "p99_contact_delta_km", "median_contact_delta_km",
                    "max_source_direction_delta_rad", "max_observer_direction_delta_rad",
                    "max_tangent_parameter_delta", "nearest_assignment_identity_changes"):
            print(f"{prefix}_{key}={item[key]}")
        print(f"{prefix}_direct_branch_correspondence=PASS")
    contact_decreased = b["max_contact_delta_km"] < a["max_contact_delta_km"]
    source_decreased = b["max_source_direction_delta_rad"] < a["max_source_direction_delta_rad"]
    observer_decreased = b["max_observer_direction_delta_rad"] < a["max_observer_direction_delta_rad"]
    print(f"max_contact_difference_decreased_at_next_refinement={contact_decreased}")
    print(f"max_source_direction_difference_decreased_at_next_refinement={source_decreased}")
    print(f"max_observer_direction_difference_decreased_at_next_refinement={observer_decreased}")
    print("monotonic_decrease_is_reported_not_assumed=YES")
    print("nearest_assignment_is_diagnostic_only=YES")
    print("continuous_between_samples=NOT_PROVEN")
    print("crossing_time_extraction=NOT_RUN")
    print("crossing_roots_modified=NO")
    print(f"summary_csv={output}")
    print(f"detail_csv={detail_path}")
    print("status=PASS")


if __name__ == "__main__":
    main()
