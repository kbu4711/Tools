# -*- coding: utf-8 -*-
"""End-to-end pipeline: transcript -> detailed Word summary -> training slides."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from github_models import github_models_enabled, github_models_model
from ppt_export import export_training_presentation
from summary_builder import build_hybrid_summary, generate_ppt_blueprint, generate_word_blueprint
from transcribe_video import _collect_media_files, _load_model, transcribe
from visuals import generate_visual_assets
from word_export import export_summary_to_word


def _format_segment_lines(segments: Any) -> list[str]:
    if not isinstance(segments, list):
        return []

    output: list[str] = []
    for seg in segments:
        if not isinstance(seg, dict):
            continue
        try:
            start = float(seg.get("start", 0.0))
            end = float(seg.get("end", 0.0))
        except Exception:
            start = 0.0
            end = 0.0
        text = str(seg.get("text", "")).strip()
        output.append(f"[{start:07.2f}s - {end:07.2f}s] {text}")
    return output


def _slugify(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-")


def _write_text_transcript(
    transcript_text: str,
    media_path: str,
    output_dir: str,
) -> str:
    base_name = Path(media_path).stem
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = Path(output_dir) / f"{base_name}_transcript_{timestamp}.txt"

    with open(out_path, "w", encoding="utf-8") as handle:
        handle.write(transcript_text.strip())

    return str(out_path)


def _package_single_media(
    media_path: str,
    model: Any,
    output_root: str,
    language: Optional[str],
    no_llm: bool,
    llm_model: str,
    max_slides: int,
) -> dict[str, Any]:
    media_stem = _slugify(Path(media_path).stem)
    media_out_dir = Path(output_root) / media_stem
    media_out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Step: Transcribe | File: {media_path}")

    result = transcribe(media_path, model=model, language=language)
    transcript_text = str(result.get("text", "")).strip()
    segments = result.get("segments", [])
    segment_lines = _format_segment_lines(segments)

    transcript_path = _write_text_transcript(
        transcript_text=transcript_text,
        media_path=media_path,
        output_dir=str(media_out_dir),
    )

    summary = build_hybrid_summary(
        transcript_text=transcript_text,
        preferred_language=language,
        use_llm=not no_llm,
        llm_model=llm_model,
    )

    word_blueprint = None if no_llm else generate_word_blueprint(
        transcript_text=transcript_text,
        preferred_language=language,
        llm_model=llm_model,
    )
    ppt_blueprint = None if no_llm else generate_ppt_blueprint(
        transcript_text=transcript_text,
        preferred_language=language,
        max_slides=max_slides,
        llm_model=llm_model,
    )

    visuals = generate_visual_assets(
        summary=summary,
        output_dir=str(media_out_dir),
        base_name=Path(media_path).stem,
    )

    print(f"Step: Generate Word | File: {media_path}")
    word_path = export_summary_to_word(
        summary=summary,
        transcript_text=transcript_text,
        media_path=media_path,
        output_dir=str(media_out_dir),
        segment_lines=segment_lines,
        word_blueprint=word_blueprint,
    )

    print(f"Step: Generate PowerPoint | File: {media_path}")
    ppt_path = export_training_presentation(
        summary=summary,
        media_path=media_path,
        output_dir=str(media_out_dir),
        visual_assets=visuals,
        max_slides=max_slides,
        ppt_blueprint=ppt_blueprint,
    )

    return {
        "media_path": os.path.abspath(media_path),
        "language": summary.get("language"),
        "summary_source": summary.get("source"),
        "segment_count": len(segment_lines),
        "artifacts": {
            "transcript": os.path.abspath(transcript_path),
            "word_summary": os.path.abspath(word_path),
            "slides": os.path.abspath(ppt_path),
            "visuals": {k: os.path.abspath(v) for k, v in visuals.items()},
        },
    }


def build_training_package(args: argparse.Namespace) -> dict[str, Any]:
    media_files = _collect_media_files(args.input_path)
    model = _load_model(args.model, offline=args.offline)
    llm_model = args.llm_model or github_models_model()
    llm_model_source = "cli" if args.llm_model else "env/default"

    if args.no_llm:
        print("LLM: disabled (--no-llm)")
    elif github_models_enabled():
        print(f"LLM: enabled | Model: {llm_model} | Source: {llm_model_source}")
    else:
        print(f"LLM: requested but no GitHub Models token found | Fallback: local generation | Requested model: {llm_model} | Source: {llm_model_source}")

    if args.output_dir:
        output_root = Path(args.output_dir)
    else:
        input_abs = Path(args.input_path).resolve()
        output_root = input_abs.parent / "training_package_output"

    output_root.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, Any] = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "input_path": os.path.abspath(args.input_path),
        "model": args.model,
        "offline": bool(args.offline),
        "llm_enabled": not bool(args.no_llm),
        "llm_model": llm_model,
        "max_slides": int(args.max_slides),
        "results": [],
        "failed": [],
    }

    for media_path in media_files:
        try:
            package = _package_single_media(
                media_path=media_path,
                model=model,
                output_root=str(output_root),
                language=args.language,
                no_llm=args.no_llm,
                llm_model=llm_model,
                max_slides=args.max_slides,
            )
            manifest["results"].append(package)
            print(f"OK: {media_path}")
            print(f"  transcript: {package['artifacts']['transcript']}")
            print(f"  word:       {package['artifacts']['word_summary']}")
            print(f"  slides:     {package['artifacts']['slides']}")
        except Exception as exc:  # pragma: no cover - top-level resilience
            manifest["failed"].append({"media_path": os.path.abspath(media_path), "error": str(exc)})
            print(f"FAILED: {media_path}: {exc}")

    manifest_name = f"training_package_manifest_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    manifest_path = output_root / manifest_name
    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)

    print(f"Manifest: {manifest_path}")
    manifest["manifest_path"] = str(manifest_path.resolve())
    return manifest


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build transcript, detailed Word summary, and training slides from media input."
    )
    parser.add_argument("input_path", help="Path to media file or folder")
    parser.add_argument(
        "--model",
        default="base",
        choices=["tiny", "base", "small", "medium", "large"],
        help="Whisper model size (default: base)",
    )
    parser.add_argument("--language", default=None, help="Optional language override, e.g. de or en")
    parser.add_argument("--output-dir", default=None, help="Root output directory for generated artifacts")
    parser.add_argument("--offline", action="store_true", help="Do not allow model download")
    parser.add_argument("--max-slides", type=int, default=12, help="Maximum number of slides to keep")
    parser.add_argument("--theme", default="standard", help="Reserved parameter for future slide themes")
    parser.add_argument("--no-llm", action="store_true", help="Disable LLM refinement and use local summary only")
    parser.add_argument(
        "--llm-model",
        default=None,
        help="GitHub Models model ID (overrides GITHUB_MODELS_MODEL from .env), e.g. openai/gpt-5",
    )
    return parser


def main() -> None:
    parser = _build_arg_parser()
    args = parser.parse_args()

    _ = args.theme  # Reserved for compatibility with the agreed CLI contract.
    build_training_package(args)


if __name__ == "__main__":
    main()
