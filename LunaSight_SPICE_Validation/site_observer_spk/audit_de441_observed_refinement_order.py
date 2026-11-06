"""Audit observed temporal refinement order from existing DE441 shard CSVs.

This is a sampled-grid diagnostic. It compares signed solution-vector differences
at common epochs and never interprets the result as absolute physical accuracy.
"""
from __future__ import annotations

import argparse
import csv
import glob
import math
from collections import defaultdict
from pathlib import Path

import numpy as np

from compare_de441_subsecond_limb_convergence import (
    BRANCHES, merge_shards, validate_grid, vec, START, DURATION
)

EPS = np.finfo(float).eps
CONTACT_FLOOR_FACTOR = 32.0
UNIT_VECTOR_FLOOR_FACTOR = 32.0
H_FLOOR_FACTOR = 32.0


def unit_difference(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    a = a / np.linalg.norm(a)
    b = b / np.linalg.norm(b)
    return a - b


def observed_order(coarse_delta: np.ndarray, fine_delta: np.ndarray, floor: float):
    nc = float(np.linalg.norm(coarse_delta))
    nf = float(np.linalg.norm(fine_delta))
    if nc <= floor or nf <= floor:
        return "", "BELOW_NUMERICAL_FLOOR", nc, nf, ""
    ratio = nc / nf
    if not math.isfinite(ratio) or ratio <= 0:
        return "", "INVALID_RATIO", nc, nf, ratio
    p = math.log(ratio, 2.0)
    # Signed vector differences should be approximately aligned for a clean
    # single-leading-error-term interpretation.
    alignment = float(np.dot(coarse_delta, fine_delta) / (nc * nf))
    status = "ORDER_ESTIMATE_VALID" if alignment > 0.90 else "VECTOR_CANCELLATION_OR_MIXED_TERMS"
    return p, status, nc, nf, alignment


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--one-glob", required=True)
    parser.add_argument("--half-glob", required=True)
    parser.add_argument("--quarter-glob", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    one, one_overlap = merge_shards([Path(x) for x in sorted(glob.glob(args.one_glob))], 4, "1s")
    half, half_overlap = merge_shards([Path(x) for x in sorted(glob.glob(args.half_glob))], 4, "0.5s")
    quarter, quarter_overlap = merge_shards([Path(x) for x in sorted(glob.glob(args.quarter_glob))], 12, "0.25s")
    counts = (validate_grid(one, 1.0, "1s"), validate_grid(half, 0.5, "0.5s"),
              validate_grid(quarter, 0.25, "0.25s"))

    common = sorted(set(one) & set(half) & set(quarter))
    if len(common) != 241 * BRANCHES:
        raise AssertionError(f"Expected 241*96 common samples, got {len(common)}")

    detail_path = args.output.with_name(args.output.stem + "_detail.csv")
    records = []
    metric_values = defaultdict(list)
    metric_orders = defaultdict(list)
    metric_status = defaultdict(lambda: defaultdict(int))

    # Coordinate magnitudes establish scale-aware roundoff floors. The floors
    # are diagnostics, not acceptance thresholds.
    max_contact_scale = max(float(np.linalg.norm(vec(row, "point_fixed"))) for row in one.values())
    contact_floor = CONTACT_FLOOR_FACTOR * EPS * max_contact_scale
    direction_floor = UNIT_VECTOR_FLOOR_FACTOR * EPS
    h_floor = H_FLOOR_FACTOR * EPS

    for key in common:
        r1, r05, r025 = one[key], half[key], quarter[key]
        d1 = vec(r1, "point_fixed") - vec(r05, "point_fixed")
        d2 = vec(r05, "point_fixed") - vec(r025, "point_fixed")
        p, status, n1, n2, alignment = observed_order(d1, d2, contact_floor)
        records.append(("contact_position", *key, n1, n2, p, alignment, status))
        metric_values["contact_position"].extend((n1, n2))
        metric_status["contact_position"][status] += 1
        if isinstance(p, float):
            metric_orders["contact_position"].append(p)

        for label, field in (("source_direction", "source_dir"), ("observer_direction", "observer_dir")):
            v1 = unit_difference(vec(r1, field), vec(r05, field))
            v2 = unit_difference(vec(r05, field), vec(r025, field))
            p, status, n1, n2, alignment = observed_order(v1, v2, direction_floor)
            records.append((label, *key, n1, n2, p, alignment, status))
            metric_values[label].extend((n1, n2))
            metric_status[label][status] += 1
            if isinstance(p, float):
                metric_orders[label].append(p)

        dh1 = float(r1["h"]) - float(r05["h"])
        dh2 = float(r05["h"]) - float(r025["h"])
        p, status, n1, n2, alignment = observed_order(np.array([dh1]), np.array([dh2]), h_floor)
        records.append(("tangent_parameter", *key, n1, n2, p, alignment, status))
        metric_values["tangent_parameter"].extend((n1, n2))
        metric_status["tangent_parameter"][status] += 1
        if isinstance(p, float):
            metric_orders["tangent_parameter"].append(p)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with detail_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(("metric", "utc", "branch", "coarse_difference_norm",
                         "fine_difference_norm", "observed_order_p", "signed_vector_alignment",
                         "classification"))
        writer.writerows(records)

    summary_path = args.output
    with summary_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(("metric", "valid_order_samples", "below_floor_or_invalid_samples",
                         "median_observed_order", "p10_observed_order", "p90_observed_order",
                         "median_coarse_difference", "median_fine_difference", "unit",
                         "roundoff_floor", "interpretation"))
        units = {"contact_position": "km", "source_direction": "rad",
                 "observer_direction": "rad", "tangent_parameter": "dimensionless"}
        for metric in ("contact_position", "source_direction", "observer_direction", "tangent_parameter"):
            orders = np.asarray(metric_orders[metric], dtype=float)
            values = np.asarray(metric_values[metric], dtype=float)
            floor = contact_floor if metric == "contact_position" else (h_floor if metric == "tangent_parameter" else direction_floor)
            interpretation = ("SAMPLED_DIAGNOSTIC_ONLY; order meaningful only where signed differences align "
                              "and exceed roundoff floor")
            writer.writerow((metric, len(orders), len(common) - len(orders),
                             float(np.median(orders)) if len(orders) else "",
                             float(np.quantile(orders, .1)) if len(orders) else "",
                             float(np.quantile(orders, .9)) if len(orders) else "",
                             float(np.median(values[0::2])) if len(values) else "",
                             float(np.median(values[1::2])) if len(values) else "",
                             units[metric], floor, interpretation))

    print("phase=DE441_OBSERVED_REFINEMENT_ORDER_AUDIT")
    print(f"epoch_counts_1s_0.5s_0.25s={counts}")
    print(f"common_epoch_branch_samples={len(common)}")
    print(f"overlap_duplicates_1s_0.5s_0.25s={one_overlap},{half_overlap},{quarter_overlap}")
    print(f"contact_roundoff_floor_km={contact_floor:.16e}")
    print(f"unit_vector_roundoff_floor_rad={direction_floor:.16e}")
    for metric in ("contact_position", "source_direction", "observer_direction", "tangent_parameter"):
        orders = np.asarray(metric_orders[metric], dtype=float)
        print(f"{metric}_valid_order_samples={len(orders)}")
        if len(orders):
            print(f"{metric}_median_observed_order={np.median(orders):.12g}")
            print(f"{metric}_p10_observed_order={np.quantile(orders,.1):.12g}")
            print(f"{metric}_p90_observed_order={np.quantile(orders,.9):.12g}")
        print(f"{metric}_classification_counts={dict(metric_status[metric])}")
    print("order_estimate_requires_signed_vector_alignment=YES")
    print("roundoff_floor_is_diagnostic_not_acceptance_gate=YES")
    print("continuous_between_samples=NOT_PROVEN")
    print("absolute_physical_accuracy=NOT_ESTABLISHED")
    print("crossing_time_extraction=NOT_RUN")
    print("historical_roots_and_horizons_outputs_modified=NO")
    print(f"summary_csv={summary_path}")
    print(f"detail_csv={detail_path}")
    print("status=PASS")


if __name__ == "__main__":
    main()
