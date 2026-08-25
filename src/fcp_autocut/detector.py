from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

from .models import AutoCutPlan, AutoCutSettings, TimeRange, build_cut_ranges


_SILENCE_START = re.compile(r"silence_start:\s*(-?\d+(?:\.\d+)?)")
_SILENCE_END = re.compile(r"silence_end:\s*(-?\d+(?:\.\d+)?)")


class FFmpegError(RuntimeError):
    pass


def parse_silencedetect_output(output: str) -> tuple[TimeRange, ...]:
    """Transforme le journal du filtre FFmpeg en plages de silence."""

    ranges: list[TimeRange] = []
    current_start: float | None = None

    for line in output.splitlines():
        start_match = _SILENCE_START.search(line)
        if start_match:
            current_start = max(0.0, float(start_match.group(1)))

        end_match = _SILENCE_END.search(line)
        if end_match and current_start is not None:
            end = max(current_start, float(end_match.group(1)))
            ranges.append(TimeRange(current_start, end))
            current_start = None

    return tuple(ranges)


class FFmpegSilenceDetector:
    def __init__(self, ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe") -> None:
        self.ffmpeg = ffmpeg
        self.ffprobe = ffprobe

    def analyze(
        self,
        media: str | Path,
        settings: AutoCutSettings | None = None,
    ) -> AutoCutPlan:
        settings = settings or AutoCutSettings()
        media_path = Path(media).expanduser().resolve()
        self._validate_environment(media_path)

        duration = self._probe_duration(media_path)
        command = [
            self.ffmpeg,
            "-hide_banner",
            "-nostats",
            "-i",
            str(media_path),
            "-vn",
            "-af",
            (
                f"silencedetect=noise={settings.threshold_db:g}dB:"
                f"d={settings.minimum_silence:g}"
            ),
            "-f",
            "null",
            "-",
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            message = result.stderr.strip().splitlines()
            detail = message[-1] if message else "erreur FFmpeg inconnue"
            raise FFmpegError(f"Impossible d'analyser le média : {detail}")

        silences = parse_silencedetect_output(result.stderr)
        return AutoCutPlan(
            media=str(media_path),
            media_duration=duration,
            settings=settings,
            silence_ranges=silences,
            cut_ranges=build_cut_ranges(silences, settings),
        )

    def _validate_environment(self, media_path: Path) -> None:
        if not media_path.is_file():
            raise FileNotFoundError(f"Média introuvable : {media_path}")
        if shutil.which(self.ffmpeg) is None:
            raise FFmpegError(f"Exécutable introuvable : {self.ffmpeg}")
        if shutil.which(self.ffprobe) is None:
            raise FFmpegError(f"Exécutable introuvable : {self.ffprobe}")

    def _probe_duration(self, media_path: Path) -> float:
        command = [
            self.ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(media_path),
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise FFmpegError("Impossible de lire la durée du média")

        try:
            duration = float(json.loads(result.stdout)["format"]["duration"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise FFmpegError("Durée du média absente ou invalide") from error

        if duration <= 0:
            raise FFmpegError("La durée du média doit être positive")
        return duration
