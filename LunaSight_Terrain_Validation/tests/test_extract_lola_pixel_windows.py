import unittest

from LunaSight_Terrain_Validation.extract_lola_pixel_windows import (
    inverse_affine, pixel_window_from_map_bounds,
)


class PixelWindowTests(unittest.TestCase):
    def test_north_up_negative_y_resolution(self):
        gt = [100.0, 5.0, 0.0, 200.0, 0.0, -5.0]
        self.assertEqual(pixel_window_from_map_bounds(gt, 100, 100, (120, 150, 170, 180)),
                         (4, 4, 10, 6))

    def test_positive_y_resolution(self):
        gt = [100.0, 5.0, 0.0, 200.0, 0.0, 5.0]
        self.assertEqual(pixel_window_from_map_bounds(gt, 100, 100, (120, 210, 170, 240)),
                         (4, 2, 10, 6))

    def test_rotated_affine(self):
        gt = [10.0, 2.0, 1.0, 20.0, 1.0, -2.0]
        points = [(3, 4), (5, 4), (3, 6), (5, 6)]
        mapped = [(gt[0] + c*gt[1] + r*gt[2], gt[3] + c*gt[4] + r*gt[5])
                  for c, r in points]
        bounds = (min(p[0] for p in mapped), min(p[1] for p in mapped),
                  max(p[0] for p in mapped), max(p[1] for p in mapped))
        window = pixel_window_from_map_bounds(gt, 20, 20, bounds)
        self.assertEqual(window, (2, 3, 4, 4))

    def test_rejects_out_of_bounds(self):
        gt = [0.0, 1.0, 0.0, 10.0, 0.0, -1.0]
        with self.assertRaisesRegex(ValueError, "outside raster"):
            pixel_window_from_map_bounds(gt, 10, 10, (-2, 2, 2, 8))

    def test_rejects_invalid_bounds(self):
        with self.assertRaisesRegex(ValueError, "Invalid map bounds"):
            pixel_window_from_map_bounds([0, 1, 0, 0, 0, -1], 10, 10, (4, 4, 2, 2))

    def test_inverse_affine_roundtrip(self):
        gt = [10.0, 2.0, 1.0, 20.0, 1.0, -2.0]
        x = gt[0] + 3*gt[1] + 4*gt[2]
        y = gt[3] + 3*gt[4] + 4*gt[5]
        self.assertEqual(inverse_affine(gt, x, y), (3.0, 4.0))


if __name__ == "__main__":
    unittest.main()
