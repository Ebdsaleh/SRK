import unittest

from rikai_kotoba.hardware.saturn.midi_68k_r25_progress import (
    SaturnMidi68KR25ProgressError,
    build_saturn_midi_68k_r25_progress,
    build_saturn_midi_68k_r25_progress_bar,
    format_saturn_midi_68k_r25_clock,
)


class SaturnMidi68KR25ProgressTests(unittest.TestCase):
    def test_formats_reference_song_total_for_human_readable_timeline(self):
        self.assertEqual(format_saturn_midi_68k_r25_clock(108_151_354), "01:48.151")

    def test_progress_surface_exposes_elapsed_total_events_batches_and_bar(self):
        progress = build_saturn_midi_68k_r25_progress(
            elapsed_us=54_075_677,
            total_us=108_151_354,
            completed_records=155,
            total_records=310,
            batch_sequence=5,
            total_batches=10,
            bar_width=20,
        )
        self.assertEqual(progress.permille, 500)
        self.assertEqual(progress.clock_text, "00:54.075/01:48.151  50%")
        self.assertEqual(progress.record_text, "Events 155/310")
        self.assertEqual(progress.batch_text, "Batch 05/10")
        self.assertEqual(progress.bar_text, "[##########----------]")

    def test_elapsed_clock_clamps_at_total_after_terminal_poll_delay(self):
        progress = build_saturn_midi_68k_r25_progress(
            elapsed_us=108_347_424,
            total_us=108_151_354,
            completed_records=310,
            total_records=310,
            batch_sequence=10,
            total_batches=10,
        )
        self.assertEqual(progress.permille, 1000)
        self.assertEqual(progress.clock_text, "01:48.151/01:48.151 100%")
        self.assertTrue(progress.bar_text.startswith("["))
        self.assertNotIn("-", progress.bar_text)

    def test_progress_bar_rejects_invalid_range(self):
        with self.assertRaises(SaturnMidi68KR25ProgressError):
            build_saturn_midi_68k_r25_progress_bar(1001)

    def test_progress_rejects_record_overrun(self):
        with self.assertRaisesRegex(SaturnMidi68KR25ProgressError, "record progress"):
            build_saturn_midi_68k_r25_progress(
                elapsed_us=1,
                total_us=10,
                completed_records=311,
                total_records=310,
                batch_sequence=1,
                total_batches=10,
            )


if __name__ == "__main__":
    unittest.main()
