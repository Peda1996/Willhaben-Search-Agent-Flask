import unittest
from datetime import datetime, timezone

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from time_utils import format_local_datetime, parse_stored_datetime  # noqa: E402


class TimezoneTests(unittest.TestCase):
    def test_legacy_sqlite_utc_timestamp_is_shown_in_vienna_summer_time(self):
        self.assertEqual(
            format_local_datetime("2026-09-22 20:15:00"),
            "22.09.2026, 22:15:00 CEST",
        )

    def test_legacy_sqlite_utc_timestamp_is_shown_in_vienna_winter_time(self):
        self.assertEqual(
            format_local_datetime("2026-01-22 20:15:00"),
            "22.01.2026, 21:15:00 CET",
        )

    def test_offset_timestamp_describes_the_same_utc_instant(self):
        parsed = parse_stored_datetime("2026-09-22T22:15:00+02:00")
        self.assertEqual(parsed, datetime(2026, 9, 22, 20, 15, tzinfo=timezone.utc))


if __name__ == "__main__":
    unittest.main()
