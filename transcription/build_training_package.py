# -*- coding: utf-8 -*-
"""End-to-end pipeline: transcript generation plus optional Word and PowerPoint artifacts."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from github_models import github_models_enabled, github_models_model
from ppt_export import export_training_presentation
from summary_builder import generate_single_slide_content, generate_word_document_content
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


def _write_markdown_summary(
    markdown_text: str,
    media_path: str,
    output_dir: str,
    output_path: Optional[str] = None,
) -> str:
    if output_path:
        out_path = Path(output_path)
    else:
        base_name = Path(media_path).stem
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = Path(output_dir) / f"{base_name}_summary_{timestamp}.md"

    with open(out_path, "w", encoding="utf-8") as handle:
        handle.write(markdown_text.strip())

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
    overwrite: bool,
    with_docs: bool,
    no_llm: bool,
    llm_model: str,
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

    transcript_existing = _latest_matching_file(media_out_dir, f"{base_name}_transcript_{lang_for_search}_*.txt")
    word_existing = _latest_matching_file(media_out_dir, f"{base_name}_summary_*_*.docx") if with_docs else None
    ppt_existing = _latest_matching_file(media_out_dir, f"{base_name}_training_slides_*_*.pptx") if with_docs else None

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

    word_path: Optional[str] = None
    ppt_path: Optional[str] = None
    markdown_path: Optional[str] = None
    ppt_markdown_path: Optional[str] = None
    word_status = "disabled"
    ppt_status = "disabled"
    visual_assets: list[dict[str, str]] = []

    llm_available = (not no_llm) and github_models_enabled()
    if with_docs:
        if not llm_available:
            word_status = "skipped"
            ppt_status = "skipped"
            print(f"Step: Generate Word | File: {media_path} | SKIPPED (no LLM available)")
            print(f"Step: Generate PowerPoint | File: {media_path} | SKIPPED (no LLM available)")
        else:
            try:
                word_markdown_payload = generate_word_document_content(
                    transcript_text=transcript_text,
                    llm_model=llm_model,
                )
                ppt_markdown_payload = generate_single_slide_content(
                    transcript_text=transcript_text,
                    llm_model=llm_model,
                )

                word_markdown = str((word_markdown_payload or {}).get("markdown", "")).strip()
                ppt_markdown = str((ppt_markdown_payload or {}).get("markdown", "")).strip()

                if word_markdown:
                    try:
                        markdown_path = _write_markdown_summary(
                            markdown_text=word_markdown,
                            media_path=media_path,
                            output_dir=str(media_out_dir),
                        )
                        print(f"Step: Export Markdown | File: {media_path}")
                        visual_assets = generate_visual_assets(
                            markdown_text=word_markdown,
                            output_dir=str(media_out_dir),
                            base_name=base_name,
                        )
                        word_status = "overwritten" if (overwrite and word_existing) else "generated"
                        print(f"Step: Generate Word | File: {media_path}")
                        word_path = export_summary_to_word(
                            markdown_text=word_markdown,
                            media_path=media_path,
                            output_dir=str(media_out_dir),
                            visual_assets=visual_assets,
                            output_path=str(word_existing) if (overwrite and word_existing) else None,
                        )
                    except Exception as word_exc:  # pragma: no cover
                        word_status = "failed"
                        print(f"Step: Generate Word | File: {media_path} | FAILED: {word_exc}")
                else:
                    word_status = "skipped"
                    print(f"Step: Generate Word | File: {media_path} | SKIPPED (LLM returned no content)")

                if ppt_markdown:
                    try:
                        # Save PPT markdown as separate file
                        ppt_markdown_path = _write_markdown_summary(
                            markdown_text=ppt_markdown,
                            media_path=media_path,
                            output_dir=str(media_out_dir),
                            output_path=str(media_out_dir / f"{base_name}_slides_spec_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"),
                        )
                        print(f"Step: Export PowerPoint Specification | File: {media_path}")
                        
                        ppt_status = "overwritten" if (overwrite and ppt_existing) else "generated"
                        print(f"Step: Generate PowerPoint | File: {media_path}")
                        ppt_path = export_training_presentation(
                            markdown_text=ppt_markdown,
                            media_path=media_path,
                            output_dir=str(media_out_dir),
                            output_path=str(ppt_existing) if (overwrite and ppt_existing) else None,
                        )
                    except Exception as ppt_exc:  # pragma: no cover
                        ppt_status = "failed"
                        print(f"Step: Generate PowerPoint | File: {media_path} | FAILED: {ppt_exc}")
                        import traceback
                        print(f"Traceback: {traceback.format_exc()}")
                else:
                    ppt_status = "skipped"
                    print(f"Step: Generate PowerPoint | File: {media_path} | SKIPPED (LLM returned no content)")
            except Exception as llm_exc:  # pragma: no cover
                word_status = "failed"
                ppt_status = "failed"
                print(f"Step: LLM generation failed | File: {media_path} | ERROR: {llm_exc}")
                print(f"Step: Generate Word | File: {media_path} | SKIPPED (LLM failed)")
                print(f"Step: Generate PowerPoint | File: {media_path} | SKIPPED (LLM failed)")

    return {
        "media_path": os.path.abspath(media_path),
        "language": effective_language,
        "segment_count": len(segment_lines),
        "artifacts": {
            "transcript": os.path.abspath(transcript_path),
            "markdown_summary": os.path.abspath(markdown_path) if markdown_path else None,
            "markdown_ppt": os.path.abspath(ppt_markdown_path) if ppt_markdown_path else None,
            "word_summary": os.path.abspath(word_path) if word_path else None,
            "slides": os.path.abspath(ppt_path) if ppt_path else None,
            "visuals": [
                {
                    "title": item.get("title", ""),
                    "placement": item.get("placement", ""),
                    "path": os.path.abspath(item.get("path", "")) if item.get("path") else "",
                }
                for item in visual_assets
            ],
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
        print(f"LLM: requested but no GitHub Models token found | Word/PPT will be skipped | Requested model: {llm_model} | Source: {llm_model_source}")

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
        "with_docs": bool(args.with_docs),
        "llm_enabled": not bool(args.no_llm),
        "llm_model": llm_model,
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
                overwrite=args.overwrite,
                with_docs=args.with_docs,
                no_llm=args.no_llm,
                llm_model=llm_model,
            )
            manifest["results"].append(package)
            print(f"OK: {media_path}")
            print(f"  transcript: {package['artifacts']['transcript']}")
            if args.with_docs:
                markdown = package['artifacts'].get('markdown_summary')
                if markdown:
                    print(f"  markdown:   {markdown}")
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
        description="Build transcript files and optional Word/PowerPoint artifacts from media input."
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
    parser.add_argument("--with-docs", action="store_true", help="Also generate Word and PowerPoint artifacts from the transcript via LLM")
    parser.add_argument("--no-llm", action="store_true", help="Disable LLM generation and skip Word/PowerPoint artifacts")
    parser.add_argument("--llm-model", default=None, help="GitHub Models model ID (overrides GITHUB_MODELS_MODEL from .env)")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing transcript/Word/PowerPoint artifacts for each media file (ignores timestamp in existence check)",
    )
    return parser


def main() -> None:
    parser = _build_arg_parser()
    args = parser.parse_args()
    build_training_package(args)


if __name__ == "__main__":
    main()
