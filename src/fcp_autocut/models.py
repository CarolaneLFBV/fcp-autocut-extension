from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TimeRange:
    start: float
    end: float

    def __post_init__(self) -> None:
        if self.start < 0:
            raise ValueError("Le début d'une plage ne peut pas être négatif")
        if self.end < self.start:
            raise ValueError("La fin d'une plage doit suivre son début")

    @property
    def duration(self) -> float:
        return self.end - self.start

    def as_dict(self) -> dict[str, float]:
        return {
            "start": round(self.start, 6),
            "end": round(self.end, 6),
            "duration": round(self.duration, 6),
        }


@dataclass(frozen=True, slots=True)
class AutoCutSettings:
    threshold_db: float = -40.0
    minimum_silence: float = 2.0
    padding: float = 0.2

    def __post_init__(self) -> None:
        if self.threshold_db > 0:
            raise ValueError("Le seuil audio doit être inférieur ou égal à 0 dB")
        if self.minimum_silence <= 0:
            raise ValueError("La durée minimale doit être positive")
        if self.padding < 0:
            raise ValueError("La marge ne peut pas être négative")

    def as_dict(self) -> dict[str, float]:
        return {
            "threshold_db": self.threshold_db,
            "minimum_silence": self.minimum_silence,
            "padding": self.padding,
        }


@dataclass(frozen=True, slots=True)
class AutoCutPlan:
    media: str
    media_duration: float
    settings: AutoCutSettings
    silence_ranges: tuple[TimeRange, ...]
    cut_ranges: tuple[TimeRange, ...]

    @property
    def removed_duration(self) -> float:
        return sum(item.duration for item in self.cut_ranges)

    @property
    def output_duration(self) -> float:
        return max(0.0, self.media_duration - self.removed_duration)

    def as_dict(self) -> dict[str, object]:
        return {
            "media": self.media,
            "media_duration": round(self.media_duration, 6),
            "settings": self.settings.as_dict(),
            "silence_ranges": [item.as_dict() for item in self.silence_ranges],
            "cut_ranges": [item.as_dict() for item in self.cut_ranges],
            "removed_duration": round(self.removed_duration, 6),
            "output_duration": round(self.output_duration, 6),
        }


def build_cut_ranges(
    silence_ranges: list[TimeRange] | tuple[TimeRange, ...],
    settings: AutoCutSettings,
) -> tuple[TimeRange, ...]:
    """Conserve une marge de chaque côté des silences assez longs."""

    cuts: list[TimeRange] = []
    for silence in silence_ranges:
        # Le produit promet « supérieur à », et non « supérieur ou égal à ».
        if silence.duration <= settings.minimum_silence:
            continue

        start = silence.start + settings.padding
        end = silence.end - settings.padding
        if end > start:
            cuts.append(TimeRange(start, end))

    return tuple(cuts)


def build_kept_ranges(
    media_duration: float,
    cut_ranges: list[TimeRange] | tuple[TimeRange, ...],
) -> tuple[TimeRange, ...]:
    """Retourne le complément ordonné des plages à retirer."""

    if media_duration <= 0:
        raise ValueError("La durée du média doit être positive")

    kept: list[TimeRange] = []
    cursor = 0.0
    for cut in cut_ranges:
        if cut.start < cursor or cut.end > media_duration:
            raise ValueError("Les coupes doivent être ordonnées et incluses dans le média")
        if cut.start > cursor:
            kept.append(TimeRange(cursor, cut.start))
        cursor = cut.end

    if cursor < media_duration:
        kept.append(TimeRange(cursor, media_duration))
    return tuple(kept)
