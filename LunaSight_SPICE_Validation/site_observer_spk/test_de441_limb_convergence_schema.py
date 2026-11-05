"""Fast schema-contract tests for the expensive DE441 convergence pipeline."""
from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from compare_de441_limb_temporal_convergence import REQUIRED_COLUMNS, read_csv, vector


class ConvergenceCsvSchemaTests(unittest.TestCase):
    def test_export_header_matches_comparator_contract(self):
        exported = {
            "utc", "azimuth_index", "h",
            "earth_fixed_point_step_km", "ssb_point_step_km_including_earth_translation",
            "source_direction_step_arcsec", "observer_direction_step_arcsec",
            "source_direction_second_difference_arcsec",
            "observer_direction_second_difference_arcsec",
            "earth_fixed_point_second_difference_km",
            "tangency_residual", "surface_residual", "independent_reference_error",
            "point_fixed_x_km", "point_fixed_y_km", "point_fixed_z_km",
            "source_dir_x", "source_dir_y", "source_dir_z",
            "observer_dir_x", "observer_dir_y", "observer_dir_z",
        }
        self.assertTrue(REQUIRED_COLUMNS.issubset(exported))

    def test_reader_accepts_actual_export_vector_names(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.csv"
            fields = sorted(REQUIRED_COLUMNS)
            row = {name: "1" for name in fields}
            row.update({"utc": "2026-11-02T14:12:00.000", "azimuth_index": "0", "h": "0.5"})
            with path.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                writer.writerow(row)
            loaded = read_csv(path)
            self.assertEqual(len(loaded), 1)
            self.assertEqual(vector(loaded[("2026-11-02T14:12:00.000", 0)], "point_fixed").tolist(),
                             [1.0, 1.0, 1.0])
            self.assertEqual(vector(loaded[("2026-11-02T14:12:00.000", 0)], "source_dir").tolist(),
                             [1.0, 1.0, 1.0])

    def test_reader_rejects_missing_vector_column(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.csv"
            path.write_text("utc,azimuth_index,h\n2026-11-02T14:12:00.000,0,0.5\n", encoding="utf-8")
            with self.assertRaisesRegex(AssertionError, "missing required CSV columns"):
                read_csv(path)


if __name__ == "__main__":
    unittest.main()
