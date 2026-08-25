import math
import shutil
import struct
import tempfile
import unittest
import wave
from pathlib import Path

from fcp_autocut.detector import FFmpegSilenceDetector, parse_silencedetect_output
from fcp_autocut.models import AutoCutSettings, TimeRange


class ParseSilenceDetectOutputTests(unittest.TestCase):
    def test_parses_ranges_and_ignores_unrelated_output(self) -> None:
        output = """
        Input #0, wav, from 'test.wav':
        [silencedetect @ 0x123] silence_start: 1.00002
        [silencedetect @ 0x123] silence_end: 4.00004 | silence_duration: 3.00002
        video:0kB audio:469kB
        """

        self.assertEqual(
            parse_silencedetect_output(output),
            (TimeRange(1.00002, 4.00004),),
        )


@unittest.skipUnless(
    shutil.which("ffmpeg") and shutil.which("ffprobe"),
    "FFmpeg et ffprobe sont nécessaires",
)
class FFmpegSilenceDetectorIntegrationTests(unittest.TestCase):
    def test_detects_three_second_silence_in_generated_audio(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            media = Path(directory) / "speech-silence-speech.wav"
            self._write_fixture(media)

            plan = FFmpegSilenceDetector().analyze(
                media,
                AutoCutSettings(
                    threshold_db=-40,
                    minimum_silence=2,
                    padding=0.2,
                ),
            )

            self.assertAlmostEqual(plan.media_duration, 5.0, places=2)
            self.assertEqual(len(plan.silence_ranges), 1)
            self.assertAlmostEqual(plan.silence_ranges[0].start, 1.0, places=2)
            self.assertAlmostEqual(plan.silence_ranges[0].end, 4.0, places=2)
            self.assertEqual(len(plan.cut_ranges), 1)
            self.assertAlmostEqual(plan.cut_ranges[0].start, 1.2, places=2)
            self.assertAlmostEqual(plan.cut_ranges[0].end, 3.8, places=2)
            self.assertAlmostEqual(plan.removed_duration, 2.6, places=2)

    @staticmethod
    def _write_fixture(path: Path) -> None:
        sample_rate = 48_000
        amplitude = 0.25 * 32767

        with wave.open(str(path), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(sample_rate)

            for second in range(5):
                for sample_index in range(sample_rate):
                    if second in (0, 4):
                        value = int(
                            amplitude
                            * math.sin(2 * math.pi * 440 * sample_index / sample_rate)
                        )
                    else:
                        value = 0
                    output.writeframesraw(struct.pack("<h", value))


if __name__ == "__main__":
    unittest.main()
