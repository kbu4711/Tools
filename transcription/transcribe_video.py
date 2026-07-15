# -*- coding: utf-8 -*-
"""
Transcribes speech from video or audio files using OpenAI Whisper.
Usage: python transcribe_video.py <input_path> [--model base] [--language de] [--no-segments]
"""

import argparse
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    import whisper  # type: ignore[import-untyped]
except ModuleNotFoundError as exc:
    install_cmd = f'"{sys.executable}" -m pip install openai-whisper'
    raise SystemExit(
        "Error: 'whisper' module not found for the current interpreter.\n"
        f"Python executable: {sys.executable}\n"
        f"Install it for this interpreter with:\n{install_cmd}\n"
        "If you are in VS Code, use Python: Select Interpreter and pick the same Python shown above."
    ) from exc


SUPPORTED_MEDIA_EXTENSIONS = {
    ".mp4",
    ".mkv",
    ".avi",
    ".mov",
    ".webm",
    ".m4v",
    ".mp3",
    ".wav",
    ".m4a",
    ".flac",
    ".aac",
    ".ogg",
    ".opus",
    ".wma",
}


def ensure_ffmpeg_available() -> None:
    if shutil.which("ffmpeg") is None:
        raise RuntimeError(
            "ffmpeg was not found on PATH. Install ffmpeg and restart the terminal. "
            "On Windows you can run: winget install Gyan.FFmpeg"
        )


def _default_whisper_cache_dir() -> Path:
    xdg_cache_home = os.environ.get("XDG_CACHE_HOME")
    if xdg_cache_home:
        return Path(xdg_cache_home) / "whisper"
    return Path.home() / ".cache" / "whisper"


def is_model_cached(model_name: str) -> bool:
    models = getattr(whisper, "_MODELS", {})
    model_url = models.get(model_name)
    if not model_url:
        return False

    expected_filename = os.path.basename(model_url)
    model_path = _default_whisper_cache_dir() / expected_filename
    return model_path.is_file()


def _validate_media_extension(path: str) -> None:
    ext = os.path.splitext(path)[1].lower()
    if ext not in SUPPORTED_MEDIA_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_MEDIA_EXTENSIONS))
        raise ValueError(f"Unsupported media format '{ext}'. Supported formats: {supported}")


def _collect_media_files(input_path: str) -> list[str]:
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Path not found: {input_path}")

    if os.path.isfile(input_path):
        _validate_media_extension(input_path)
        return [input_path]

    media_files = []
    for name in sorted(os.listdir(input_path)):
        full_path = os.path.join(input_path, name)
        if not os.path.isfile(full_path):
            continue
        ext = os.path.splitext(full_path)[1].lower()
        if ext in SUPPORTED_MEDIA_EXTENSIONS:
            media_files.append(full_path)

    if not media_files:
        supported = ", ".join(sorted(SUPPORTED_MEDIA_EXTENSIONS))
        raise FileNotFoundError(
            f"No supported media files found in directory: {input_path}. Supported formats: {supported}"
        )

    return media_files


def _load_model(model_name: str, offline: bool):
    ensure_ffmpeg_available()

    if offline and not is_model_cached(model_name):
        cache_dir = _default_whisper_cache_dir()
        raise RuntimeError(
            f"Offline mode is enabled, but model '{model_name}' is not cached locally. "
            f"Run once online to download it first. Expected cache dir: {cache_dir}"
        )

    print(f"Loading Whisper model '{model_name}' ...")
    return whisper.load_model(model_name)


def transcribe(media_path: str, model, language: Optional[str] = None) -> dict:
    _validate_media_extension(media_path)
    print(f"Transcribing: {media_path}")
    options = {}
    if language:
        options["language"] = language

    result = model.transcribe(media_path, **options)
    return result


def save_transcript(
    result: dict,
    media_path: str,
    output_dir: Optional[str] = None,
    include_segments: bool = True,
):
    base = os.path.splitext(os.path.basename(media_path))[0]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{base}_transcript_{timestamp}.txt"

    out_dir = output_dir or os.path.dirname(os.path.abspath(media_path))
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, filename)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(result["text"].strip())
        if include_segments:
            f.write("\n\n--- Segments ---\n")
            for seg in result.get("segments", []):
                start = seg["start"]
                end = seg["end"]
                text = seg["text"].strip()
                f.write(f"[{start:07.2f}s - {end:07.2f}s]  {text}\n")

    return out_path


def main():
    parser = argparse.ArgumentParser(description="Transcribe speech from a video/audio file or directory.")
    parser.add_argument(
        "input_path",
        help="Path to one media file or a directory containing media files",
    )
    parser.add_argument(
        "--model",
        default="base",
        choices=["tiny", "base", "small", "medium", "large"],
        help="Whisper model size (default: base)",
    )
    parser.add_argument(
        "--language",
        default=None,
        help="Language code, e.g. 'de', 'en' (auto-detect if omitted)",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory to write transcript files (default: same as input file)",
    )
    parser.add_argument(
        "--print",
        action="store_true",
        dest="print_output",
        help="Also print transcript to stdout",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Do not allow model download. Fails if model is not already cached locally.",
    )
    parser.add_argument(
        "--segments",
        action="store_true",
        dest="include_segments",
        help="Include timestamped segment details in transcript files.",
    )
    parser.add_argument(
        "--no-segments",
        action="store_false",
        dest="include_segments",
        help="Write only plain transcript text without segment details.",
    )
    parser.set_defaults(include_segments=False)
    args = parser.parse_args()

    try:
        media_files = _collect_media_files(args.input_path)
        model = _load_model(args.model, offline=args.offline)
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        raise SystemExit(f"Error: {exc}") from exc

    print(f"Found {len(media_files)} media file(s).")
    success_count = 0
    skipped_missing_count = 0
    failed_count = 0

    for media_path in media_files:
        if not os.path.exists(media_path):
            # File may be removed after initial directory scan.
            print(f"Warning: file no longer exists, skipping: {media_path}")
            skipped_missing_count += 1
            continue

        try:
            result = transcribe(media_path, model=model, language=args.language)
            out_path = save_transcript(
                result,
                media_path,
                output_dir=args.output_dir,
                include_segments=args.include_segments,
            )
            print(f"Transcript saved: {out_path}")
            success_count += 1

            if args.print_output:
                print("\n--- Transcript ---")
                print(result["text"].strip())
        except (FileNotFoundError, OSError, RuntimeError, ValueError) as exc:
            print(f"Warning: failed to transcribe '{media_path}': {exc}")
            failed_count += 1

    print(
        "Done. "
        f"Successful: {success_count}, "
        f"Skipped missing: {skipped_missing_count}, "
        f"Failed: {failed_count}"
    )


if __name__ == "__main__":
    main()
