"""Tests de las funciones de formato."""

import unittest
from datetime import datetime
from src.display.formatters import (
	format_uptime,
	format_time_unix,
	format_kb,
	format_proc_state,
)


class TestFormatUptime(unittest.TestCase):
	def test_seconds_only(self):
		self.assertEqual(format_uptime(45), "45s")

	def test_minutes_and_seconds(self):
		self.assertEqual(format_uptime(125), "2m 5s")

	def test_hours_minutes_seconds(self):
		self.assertEqual(format_uptime(3665), "1h 1m 5s")

	def test_days_hours_minutes_seconds(self):
		self.assertEqual(format_uptime(90125), "1d 1h 2m 5s")

	def test_zero_seconds(self):
		self.assertEqual(format_uptime(0), "0s")

	def test_none_input(self):
		self.assertIsNone(format_uptime(None))


class TestFormatTimeUnix(unittest.TestCase):
	def test_known_timestamp(self):
		# 2026-07-28 12:00:00 UTC
		ts = int(datetime(2026, 7, 28, 12, 0, 0).timestamp())
		result = format_time_unix(ts)
		self.assertIn("2026", result)
		self.assertIn("07-28", result)

	def test_none_input(self):
		self.assertIsNone(format_time_unix(None))


class TestFormatKb(unittest.TestCase):
	def test_kilobytes(self):
		self.assertEqual(format_kb(512), "512 KB")

	def test_megabytes(self):
		self.assertEqual(format_kb(1024 * 512), "512 MB")

	def test_gigabytes_with_decimals(self):
		result = format_kb(1024 * 1024 * 1)
		self.assertIn("1", result)
		self.assertIn("GB", result)

	def test_gigabytes_large(self):
		result = format_kb(1024 * 1024 * 512)
		self.assertIn("512", result)
		self.assertIn("GB", result)

	def test_terabytes(self):
		result = format_kb(1024 * 1024 * 1024 * 2)
		self.assertIn("2", result)
		self.assertIn("TB", result)

	def test_none_input(self):
		self.assertIsNone(format_kb(None))

	def test_zero(self):
		self.assertEqual(format_kb(0), "0 KB")


class TestFormatProcState(unittest.TestCase):
	def test_single_state(self):
		result = format_proc_state({"R": 2})
		self.assertEqual(result, "R: 2")

	def test_multiple_states(self):
		result = format_proc_state({"R": 2, "S": 38, "Z": 1})
		self.assertEqual(result, "R: 2  S: 38  Z: 1")

	def test_all_states(self):
		result = format_proc_state({"R": 1, "S": 2, "D": 3, "T": 4, "Z": 5})
		self.assertEqual(result, "R: 1  S: 2  D: 3  T: 4  Z: 5")

	def test_zero_counts_excluded(self):
		result = format_proc_state({"R": 2, "S": 0, "D": 0, "T": 0, "Z": 1})
		self.assertEqual(result, "R: 2  Z: 1")

	def test_empty_dict(self):
		self.assertIsNone(format_proc_state({}))

	def test_none_input(self):
		self.assertIsNone(format_proc_state(None))


if __name__ == "__main__":
	unittest.main()
