import tempfile
import unittest
import xml.etree.ElementTree as ET
from fractions import Fraction
from pathlib import Path

from fcp_autocut.fcpxml import MediaInfo, build_fcpxml
from fcp_autocut.models import AutoCutPlan, AutoCutSettings, TimeRange


class FCPXMLTests(unittest.TestCase):
    def test_builds_compacted_storyline_from_kept_ranges(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            media = Path(directory) / "Interview & test.mov"
            media.touch()
            plan = AutoCutPlan(
                media=str(media),
                media_duration=5,
                settings=AutoCutSettings(),
                silence_ranges=(TimeRange(1, 4),),
                cut_ranges=(TimeRange(1.2, 3.8),),
            )
            info = MediaInfo(
                width=1920,
                height=1080,
                frame_rate=Fraction(25, 1),
                audio_rate=48_000,
                audio_channels=2,
            )

            document = build_fcpxml(plan, info)
            root = ET.fromstring(document.split("<!DOCTYPE fcpxml>\n", 1)[1])

            self.assertEqual(root.attrib["version"], "1.10")
            self.assertEqual(
                root.find("./resources/format").attrib["frameDuration"],
                "1/25s",
            )
            self.assertEqual(
                root.find("./resources/asset/media-rep").attrib["src"],
                media.as_uri(),
            )
            sequence = root.find("./event/project/sequence")
            self.assertEqual(sequence.attrib["duration"], "12/5s")
            clips = root.findall("./event/project/sequence/spine/asset-clip")
            self.assertEqual(len(clips), 2)
            self.assertEqual(clips[0].attrib["start"], "0s")
            self.assertEqual(clips[0].attrib["duration"], "6/5s")
            self.assertEqual(clips[1].attrib["offset"], "6/5s")
            self.assertEqual(clips[1].attrib["start"], "19/5s")
            self.assertEqual(clips[1].attrib["duration"], "6/5s")

    def test_aligns_detected_boundaries_to_video_frames(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            media = Path(directory) / "interview.mov"
            media.touch()
            plan = AutoCutPlan(
                media=str(media),
                media_duration=5,
                settings=AutoCutSettings(),
                silence_ranges=(TimeRange(1, 4.00002),),
                cut_ranges=(TimeRange(1.20001, 3.80002),),
            )
            info = MediaInfo(1920, 1080, Fraction(25), 48_000, 2)

            document = build_fcpxml(plan, info)
            root = ET.fromstring(document.split("<!DOCTYPE fcpxml>\n", 1)[1])
            sequence = root.find("./event/project/sequence")
            clips = root.findall("./event/project/sequence/spine/asset-clip")

            self.assertEqual(sequence.attrib["duration"], "61/25s")
            self.assertEqual(clips[0].attrib["duration"], "31/25s")
            self.assertEqual(clips[1].attrib["offset"], "31/25s")
            self.assertEqual(clips[1].attrib["start"], "19/5s")


if __name__ == "__main__":
    unittest.main()
