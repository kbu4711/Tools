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
    language: str = "en",
    output_path: Optional[str] = None,
) -> str:
    if output_path:
        out_path = Path(output_path)
    else:
        base_name = Path(media_path).stem
        lang_code = language.lower() if language else "en"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = Path(output_dir) / f"{base_name}_transcript_{lang_code}_{timestamp}.txt"

    with open(out_path, "w", encoding="utf-8") as handle:
        handle.write(transcript_text.strip())

    return str(out_path)


def _latest_matching_file(directory: Path, pattern: str) -> Optional[Path]:
    matches = sorted(directory.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return matches[0] if matches else None


def _extract_language_from_transcript_filename(filename: str) -> Optional[str]:
    """Extract language code from transcript filename.
    Expected format: basename_transcript_LANG_TIMESTAMP.txt
    Returns the language code (e.g., 'de', 'en') or None if not found."""
    parts = filename.replace('.txt', '').split('_')
    # Format: [..., 'transcript', LANG, TIMESTAMP, ...]
    try:
        transcript_idx = parts.index('transcript')
        if transcript_idx + 1 < len(parts):
            return parts[transcript_idx + 1]
    except (ValueError, IndexError):
        pass
    return None


def _package_single_media(
    media_path: str,
    model: Any,
    output_root: str,
    language: Optional[str],
    no_llm: bool,
    llm_model: str,
    max_slides: int,
    overwrite: bool,
    with_docs: bool,
) -> dict[str, Any]:
    media_stem = _slugify(Path(media_path).stem)
    media_out_dir = Path(output_root) / media_stem
    media_out_dir.mkdir(parents=True, exist_ok=True)
    base_name = Path(media_path).stem

    # Determine which language to search for in existing transcripts
    if language:
        lang_for_search = language.lower()
    else:
        # If no language specified, find any existing transcript and extract its language
        any_transcript = _latest_matching_file(media_out_dir, f"{base_name}_transcript_*_*.txt")
        if any_transcript:
            extracted_lang = _extract_language_from_transcript_filename(any_transcript.name)
            lang_for_search = extracted_lang or "en"
        else:
            lang_for_search = "en"  # Default fallback

    # Search for transcript with matching language
    transcript_existing = _latest_matching_file(media_out_dir, f"{base_name}_transcript_{lang_for_search}_*.txt")
    word_existing = _latest_matching_file(media_out_dir, f"{base_name}_summary_{lang_for_search}_*.docx") if with_docs else None
    ppt_existing = _latest_matching_file(media_out_dir, f"{base_name}_training_slides_{lang_for_search}_*.pptx") if with_docs else None

    transcript_text = ""
    segment_lines: list[str] = []
    transcript_path: str
    transcript_status = "generated"

    if transcript_existing and not overwrite:
        transcript_path = str(transcript_existing)
        transcript_status = "skipped"
        print(f"Step: Transcribe | File: {media_path} | SKIPPED (exists, --overwrite disabled): {transcript_path}")
        transcript_text = transcript_existing.read_text(encoding="utf-8").strip()
        effective_language = lang_for_search  # Use language from existing file
    else:
        transcript_status = "overwritten" if (overwrite and transcript_existing) else "generated"
        print(f"Step: Transcribe | File: {media_path}")
        result = transcribe(media_path, model=model, language=language)
        transcript_text = str(result.get("text", "")).strip()
        segments = result.get("segments", [])
        segment_lines = _format_segment_lines(segments)
        transcript_path = _write_text_transcript(
            transcript_text=transcript_text,
            media_path=media_path,
            output_dir=str(media_out_dir),
            language=language or "en",
            output_path=str(transcript_existing) if (overwrite and transcript_existing) else None,
        )
        effective_language = language or "en"

    if not transcript_text:
        raise RuntimeError("Transcript text is empty. Cannot continue with packaging.")

    summary: Optional[dict[str, Any]] = None
    word_blueprint: Optional[dict[str, Any]] = None
    ppt_blueprint: Optional[dict[str, Any]] = None
    visuals: Optional[dict[str, str]] = None

    def _ensure_summary() -> dict[str, Any]:
        nonlocal summary
        if summary is None:
            summary = build_hybrid_summary(
                transcript_text=transcript_text,
                preferred_language=effective_language,
                use_llm=not no_llm,
                llm_model=llm_model,
            )
        return summary

    def _ensure_word_blueprint() -> Optional[dict[str, Any]]:
        nonlocal word_blueprint
        if no_llm:
            return None
        if word_blueprint is None:
            word_blueprint = generate_word_blueprint(
                transcript_text=transcript_text,
                preferred_language=effective_language,
                llm_model=llm_model,
            )
        return word_blueprint

    def _ensure_ppt_blueprint() -> Optional[dict[str, Any]]:
        nonlocal ppt_blueprint
        if no_llm:
            return None
        if ppt_blueprint is None:
            ppt_blueprint = generate_ppt_blueprint(
                transcript_text=transcript_text,
                preferred_language=effective_language,
                max_slides=max_slides,
                llm_model=llm_model,
            )
        return ppt_blueprint

    def _ensure_visuals() -> dict[str, str]:
        nonlocal visuals
        if visuals is None:
            visuals = generate_visual_assets(
                summary=_ensure_summary(),
                output_dir=str(media_out_dir),
                base_name=Path(media_path).stem,
            )
        return visuals

    word_path: Optional[str] = None
    ppt_path: Optional[str] = None
    word_status = "disabled"
    ppt_status = "disabled"

    if with_docs:
        if word_existing and not overwrite:
            word_path = str(word_existing)
            word_status = "skipped"
            print(f"Step: Generate Word | File: {media_path} | SKIPPED (exists, --overwrite disabled): {word_path}")
        else:
            word_status = "overwritten" if (overwrite and word_existing) else "generated"
            print(f"Step: Generate Word | File: {media_path}")
            word_path = export_summary_to_word(
                summary=_ensure_summary(),
                transcript_text=transcript_text,
                media_path=media_path,
                output_dir=str(media_out_dir),
                segment_lines=segment_lines,
                word_blueprint=_ensure_word_blueprint(),
                output_path=str(word_existing) if (overwrite and word_existing) else None,
            )

        if ppt_existing and not overwrite:
            ppt_path = str(ppt_existing)
            ppt_status = "skipped"
            print(f"Step: Generate PowerPoint | File: {media_path} | SKIPPED (exists, --overwrite disabled): {ppt_path}")
        else:
            ppt_status = "overwritten" if (overwrite and ppt_existing) else "generated"
            print(f"Step: Generate PowerPoint | File: {media_path}")
            ppt_path = export_training_presentation(
                summary=_ensure_summary(),
                media_path=media_path,
                output_dir=str(media_out_dir),
                visual_assets=_ensure_visuals(),
                max_slides=max_slides,
                ppt_blueprint=_ensure_ppt_blueprint(),
                output_path=str(ppt_existing) if (overwrite and ppt_existing) else None,
            )
    else:
        print(f"Step: Generate Word | File: {media_path} | SKIPPED (transcript-only mode)")
        print(f"Step: Generate PowerPoint | File: {media_path} | SKIPPED (transcript-only mode)")

    summary_meta = _ensure_summary() if (summary is not None or (not word_existing or overwrite) or (not ppt_existing or overwrite)) else {}

    return {
        "media_path": os.path.abspath(media_path),
        "language": summary_meta.get("language"),
        "summary_source": summary_meta.get("source"),
        "segment_count": len(segment_lines),
        "artifacts": {
            "transcript": os.path.abspath(transcript_path),
            "word_summary": os.path.abspath(word_path) if word_path else None,
            "slides": os.path.abspath(ppt_path) if ppt_path else None,
            "visuals": {k: os.path.abspath(v) for k, v in (visuals or {}).items()},
        },
        "steps": {
            "transcript": {
                "status": transcript_status,
                "path": os.path.abspath(transcript_path),
            },
            "word": {
                "status": word_status,
                "path": os.path.abspath(word_path) if word_path else None,
            },
            "slides": {
                "status": ppt_status,
                "path": os.path.abspath(ppt_path) if ppt_path else None,
            },
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
        "transcript_only": not bool(args.with_docs),
        "with_docs": bool(args.with_docs),
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
                overwrite=args.overwrite,
                with_docs=args.with_docs,
            )
            manifest["results"].append(package)
            print(f"OK: {media_path}")
            print(f"  transcript: {package['artifacts']['transcript']}")
            if args.with_docs:
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
        "--transcript-only",
        action="store_true",
        default=True,
        help="Generate only transcript files and skip Word/PowerPoint (default mode)",
    )
    parser.add_argument(
        "--with-docs",
        action="store_true",
        help="Also generate Word and PowerPoint artifacts",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing transcript/Word/PowerPoint artifacts for each media file (ignores timestamp in existence check)",
    )
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
