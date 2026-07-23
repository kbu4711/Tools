# -*- coding: utf-8 -*-
"""Video-only transcription by sampling frames and describing visual content with an LLM."""

from __future__ import annotations

import base64
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Optional

from github_models import chat_completion, github_models_enabled


def _probe_duration_seconds(media_path: str) -> float:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        media_path,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"ffprobe failed for '{media_path}': {proc.stderr.strip() or proc.stdout.strip()}")

    try:
        payload = json.loads(proc.stdout)
        duration_raw = payload.get("format", {}).get("duration", 0)
        duration = float(duration_raw)
    except Exception as exc:
        raise RuntimeError(f"Could not parse ffprobe duration for '{media_path}'.") from exc

    if duration <= 0:
        return 1.0
    return duration


def _sample_timestamps(duration_seconds: float, interval_seconds: int, max_frames: int) -> list[float]:
    if interval_seconds <= 0:
        interval_seconds = 8
    if max_frames <= 0:
        max_frames = 24

    timestamps: list[float] = []
    current = 0.0
    while current <= duration_seconds and len(timestamps) < max_frames:
        timestamps.append(round(current, 2))
        current += float(interval_seconds)

    if timestamps and timestamps[-1] < duration_seconds and len(timestamps) < max_frames:
        timestamps.append(round(duration_seconds, 2))

    if not timestamps:
        timestamps = [0.0]
    return timestamps


def _extract_frame(media_path: str, timestamp: float, out_path: Path) -> None:
    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        str(timestamp),
        "-i",
        media_path,
        "-frames:v",
        "1",
        "-q:v",
        "2",
        str(out_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0 or not out_path.exists():
        message = proc.stderr.strip() or proc.stdout.strip()
        raise RuntimeError(f"ffmpeg frame extraction failed at {timestamp:.2f}s: {message}")


def _to_data_uri(image_path: Path) -> str:
    raw = image_path.read_bytes()
    encoded = base64.b64encode(raw).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def _describe_frame(data_uri: str, timestamp: float, llm_model: str, language: Optional[str]) -> str:
    target_language = language or "auto"
    instruction = (
        "Describe this video frame for a timeline transcript. "
        "Focus on visible actions, objects, text on screen, and scene context. "
        "Keep it factual, concise (1-2 sentences), and avoid speculation. "
        f"Preferred language: {target_language}."
    )
    messages: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": "You convert video frames into concise visual transcript notes.",
        },
        {
            "role": "user",
            "content": [
                {"type": "text", "text": instruction},
                {"type": "image_url", "image_url": {"url": data_uri}},
            ],
        },
    ]
    text = chat_completion(model=llm_model, messages=messages, temperature=0.1, max_tokens=220)
    if not text:
        return "No reliable frame description available."
    return text.strip().replace("\n", " ")


def _merge_frame_notes(
    frame_notes: list[dict[str, Any]],
    llm_model: str,
    language: Optional[str],
) -> str:
    timeline = "\n".join(
        f"[{note['start']:07.2f}s - {note['end']:07.2f}s] {note['text']}" for note in frame_notes
    )
    target_language = language or "auto"
    messages: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": (
                "You are creating a visual transcript from frame-by-frame notes. "
                "Do not invent events beyond the notes."
            ),
        },
        {
            "role": "user",
            "content": (
                "Create a coherent visual transcript from the timeline notes below. "
                "Use short paragraphs in chronological order and keep details concrete. "
                f"Preferred language: {target_language}.\n\n{timeline}"
            ),
        },
    ]
    merged = chat_completion(model=llm_model, messages=messages, temperature=0.2, max_tokens=1800)
    if merged:
        return merged.strip()
    return timeline


def transcribe_video_visual(
    media_path: str,
    llm_model: str,
    language: Optional[str] = None,
    interval_seconds: int = 8,
    max_frames: int = 24,
) -> dict[str, Any]:
    if not github_models_enabled():
        raise RuntimeError(
            "Visual transcription requires GitHub Models credentials (GITHUB_MODELS_TOKEN/GITHUB_TOKEN/GH_TOKEN)."
        )

    duration_seconds = _probe_duration_seconds(media_path)
    timestamps = _sample_timestamps(
        duration_seconds=duration_seconds,
        interval_seconds=interval_seconds,
        max_frames=max_frames,
    )

    frame_notes: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="video_frames_") as tmp_dir:
        tmp_path = Path(tmp_dir)
        for timestamp in timestamps:
            frame_path = tmp_path / f"frame_{timestamp:010.2f}.jpg"
            _extract_frame(media_path, timestamp, frame_path)
            data_uri = _to_data_uri(frame_path)
            note = _describe_frame(
                data_uri=data_uri,
                timestamp=timestamp,
                llm_model=llm_model,
                language=language,
            )
            frame_notes.append(
                {
                    "start": float(timestamp),
                    "end": min(float(timestamp + interval_seconds), duration_seconds),
                    "text": note,
                }
            )

    transcript_text = _merge_frame_notes(
        frame_notes=frame_notes,
        llm_model=llm_model,
        language=language,
    )

    return {
        "text": transcript_text,
        "segments": frame_notes,
        "metadata": {
            "mode": "video",
            "duration_seconds": duration_seconds,
            "interval_seconds": interval_seconds,
            "frame_count": len(frame_notes),
        },
    }
