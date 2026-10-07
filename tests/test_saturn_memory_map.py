"""Tests for the small Saturn memory-map surface used by capture tools."""

import unittest

from rikai_kotoba.hardware.saturn.memory_map import (
    WORK_RAM_HIGH,
    WORK_RAM_LOW,
    WORK_RAM_REGIONS,
)


class SaturnMemoryMapTests(unittest.TestCase):
    def test_work_ram_low_is_one_megabyte_at_canonical_address(self):
        self.assertEqual(WORK_RAM_LOW.start_address, 0x00200000)
        self.assertEqual(WORK_RAM_LOW.size, 0x00100000)
        self.assertEqual(WORK_RAM_LOW.end_address_exclusive, 0x00300000)

    def test_work_ram_high_is_one_megabyte_at_canonical_address(self):
        self.assertEqual(WORK_RAM_HIGH.start_address, 0x06000000)
        self.assertEqual(WORK_RAM_HIGH.size, 0x00100000)
        self.assertEqual(WORK_RAM_HIGH.end_address_exclusive, 0x06100000)

    def test_capture_region_order_is_low_then_high(self):
        self.assertEqual(WORK_RAM_REGIONS, (WORK_RAM_LOW, WORK_RAM_HIGH))


if __name__ == "__main__":
    unittest.main()
