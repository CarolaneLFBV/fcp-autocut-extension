from __future__ import annotations

import hashlib
import json
import math
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from .detector import FFmpegError
from .models import AutoCutPlan


@dataclass(frozen=True, slots=True)
class MediaInfo:
    width: int
    height: int
    frame_rate: Fraction
    audio_rate: int
    audio_channels: int


def _seconds(value: float) -> str:
    fraction = Fraction(round(value * 1_000_000), 1_000_000)
    if fraction.denominator == 1:
        return f"{fraction.numerator}s"
    return f"{fraction.numerator}/{fraction.denominator}s"


def _fraction(value: str) -> Fraction:
    try:
        result = Fraction(value)
    except (ValueError, ZeroDivisionError) as error:
        raise FFmpegError(f"Fréquence d'image invalide : {value}") from error
    if result <= 0:
        raise FFmpegError(f"Fréquence d'image invalide : {value}")
    return result


def probe_media_info(media: str | Path, ffprobe: str = "ffprobe") -> MediaInfo:
    command = [
        ffprobe,
        "-v",
        "error",
        "-show_entries",
        "stream=codec_type,width,height,avg_frame_rate,r_frame_rate,sample_rate,channels",
        "-of",
        "json",
        str(media),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise FFmpegError("Impossible de lire les pistes du média")

    try:
        streams = json.loads(result.stdout)["streams"]
        video = next(item for item in streams if item.get("codec_type") == "video")
        audio = next(item for item in streams if item.get("codec_type") == "audio")
        rate_text = video.get("avg_frame_rate") or video["r_frame_rate"]
        return MediaInfo(
            width=int(video["width"]),
            height=int(video["height"]),
            frame_rate=_fraction(rate_text),
            audio_rate=int(audio["sample_rate"]),
            audio_channels=int(audio["channels"]),
        )
    except (KeyError, StopIteration, TypeError, ValueError, json.JSONDecodeError) as error:
        raise FFmpegError("Le média doit contenir une piste vidéo et une piste audio") from error


def _kept_frame_ranges(
    plan: AutoCutPlan,
    frame_rate: Fraction,
) -> tuple[tuple[int, int], ...]:
    epsilon = 1e-7
    total_frames = math.floor(plan.media_duration * float(frame_rate) + epsilon)
    cut_frames: list[tuple[int, int]] = []
    for cut in plan.cut_ranges:
        # Réduire la coupe plutôt que risquer de rogner la parole adjacente.
        start_frame = math.ceil(cut.start * float(frame_rate) - epsilon)
        end_frame = math.floor(cut.end * float(frame_rate) + epsilon)
        if end_frame > start_frame:
            cut_frames.append((start_frame, end_frame))

    kept: list[tuple[int, int]] = []
    cursor = 0
    for start, end in cut_frames:
        if start > cursor:
            kept.append((cursor, start))
        cursor = end
    if cursor < total_frames:
        kept.append((cursor, total_frames))
    return tuple(kept)


def _frame_time(frame_count: int, frame_rate: Fraction) -> str:
    value = Fraction(frame_count, 1) / frame_rate
    if value.denominator == 1:
        return f"{value.numerator}s"
    return f"{value.numerator}/{value.denominator}s"


def build_fcpxml(plan: AutoCutPlan, info: MediaInfo) -> str:
    media_path = Path(plan.media)
    kept_ranges = _kept_frame_ranges(plan, info.frame_rate)
    timeline_frames = sum(end - start for start, end in kept_ranges)
    signature = hashlib.sha256(media_path.as_uri().encode()).hexdigest()[:32].upper()

    root = ET.Element("fcpxml", {"version": "1.10"})
    resources = ET.SubElement(root, "resources")
    frame_duration = Fraction(1, 1) / info.frame_rate
    ET.SubElement(
        resources,
        "format",
        {
            "id": "r1",
            "frameDuration": (
                f"{frame_duration.numerator}/{frame_duration.denominator}s"
            ),
            "width": str(info.width),
            "height": str(info.height),
            "colorSpace": "1-1-1 (Rec. 709)",
        },
    )
    asset = ET.SubElement(
        resources,
        "asset",
        {
            "id": "r2",
            "name": media_path.name,
            "uid": signature,
            "start": "0s",
            "duration": _seconds(plan.media_duration),
            "hasVideo": "1",
            "format": "r1",
            "videoSources": "1",
            "hasAudio": "1",
            "audioSources": "1",
            "audioChannels": str(info.audio_channels),
            "audioRate": str(info.audio_rate),
        },
    )
    ET.SubElement(
        asset,
        "media-rep",
        {
            "kind": "original-media",
            "sig": signature,
            "src": media_path.as_uri(),
        },
    )

    event = ET.SubElement(root, "event", {"name": "AutoCut"})
    project = ET.SubElement(
        event,
        "project",
        {"name": f"{media_path.stem} — AutoCut"},
    )
    sequence = ET.SubElement(
        project,
        "sequence",
        {
            "format": "r1",
            "duration": _frame_time(timeline_frames, info.frame_rate),
            "tcStart": "0s",
            "tcFormat": "NDF",
            "audioLayout": "mono" if info.audio_channels == 1 else "stereo",
            "audioRate": _sequence_audio_rate(info.audio_rate),
        },
    )
    spine = ET.SubElement(sequence, "spine")

    offset_frames = 0
    for start_frame, end_frame in kept_ranges:
        duration_frames = end_frame - start_frame
        ET.SubElement(
            spine,
            "asset-clip",
            {
                "ref": "r2",
                "offset": _frame_time(offset_frames, info.frame_rate),
                "name": media_path.name,
                "start": _frame_time(start_frame, info.frame_rate),
                "duration": _frame_time(duration_frames, info.frame_rate),
                "format": "r1",
                "tcFormat": "NDF",
                "audioRole": "dialogue",
            },
        )
        offset_frames += duration_frames

    ET.indent(root, space="    ")
    body = ET.tostring(root, encoding="unicode", short_empty_elements=True)
    return '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE fcpxml>\n' + body + "\n"


def write_fcpxml(plan: AutoCutPlan, destination: str | Path) -> Path:
    output_path = Path(destination).expanduser().resolve()
    info = probe_media_info(plan.media)
    output_path.write_text(build_fcpxml(plan, info), encoding="utf-8")
    return output_path


def _sequence_audio_rate(rate: int) -> str:
    labels = {
        32_000: "32k",
        44_100: "44.1k",
        48_000: "48k",
        88_200: "88.2k",
        96_000: "96k",
        176_400: "176.4k",
        192_000: "192k",
    }
    try:
        return labels[rate]
    except KeyError as error:
        raise FFmpegError(f"Fréquence audio non prise en charge par FCPXML : {rate}") from error
