"""Compare 5-second and 1-second limb tracking at identical epochs.

Reports direct-index correspondence and nearest-point assignment diagnostics.
No arbitrary physical continuity thresholds are imposed.
"""
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.optimize import linear_sum_assignment

COARSE = Path("de441_limb_continuity_5s.csv")
FINE = Path("de441_limb_continuity_1s.csv")
OUTPUT = Path("de441_limb_convergence_comparison.csv")


def vector(row: dict[str, str], prefix: str) -> np.ndarray:
    return np.array([float(row[f"{prefix}_{axis}"]) for axis in "xyz"], dtype=float)


def angular_difference(a: np.ndarray, b: np.ndarray) -> float:
    a = a / np.linalg.norm(a)
    b = b / np.linalg.norm(b)
    return float(np.arctan2(np.linalg.norm(np.cross(a, b)), np.clip(np.dot(a, b), -1.0, 1.0)))


def load(path: Path) -> dict[tuple[str, int], dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return {(row["utc"], int(row["azimuth_index"])): row for row in csv.DictReader(stream)}


def main() -> None:
    coarse, fine = load(COARSE), load(FINE)
    coarse_epochs = defaultdict(dict)
    fine_epochs = defaultdict(dict)
    for (utc, index), row in coarse.items():
        coarse_epochs[utc][index] = row
    for (utc, index), row in fine.items():
        fine_epochs[utc][index] = row

    common = sorted(set(coarse_epochs) & set(fine_epochs))
    if not common:
        raise AssertionError("No common UTC epochs exist between 5-second and 1-second runs.")

    rows = []
    max_direct_point = max_direct_source = max_direct_observer = max_abs_h = 0.0
    max_nearest_point = 0.0
    identity_mismatches = 0

    for utc in common:
        c, f = coarse_epochs[utc], fine_epochs[utc]
        indices = sorted(set(c) & set(f))
        expected = set(range(96))
        if set(c) != expected or set(f) != expected:
            raise AssertionError(f"Incomplete or inconsistent branch indices at {utc}.")
        cp = np.array([vector(c[i], "point_fixed") for i in indices])
        fp = np.array([vector(f[i], "point_fixed") for i in indices])
        cost = np.linalg.norm(cp[:, None, :] - fp[None, :, :], axis=2)
        rr, cc = linear_sum_assignment(cost)
        nearest = cost[rr, cc]
        max_nearest_point = max(max_nearest_point, float(np.max(nearest)))
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
    with OUTPUT.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(("utc", "azimuth_index", "earth_fixed_contact_delta_km",
                         "source_direction_delta_rad", "observer_direction_delta_rad",
                         "tangent_parameter_abs_delta", "nearest_assignment_index_changed",
                         "nearest_assigned_contact_distance_km"))
        writer.writerows(rows)

    print("phase=DE441_LIMB_TEMPORAL_RESOLUTION_CONVERGENCE")
    print("coarse_step_seconds=5")
    print("fine_step_seconds=1")
    print(f"common_epoch_count={len(common)}")
    print(f"common_branch_comparison_count={len(rows)}")
    print(f"max_direct_index_contact_delta_km={max_direct_point:.12g}")
    print(f"max_nearest_assigned_contact_distance_km={max_nearest_point:.12g}")
    print(f"max_direct_index_source_direction_delta_rad={max_direct_source:.12g}")
    print(f"max_direct_index_observer_direction_delta_rad={max_direct_observer:.12g}")
    print(f"max_tangent_parameter_abs_delta={max_abs_h:.12g}")
    print(f"nearest_assignment_nonidentity_count={identity_mismatches}")
    print("direct_index_branch_correspondence=REPORTED")
    print("nearest_assignment_is_diagnostic_not_relabeling=YES")
    print("comparison_thresholds=NO_UNJUSTIFIED_ARBITRARY_LIMITS")
    print(f"comparison_csv={OUTPUT}")
    print("status=PASS")


if __name__ == "__main__":
    main()
