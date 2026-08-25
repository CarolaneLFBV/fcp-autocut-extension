import unittest

from fcp_autocut.models import (
    AutoCutSettings,
    TimeRange,
    build_cut_ranges,
    build_kept_ranges,
)


class BuildCutRangesTests(unittest.TestCase):
    def test_keeps_padding_around_speech(self) -> None:
        settings = AutoCutSettings(minimum_silence=2.0, padding=0.2)

        cuts = build_cut_ranges([TimeRange(1.0, 4.0)], settings)

        self.assertEqual(cuts, (TimeRange(1.2, 3.8),))

    def test_requires_silence_strictly_longer_than_minimum(self) -> None:
        settings = AutoCutSettings(minimum_silence=2.0, padding=0)

        cuts = build_cut_ranges(
            [TimeRange(0, 2), TimeRange(3, 5.0001)],
            settings,
        )

        self.assertEqual(cuts, (TimeRange(3, 5.0001),))

    def test_ignores_range_consumed_by_padding(self) -> None:
        settings = AutoCutSettings(minimum_silence=2.0, padding=2.0)

        cuts = build_cut_ranges([TimeRange(0, 3)], settings)

        self.assertEqual(cuts, ())

    def test_rejects_invalid_settings(self) -> None:
        with self.assertRaises(ValueError):
            AutoCutSettings(minimum_silence=0)
        with self.assertRaises(ValueError):
            AutoCutSettings(padding=-0.1)
        with self.assertRaises(ValueError):
            AutoCutSettings(threshold_db=1)

    def test_builds_complementary_kept_ranges(self) -> None:
        kept = build_kept_ranges(
            10,
            [TimeRange(1, 3), TimeRange(6, 8)],
        )

        self.assertEqual(
            kept,
            (TimeRange(0, 1), TimeRange(3, 6), TimeRange(8, 10)),
        )


if __name__ == "__main__":
    unittest.main()
