from __future__ import annotations

import unittest

from salix.framework.geometry import (
    ContentMetrics,
    HorizontalAlign,
    aligned_offset,
    clamp,
    content_bounds,
    fill_height,
    split_sizes,
)


class SalixGeometryTests(unittest.TestCase):
    def test_content_bounds_centers_readable_region(self):
        bounds = content_bounds(
            1400,
            800,
            metrics=ContentMetrics(
                horizontal_padding=20,
                vertical_padding=10,
                minimum_width=320,
                maximum_width=980,
            ),
        )
        self.assertEqual(bounds.width, 980)
        self.assertEqual(bounds.x, 210)
        self.assertEqual(bounds.y, 10)
        self.assertEqual(bounds.height, 780)

    def test_narrow_content_uses_available_width(self):
        bounds = content_bounds(
            300,
            metrics=ContentMetrics(horizontal_padding=20, minimum_width=320),
        )
        self.assertEqual(bounds.width, 260)
        self.assertEqual(bounds.x, 20)

    def test_alignment_offsets_are_parent_relative(self):
        self.assertEqual(aligned_offset(100, 20, HorizontalAlign.LEFT), 0)
        self.assertEqual(aligned_offset(100, 20, HorizontalAlign.CENTER), 40)
        self.assertEqual(aligned_offset(100, 20, HorizontalAlign.RIGHT), 80)

    def test_split_sizes_preserve_total_available_space(self):
        sizes = split_sizes(1000, (1, 2), minimums=(100, 100), gap=10)
        self.assertEqual(sum(sizes) + 10, 1000)
        self.assertGreater(sizes[1], sizes[0])

    def test_split_sizes_scale_when_minimums_do_not_fit(self):
        sizes = split_sizes(300, (1, 1), minimums=(250, 250), gap=10)
        self.assertEqual(sum(sizes) + 10, 300)
        self.assertTrue(all(value > 0 for value in sizes))

    def test_split_maximum_leaves_remaining_space_unclaimed(self):
        sizes = split_sizes(
            1000,
            (1, 1),
            minimums=(100, 100),
            maximums=(200, 200),
            gap=10,
        )
        self.assertEqual(sizes, (200, 200))

    def test_clamp_and_fill_height_are_stable(self):
        self.assertEqual(clamp(20, 0, 10), 10)
        self.assertEqual(fill_height(100, 30), 70)
        self.assertEqual(fill_height(10, 30, minimum=4), 4)


if __name__ == "__main__":
    unittest.main()
