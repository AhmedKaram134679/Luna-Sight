import unittest

from LunaSight_Terrain_Validation.terrain_validate import _pixel_from_map, _point_in_polygon


class GeometryHelperTests(unittest.TestCase):
    def test_pixel_inverse_affine_without_rotation(self):
        gt = [100.0, 2.0, 0.0, 200.0, 0.0, -2.0]
        self.assertEqual(_pixel_from_map(110.0, 190.0, gt), (5.0, 5.0))

    def test_pixel_inverse_affine_with_rotation(self):
        gt = [10.0, 2.0, 1.0, 20.0, 1.0, -2.0]
        col, row = 3.0, 4.0
        x = gt[0] + col * gt[1] + row * gt[2]
        y = gt[3] + col * gt[4] + row * gt[5]
        actual = _pixel_from_map(x, y, gt)
        self.assertAlmostEqual(actual[0], col)
        self.assertAlmostEqual(actual[1], row)

    def test_point_inside_polygon(self):
        polygon = [(0, 0), (10, 0), (10, 10), (0, 10)]
        self.assertTrue(_point_in_polygon((5, 5), polygon))
        self.assertFalse(_point_in_polygon((15, 5), polygon))


if __name__ == "__main__":
    unittest.main()
