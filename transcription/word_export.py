# -*- coding: utf-8 -*-
"""Word export for detailed training summaries."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
import re

from file_timestamps import set_file_times


def _safe_lines(items: Any) -> list[str]:
    if not isinstance(items, list):
        return []
    return [str(x).strip() for x in items if str(x).strip()]


def _clean_heading(text: str, fallback: str, max_len: int = 90) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip(" .:-")
    if not cleaned:
        return fallback
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 3].rstrip() + "..."


def _extract_segment_text(segment_line: str) -> str:
    # Segment lines are formatted like: [00012.34s - 00018.90s] text
    return re.sub(r"^\[[^\]]+\]\s*", "", segment_line).strip()


def _chunk_list(items: list[str], size: int) -> list[list[str]]:
    return [items[idx : idx + size] for idx in range(0, len(items), size)]


def export_summary_to_word(
    summary: dict[str, Any],
    transcript_text: str,
    media_path: str,
    output_dir: str,
    segment_lines: Optional[list[str]] = None,
    word_blueprint: Optional[dict[str, Any]] = None,
    output_path: Optional[str] = None,
) -> str:
    """Create a structured summary document and return its .docx path."""
    from docx import Document  # type: ignore[import-untyped]

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if output_path:
        out_path = Path(output_path)
    else:
        base_name = Path(media_path).stem
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = out_dir / f"{base_name}_summary_{timestamp}.docx"

    topics = _safe_lines(summary.get("topics", []))
    primary_topic = _clean_heading(topics[0], fallback="Transcript") if topics else "Transcript"
    blueprint = word_blueprint if isinstance(word_blueprint, dict) else {}
    title = str(blueprint.get("title", f"Detailed Summary: {primary_topic}")).strip()
    subtitle = str(blueprint.get("subtitle", f"Document: {Path(media_path).name}")).strip()
    overview_lines = _safe_lines(blueprint.get("overview", [])) or _safe_lines(summary.get("overview", []))
    takeaways = _safe_lines(blueprint.get("takeaways", [])) or _safe_lines(summary.get("goals", []))
    sections = blueprint.get("sections", []) if isinstance(blueprint.get("sections"), list) else []

    doc = Document()
    doc.add_heading(title, level=0)
    doc.add_paragraph(subtitle)
    doc.add_paragraph(f"Generated: {datetime.now().isoformat(timespec='seconds')} | Summary source: {summary.get('source', 'local')}")

    doc.add_heading("Overview", level=1)
    if overview_lines:
        for line in overview_lines:
            doc.add_paragraph(line)
    else:
        doc.add_paragraph("No overview available.")

    doc.add_heading("Key Concepts", level=1)

    if sections:
        for idx, section in enumerate(sections, start=1):
            if not isinstance(section, dict):
                continue
            section_title = _clean_heading(str(section.get("heading", "")), fallback=f"Concept {idx}")
            doc.add_heading(f"{idx}. {section_title}", level=2)
            bullets = _safe_lines(section.get("bullets", []))
            for bullet in bullets:
                doc.add_paragraph(bullet, style="List Bullet")
    else:
        concept_blocks: list[str] = []
        concept_blocks.extend(_safe_lines(summary.get("topics", [])))
        concept_blocks.extend(_safe_lines(summary.get("processes", [])))
        concept_blocks.extend(_safe_lines(summary.get("risks", [])))
        concept_blocks.extend(_safe_lines(summary.get("actions", [])))
        if concept_blocks:
            for idx, concept in enumerate(concept_blocks, start=1):
                section_title = _clean_heading(concept, fallback=f"Concept {idx}")
                doc.add_heading(f"{idx}. {section_title}", level=2)
                doc.add_paragraph(concept)
        else:
            doc.add_paragraph("No key concepts extracted.")

    doc.add_heading("Main Takeaways", level=1)
    takeaway_candidates = takeaways
    if not takeaway_candidates:
        takeaway_candidates = overview_lines
    if takeaway_candidates:
        for line in takeaway_candidates[:8]:
            doc.add_paragraph(line, style="List Bullet")
    else:
        doc.add_paragraph("No takeaways identified.")

    doc.add_heading("Summary (Exam-Style)", level=1)
    glossary = summary.get("glossary", [])
    if isinstance(glossary, list) and glossary:
        for item in glossary[:10]:
            if isinstance(item, dict):
                term = str(item.get("term", "")).strip()
                definition = str(item.get("definition", "")).strip()
                if term:
                    p = doc.add_paragraph(style="List Bullet")
                    p.add_run(f"{term}: ").bold = True
                    p.add_run(definition)

    generated_local = datetime.now().astimezone()
    generated_utc = generated_local.astimezone(timezone.utc)
    core = doc.core_properties
    core.created = generated_utc
    core.modified = generated_utc

    doc.save(str(out_path))
    set_file_times(out_path, generated_local)
    return str(out_path)
