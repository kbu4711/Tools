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
from urllib.parse import unquote, urlparse

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

SUPPORTED_VIDEO_EXTENSIONS = {
    ".mp4",
    ".mkv",
    ".avi",
    ".mov",
    ".webm",
    ".m4v",
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


def _normalize_video_format(video_format: Optional[str]) -> Optional[str]:
    if not video_format:
        return None
    normalized = video_format.strip().lower()
    if not normalized:
        return None
    if not normalized.startswith("."):
        normalized = f".{normalized}"
    if normalized not in SUPPORTED_VIDEO_EXTENSIONS:
        supported = ", ".join(sorted(ext.lstrip(".") for ext in SUPPORTED_VIDEO_EXTENSIONS))
        raise ValueError(
            f"Unsupported video format filter '{video_format}'. Supported video formats: {supported}"
        )
    return normalized


def _onedrive_roots() -> list[Path]:
    roots: list[Path] = []
    for var_name in ("OneDrive", "OneDriveCommercial", "OneDriveConsumer"):
        value = os.environ.get(var_name, "").strip()
        if value:
            roots.append(Path(value))

    home = Path.home()
    default_candidates = [home / "OneDrive"]
    for candidate in default_candidates:
        if candidate.exists():
            roots.append(candidate)

    # De-duplicate while preserving order.
    unique_roots: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        key = str(root.resolve()) if root.exists() else str(root)
        if key in seen:
            continue
        seen.add(key)
        unique_roots.append(root)
    return unique_roots


def _resolve_onedrive_input_path(input_path: str) -> str:
    parsed = urlparse(input_path)
    if parsed.scheme not in {"http", "https"}:
        return input_path

    host = (parsed.netloc or "").lower()
    decoded_path = unquote(parsed.path or "")
    path_lower = decoded_path.lower()
    looks_like_onedrive_link = (
        "onedrive" in host
        or "sharepoint" in host
        or "/:f:/r/" in path_lower
        or "/:u:/r/" in path_lower
        or "/personal/" in path_lower
        or "/sites/" in path_lower
    )
    if not looks_like_onedrive_link:
        return input_path

    marker = "/r/"
    if marker in decoded_path:
        decoded_path = decoded_path.split(marker, 1)[1]
    decoded_path = decoded_path.strip("/")
    if not decoded_path:
        raise FileNotFoundError(
            "OneDrive URL konnte nicht in einen lokalen, synchronisierten Ordner aufgeloest werden. "
            "Bitte pruefe die URL oder verwende den lokalen OneDrive-Pfad direkt."
        )

    relative_parts = [part for part in decoded_path.split("/") if part]

    # Reduce URL-specific prefixes to path fragments that are likely to exist locally.
    lowered_parts = [part.lower() for part in relative_parts]
    for anchor in ("documents", "shared documents"):
        if anchor in lowered_parts:
            idx = lowered_parts.index(anchor)
            relative_parts = [relative_parts[idx]] + relative_parts[idx + 1 :]
            lowered_parts = [part.lower() for part in relative_parts]
            break

    if "personal" in lowered_parts and len(relative_parts) >= 3:
        idx = lowered_parts.index("personal")
        relative_parts = relative_parts[idx + 2 :]
        lowered_parts = [part.lower() for part in relative_parts]

    if "sites" in lowered_parts and len(relative_parts) >= 3:
        idx = lowered_parts.index("sites")
        relative_parts = relative_parts[idx + 2 :]
        lowered_parts = [part.lower() for part in relative_parts]

    roots = _onedrive_roots()
    candidate_variants: list[list[str]] = [relative_parts]
    if lowered_parts and lowered_parts[0] == "documents":
        candidate_variants.append(relative_parts[1:])
    if lowered_parts and lowered_parts[0] == "shared documents":
        candidate_variants.append(relative_parts[1:])

    for root in roots:
        for variant in candidate_variants:
            if not variant:
                continue
            candidate = root.joinpath(*variant)
            if candidate.exists():
                return str(candidate)

    # Fallback: suffix-based lookup inside OneDrive roots for synced folders with custom names.
    tail_parts = [part for part in relative_parts if part]
    if tail_parts:
        leaf_name = tail_parts[-1]
        # Try longest suffix first, then relax (e.g. Videos/Clipchamp, then Clipchamp).
        tail_suffixes: list[list[str]] = []
        tail_lower_full = [part.lower() for part in tail_parts]
        for start_idx in range(0, len(tail_lower_full)):
            suffix = tail_lower_full[start_idx:]
            if suffix:
                tail_suffixes.append(suffix)

        for root in roots:
            try:
                matches = root.rglob(leaf_name)
            except Exception:
                continue
            for match in matches:
                if not match.exists():
                    continue
                parts_lower = [part.lower() for part in match.parts]
                for suffix in tail_suffixes:
                    if len(parts_lower) < len(suffix):
                        continue
                    if parts_lower[-len(suffix):] == suffix:
                        return str(match)

    root_hint = ", ".join(str(item) for item in roots) if roots else "(keine OneDrive-Roots gefunden)"
    raise FileNotFoundError(
        "OneDrive URL wurde erkannt, aber kein passender lokaler, synchronisierter Ordner gefunden. "
        f"Gepruefte OneDrive-Roots: {root_hint}. "
        "Bitte sicherstellen, dass der Ordner lokal synchronisiert ist oder den lokalen Pfad direkt angeben."
    )


def _collect_media_files(input_path: str, video_format: Optional[str] = None) -> list[str]:
    normalized_video_format = _normalize_video_format(video_format)
    input_path = _resolve_onedrive_input_path(input_path)

    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Path not found: {input_path}")

    if os.path.isfile(input_path):
        _validate_media_extension(input_path)
        if normalized_video_format:
            ext = os.path.splitext(input_path)[1].lower()
            if ext != normalized_video_format:
                raise ValueError(
                    f"Input file format '{ext}' does not match requested --video-format '{normalized_video_format}'."
                )
        return [input_path]

    media_files = []
    for root, _, files in os.walk(input_path):
        for name in sorted(files):
            full_path = os.path.join(root, name)
            ext = os.path.splitext(full_path)[1].lower()
            if normalized_video_format and ext != normalized_video_format:
                continue
            if ext in SUPPORTED_MEDIA_EXTENSIONS:
                media_files.append(full_path)

    if not media_files:
        if normalized_video_format:
            raise FileNotFoundError(
                f"No media files with format '{normalized_video_format}' found in directory: {input_path}"
            )
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
        "--video-format",
        default=None,
        help="Optional video format filter for directory scans, e.g. mp4",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory to write transcript files",
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
        media_files = _collect_media_files(args.input_path, video_format=args.video_format)
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
