"""Moteur de détection des silences pour FCP AutoCut."""

from .detector import FFmpegSilenceDetector
from .models import AutoCutPlan, AutoCutSettings, TimeRange

__all__ = [
    "AutoCutPlan",
    "AutoCutSettings",
    "FFmpegSilenceDetector",
    "TimeRange",
]
