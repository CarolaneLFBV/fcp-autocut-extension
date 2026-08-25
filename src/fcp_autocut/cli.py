from __future__ import annotations

import argparse
import json
import sys

from .detector import FFmpegError, FFmpegSilenceDetector
from .fcpxml import write_fcpxml
from .models import AutoCutPlan, AutoCutSettings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fcp-autocut",
        description="Détecte les silences et génère un plan de coupe AutoCut.",
    )
    parser.add_argument("media", help="fichier vidéo ou audio à analyser")
    parser.add_argument(
        "--threshold-db",
        type=float,
        default=-40.0,
        help="niveau maximal considéré comme silencieux (défaut : -40)",
    )
    parser.add_argument(
        "--minimum-silence",
        type=float,
        default=2.0,
        help="durée minimale d'un silence en secondes (défaut : 2)",
    )
    parser.add_argument(
        "--padding",
        type=float,
        default=0.2,
        help="marge conservée de chaque côté en secondes (défaut : 0.2)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="écrit le plan de coupe au format JSON",
    )
    parser.add_argument(
        "--fcpxml",
        metavar="FICHIER",
        help="génère un nouveau projet FCPXML avec les silences retirés",
    )
    return parser


def format_seconds(value: float) -> str:
    minutes, seconds = divmod(value, 60)
    hours, minutes = divmod(int(minutes), 60)
    if hours:
        return f"{hours:d} h {minutes:02d} min {seconds:05.2f} s"
    if minutes:
        return f"{minutes:d} min {seconds:05.2f} s"
    return f"{seconds:.2f} s"


def render_summary(plan: AutoCutPlan) -> str:
    lines = [
        f"Média : {plan.media}",
        f"Durée : {format_seconds(plan.media_duration)}",
        f"Silences détectés : {len(plan.silence_ranges)}",
        f"Coupes proposées : {len(plan.cut_ranges)}",
        f"Durée retirée : {format_seconds(plan.removed_duration)}",
        f"Durée estimée après coupe : {format_seconds(plan.output_duration)}",
    ]
    for index, cut in enumerate(plan.cut_ranges, start=1):
        lines.append(
            f"  {index}. {format_seconds(cut.start)} → "
            f"{format_seconds(cut.end)} ({format_seconds(cut.duration)})"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        settings = AutoCutSettings(
            threshold_db=args.threshold_db,
            minimum_silence=args.minimum_silence,
            padding=args.padding,
        )
        plan = FFmpegSilenceDetector().analyze(args.media, settings)
        fcpxml_path = write_fcpxml(plan, args.fcpxml) if args.fcpxml else None
    except (ValueError, FileNotFoundError, FFmpegError) as error:
        print(f"Erreur : {error}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(plan.as_dict(), ensure_ascii=False, indent=2))
    else:
        print(render_summary(plan))
        if fcpxml_path:
            print(f"Projet FCPXML créé : {fcpxml_path}")
    return 0
