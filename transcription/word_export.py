# -*- coding: utf-8 -*-
"""Word export for transcript-derived Markdown summaries."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import re

try:
    from .file_timestamps import set_file_times
except ImportError:  # pragma: no cover
    from file_timestamps import set_file_times


HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
GRAPHIC_RE = re.compile(r"^###\s+Suggested Graphic:\s*(.+?)\s*$", re.IGNORECASE)
INLINE_MD_RE = re.compile(r"(\*\*[^*]+\*\*|__[^_]+__|\*[^*]+\*|_[^_]+_)")


def _heading_level(line: str) -> tuple[int, str] | None:
    match = HEADING_RE.match(line.strip())
    if not match:
        return None
    return len(match.group(1)), match.group(2).strip()



def _bullet_text(line: str) -> str:
    stripped = line.strip()
    if stripped.startswith("- ") or stripped.startswith("* "):
        return stripped[2:].strip()
    if re.match(r"^\d+\.\s+", stripped):
        return re.sub(r"^\d+\.\s+", "", stripped).strip()
    return stripped



def _find_matching_visuals(visual_assets: list[dict[str, str]], current_heading: str) -> list[dict[str, str]]:
    if not current_heading:
        return []
    matches: list[dict[str, str]] = []
    for item in visual_assets:
        placement = item.get("placement", "")
        if placement and placement.lower() in current_heading.lower():
            matches.append(item)
    return matches


def _add_inline_markdown_runs(paragraph: Any, text: str) -> None:
    # Render common inline Markdown emphasis as native Word run formatting.
    pos = 0
    for match in INLINE_MD_RE.finditer(text):
        start, end = match.span()
        if start > pos:
            paragraph.add_run(text[pos:start])

        token = match.group(0)
        if (token.startswith("**") and token.endswith("**")) or (token.startswith("__") and token.endswith("__")):
            run = paragraph.add_run(token[2:-2])
            run.bold = True
        elif (token.startswith("*") and token.endswith("*")) or (token.startswith("_") and token.endswith("_")):
            run = paragraph.add_run(token[1:-1])
            run.italic = True
        else:
            paragraph.add_run(token)
        pos = end

    if pos < len(text):
        paragraph.add_run(text[pos:])



def export_summary_to_word(markdown_text: str, media_path: str, output_dir: str, visual_assets: list[dict[str, str]] | None = None, output_path: str | None = None) -> str:
    from docx import Document  # type: ignore[import-untyped]
    from docx.shared import Inches  # type: ignore[import-untyped]

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    base_name = Path(media_path).stem
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = Path(output_path) if output_path else out_dir / f"{base_name}_summary_generated_{timestamp}.docx"

    doc = Document()
    current_heading = ""
    inserted_visuals: set[str] = set()
    visual_assets = visual_assets or []

    for raw_line in markdown_text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped:
            continue

        heading = _heading_level(stripped)
        if heading:
            level, text = heading
            current_heading = text
            if level == 1:
                doc.add_heading(text, level=0)
            else:
                doc.add_heading(text, level=min(level - 1, 4))
            for visual in _find_matching_visuals(visual_assets, current_heading):
                path = visual.get("path", "")
                if path and path not in inserted_visuals and Path(path).exists():
                    doc.add_picture(path, width=Inches(6.5))
                    inserted_visuals.add(path)
            continue

        if GRAPHIC_RE.match(stripped):
            doc.add_heading(stripped.replace("### ", ""), level=3)
            continue

        if stripped.startswith("- ") or stripped.startswith("* ") or re.match(r"^\d+\.\s+", stripped):
            bullet_paragraph = doc.add_paragraph(style="List Bullet")
            _add_inline_markdown_runs(bullet_paragraph, _bullet_text(stripped))
            continue

        paragraph = doc.add_paragraph()
        _add_inline_markdown_runs(paragraph, stripped)

    for visual in visual_assets:
        path = visual.get("path", "")
        if path and path not in inserted_visuals and Path(path).exists():
            doc.add_heading(visual.get("title", "Suggested Graphic"), level=2)
            doc.add_picture(path, width=Inches(6.5))
            inserted_visuals.add(path)

    generated_local = datetime.now().astimezone()
    generated_utc = generated_local.astimezone(timezone.utc)
    core = doc.core_properties
    core.created = generated_utc
    core.modified = generated_utc
    try:
        doc.save(str(out_path))
    except PermissionError:
        fallback_path = out_dir / f"{base_name}_summary_generated_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
        doc.save(str(fallback_path))
        out_path = fallback_path
    set_file_times(out_path, generated_local)
    return str(out_path)
