# -*- coding: utf-8 -*-
"""PowerPoint export for training slide decks with visuals and drawings."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

from file_timestamps import set_file_times


def _as_lines(value: Any, limit: int = 5) -> list[str]:
    if not isinstance(value, list):
        return []
    lines = [str(v).strip() for v in value if str(v).strip()]
    return lines[:limit]


def _as_labels(value: Any, limit: int = 6) -> list[str]:
    if not isinstance(value, list):
        return []
    labels = [str(v).strip() for v in value if str(v).strip()]
    return labels[:limit]


def _theme_colors(rgb_color):
    return {
        "navy": rgb_color(11, 31, 58),
        "blue": rgb_color(23, 87, 166),
        "blue_soft": rgb_color(220, 235, 255),
        "text": rgb_color(17, 24, 39),
        "muted": rgb_color(91, 103, 122),
        "line": rgb_color(216, 226, 236),
        "callout_fill": rgb_color(255, 247, 237),
        "callout_text": rgb_color(154, 52, 18),
        "white": rgb_color(255, 255, 255),
    }


def _apply_run_style(paragraph, *, font_name=None, size_pt=None, color=None, bold=False):
    if not paragraph.runs:
        paragraph.text = paragraph.text or ""
    if not paragraph.runs:
        return
    run = paragraph.runs[0]
    if font_name:
        run.font.name = font_name
    if size_pt is not None:
        from pptx.util import Pt  # type: ignore[import-untyped]

        run.font.size = Pt(size_pt)
    if color is not None:
        run.font.color.rgb = color
    run.font.bold = bold


def _add_subtitle(slide, subtitle: str, left, top, width, height, inches, colors):
    if not subtitle:
        return
    box = slide.shapes.add_textbox(inches(left), inches(top), inches(width), inches(height))
    frame = box.text_frame
    frame.text = subtitle
    paragraph = frame.paragraphs[0]
    _apply_run_style(paragraph, size_pt=8.7, color=colors["muted"])


def _add_footer(slide, slide_number: int, inches, colors):
    line = slide.shapes.add_shape(1, inches(0.4), inches(7.0), inches(8.5), inches(0.01))
    line.fill.solid()
    line.fill.fore_color.rgb = colors["line"]
    line.line.color.rgb = colors["line"]
    foot = slide.shapes.add_textbox(inches(8.9), inches(7.03), inches(0.4), inches(0.2))
    foot.text_frame.text = str(slide_number)
    _apply_run_style(foot.text_frame.paragraphs[0], size_pt=10, color=colors["muted"])


def _add_callout(slide, callout: str, inches, colors):
    if not callout:
        return
    shape = slide.shapes.add_textbox(inches(0.55), inches(6.1), inches(8.5), inches(0.55))
    shape.fill.solid()
    shape.fill.fore_color.rgb = colors["callout_fill"]
    shape.line.color.rgb = colors["line"]
    shape.text_frame.text = callout
    _apply_run_style(shape.text_frame.paragraphs[0], size_pt=10.5, color=colors["callout_text"], bold=True)


def _style_slide_title(slide, text: str, colors, title_slide: bool = False):
    _set_slide_title(slide, text)
    title_shape = slide.shapes.title
    if title_shape is None or not title_shape.has_text_frame:
        return
    paragraph = title_shape.text_frame.paragraphs[0]
    _apply_run_style(
        paragraph,
        font_name="Aptos Display",
        size_pt=34 if title_slide else 24,
        color=colors["white"] if title_slide else colors["navy"],
        bold=True,
    )


def _add_title_background(slide, inches, colors):
    bg = slide.shapes.add_shape(1, inches(0), inches(0), inches(10), inches(7.5))
    bg.fill.solid()
    bg.fill.fore_color.rgb = colors["navy"]
    bg.line.color.rgb = colors["navy"]
    slide.shapes._spTree.remove(bg._element)  # pylint: disable=protected-access
    slide.shapes._spTree.insert(2, bg._element)  # pylint: disable=protected-access


def _render_process_labels(slide, labels: list[str], inches, colors):
    if not labels:
        return
    count = min(len(labels), 5)
    start_left = 0.7
    width = 1.45
    gap = 0.25
    top = 2.25
    for idx in range(count):
        left = start_left + idx * (width + gap)
        box = slide.shapes.add_textbox(inches(left), inches(top), inches(width), inches(0.7))
        box.fill.solid()
        box.fill.fore_color.rgb = colors["blue_soft"]
        box.line.color.rgb = colors["blue"]
        box.text_frame.text = labels[idx]
        _apply_run_style(box.text_frame.paragraphs[0], size_pt=13, color=colors["navy"], bold=True)
        if idx < count - 1:
            arrow = slide.shapes.add_shape(13, inches(left + width), inches(top + 0.18), inches(0.22), inches(0.22))
            arrow.fill.solid()
            arrow.fill.fore_color.rgb = colors["blue"]


def _render_comparison(slide, labels: list[str], bullets: list[str], inches, colors):
    headers = labels[:2] if len(labels) >= 2 else ["Variante A", "Variante B"]
    left_box = slide.shapes.add_textbox(inches(0.65), inches(2.1), inches(3.85), inches(3.3))
    right_box = slide.shapes.add_textbox(inches(4.8), inches(2.1), inches(3.85), inches(3.3))
    for box, header in ((left_box, headers[0]), (right_box, headers[1])):
        box.fill.solid()
        box.fill.fore_color.rgb = colors["blue_soft"]
        box.line.color.rgb = colors["line"]
        box.text_frame.text = header
        _apply_run_style(box.text_frame.paragraphs[0], size_pt=15, color=colors["navy"], bold=True)
    left_lines = bullets[0::2][:4]
    right_lines = bullets[1::2][:4]
    for target, lines in ((left_box, left_lines), (right_box, right_lines)):
        for line in lines:
            paragraph = target.text_frame.add_paragraph()
            paragraph.text = line
            paragraph.level = 0
            _apply_run_style(paragraph, size_pt=10.5, color=colors["muted"])


def _render_concept_grid(slide, labels: list[str], bullets: list[str], inches, colors):
    grid_labels = labels[:6] if labels else [f"Konzept {idx}" for idx in range(1, min(len(bullets), 6) + 1)]
    for idx, label in enumerate(grid_labels):
        row = idx // 2
        col = idx % 2
        left = 0.65 + col * 4.2
        top = 2.0 + row * 1.35
        box = slide.shapes.add_textbox(inches(left), inches(top), inches(3.75), inches(1.0))
        box.fill.solid()
        box.fill.fore_color.rgb = colors["blue_soft"]
        box.line.color.rgb = colors["line"]
        box.text_frame.text = label
        _apply_run_style(box.text_frame.paragraphs[0], size_pt=12, color=colors["navy"], bold=True)
        if idx < len(bullets):
            paragraph = box.text_frame.add_paragraph()
            paragraph.text = bullets[idx]
            paragraph.level = 0
            _apply_run_style(paragraph, size_pt=10.5, color=colors["muted"])


def _render_agenda_cards(slide, bullets: list[str], inches, colors):
    cards = bullets[:4]
    subtitles = bullets[4:8]
    for idx, title in enumerate(cards, start=1):
        top = 1.9 + (idx - 1) * 1.05
        number = slide.shapes.add_shape(1, inches(0.75), inches(top), inches(0.42), inches(0.42))
        number.fill.solid()
        number.fill.fore_color.rgb = colors["blue"]
        number.line.color.rgb = colors["blue"]
        number.text_frame.text = str(idx)
        _apply_run_style(number.text_frame.paragraphs[0], size_pt=10, color=colors["white"], bold=True)

        card = slide.shapes.add_textbox(inches(1.3), inches(top - 0.04), inches(7.6), inches(0.82))
        card.fill.solid()
        card.fill.fore_color.rgb = colors["white"]
        card.line.color.rgb = colors["line"]
        card.text_frame.text = title
        _apply_run_style(card.text_frame.paragraphs[0], size_pt=15, color=colors["navy"], bold=True)
        subtitle = subtitles[idx - 1] if idx - 1 < len(subtitles) else ""
        if subtitle:
            p = card.text_frame.add_paragraph()
            p.text = subtitle
            _apply_run_style(p, size_pt=10.5, color=colors["muted"])


def _add_bullet_slide(prs, title: str, lines: list[str]):
    slide = prs.slides.add_slide(prs.slide_layouts[1])
    _set_slide_title(slide, title)
    text_frame = slide.placeholders[1].text_frame
    text_frame.clear()

    if not lines:
        lines = ["No content available."]

    for idx, line in enumerate(lines):
        if idx == 0:
            text_frame.text = line
        else:
            p = text_frame.add_paragraph()
            p.text = line
            p.level = 0
    return slide


def _set_slide_title(slide, title: str) -> None:
    title_shape = slide.shapes.title
    if title_shape is not None and title_shape.has_text_frame:
        title_shape.text_frame.text = title


def _set_placeholder_text(slide, placeholder_index: int, text: str) -> None:
    if placeholder_index >= len(slide.placeholders):
        return

    placeholder = slide.placeholders[placeholder_index]
    if placeholder.has_text_frame:
        placeholder.text_frame.text = text


def _set_notes_text(slide, text: str) -> None:
    notes_frame = slide.notes_slide.notes_text_frame
    if notes_frame is not None:
        notes_frame.text = text


def _insert_visual(slide, image_path: str | None, left: float, top: float, width: float, inches) -> None:
    if not image_path:
        return
    slide.shapes.add_picture(image_path, inches(left), inches(top), width=inches(width))


def _pick_visual(slide_type: str, visual_assets: dict[str, str], title: str) -> str | None:
    lowered = title.lower()
    if slide_type == "process":
        if "pack" in lowered or "entscheidung" in lowered:
            return visual_assets.get("decision_tree") or visual_assets.get("process_flow")
        return visual_assets.get("hold_release") or visual_assets.get("process_flow")
    if slide_type == "comparison":
        return visual_assets.get("variant_comparison")
    if slide_type == "concept_grid":
        return visual_assets.get("hold_release")
    if "sorting" in lowered or "non-sequential" in lowered or "non sequential" in lowered:
        return visual_assets.get("non_sequential_sorting")
    if "referenz" in lowered or "cookie" in lowered or "scenario" in lowered:
        return visual_assets.get("process_flow")
    return visual_assets.get("top_terms")


def export_training_presentation(
    summary: dict[str, Any],
    media_path: str,
    output_dir: str,
    visual_assets: dict[str, str],
    max_slides: int = 12,
    ppt_blueprint: dict[str, Any] | None = None,
    output_path: str | None = None,
) -> str:
    """Create training slides with diagrams/images and return .pptx path."""
    from pptx import Presentation  # type: ignore[import-untyped]
    from pptx.dml.color import RGBColor  # type: ignore[import-untyped]
    from pptx.enum.shapes import MSO_SHAPE  # type: ignore[import-untyped]
    from pptx.util import Inches  # type: ignore[import-untyped]

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    base_name = Path(media_path).stem
    generated_label = datetime.now().strftime("%Y%m%d_%H%M%S")

    if output_path:
        out_path = Path(output_path)
    else:
        out_path = out_dir / f"{base_name}_training_slides_{generated_label}.pptx"

    prs = Presentation()
    prs.slide_width = Inches(10)
    prs.slide_height = Inches(7.5)
    titles = summary.get("titles", {}) if isinstance(summary.get("titles"), dict) else {}
    blueprint = ppt_blueprint if isinstance(ppt_blueprint, dict) else {}
    slide_defs = blueprint.get("slides", []) if isinstance(blueprint.get("slides"), list) else []
    colors = _theme_colors(RGBColor)
    generated_local = datetime.now().astimezone()
    generated_utc = generated_local.astimezone(timezone.utc)
    core = prs.core_properties
    core.created = generated_utc
    core.modified = generated_utc

    title_slide = prs.slides.add_slide(prs.slide_layouts[0])
    _add_title_background(title_slide, Inches, colors)
    _style_slide_title(title_slide, str(blueprint.get("title", "Training Slides")), colors, title_slide=True)
    _set_placeholder_text(
        title_slide,
        1,
        str(blueprint.get("subtitle", f"Source: {base_name}\nGenerated: {generated_label}")),
    )
    if len(title_slide.placeholders) > 1:
        subtitle_placeholder = title_slide.placeholders[1]
        if subtitle_placeholder.has_text_frame:
            frame = cast(Any, subtitle_placeholder).text_frame
            for idx, paragraph in enumerate(frame.paragraphs):
                _apply_run_style(paragraph, size_pt=15.5 if idx == 0 else 8.5, color=colors["blue_soft"] if idx == 0 else colors["white"])
    _add_footer(title_slide, 1, Inches, colors)

    if slide_defs:
        for slide_index, slide_def in enumerate(slide_defs[: max(0, max_slides - 1)], start=2):
            if not isinstance(slide_def, dict):
                continue
            slide_type = str(slide_def.get("slide_type", "statement")).strip() or "statement"
            slide = prs.slides.add_slide(prs.slide_layouts[5])
            _style_slide_title(slide, str(slide_def.get("title", "Slide")), colors)
            _add_subtitle(
                slide,
                str(slide_def.get("subtitle", "")).strip(),
                0.6,
                1.15,
                8.5,
                0.35,
                Inches,
                colors,
            )
            bullets = _as_lines(slide_def.get("bullets", []), 8)
            labels = _as_labels(slide_def.get("labels", []), 6)

            if slide_type == "agenda":
                _render_agenda_cards(slide, bullets, Inches, colors)
            elif slide_type == "process":
                _render_process_labels(slide, labels or bullets[:5], Inches, colors)
                visual_path = _pick_visual(slide_type, visual_assets, str(slide_def.get("title", "")))
                _insert_visual(slide, visual_path, 6.55, 2.1, 2.7, Inches)
                body = slide.shapes.add_textbox(Inches(0.7), Inches(3.45), Inches(8.2), Inches(2.0))
                for idx, line in enumerate(bullets[:5]):
                    p = body.text_frame.add_paragraph() if idx > 0 else body.text_frame.paragraphs[0]
                    p.text = line
                    p.level = 0
                    _apply_run_style(p, size_pt=10.5 if idx > 0 else 12, color=colors["navy"] if idx == 0 else colors["muted"], bold=idx == 0)
            elif slide_type == "comparison":
                _insert_visual(slide, _pick_visual(slide_type, visual_assets, str(slide_def.get("title", ""))), 6.65, 5.6, 2.1, Inches)
                _render_comparison(slide, labels, bullets, Inches, colors)
            elif slide_type == "concept_grid":
                _insert_visual(slide, _pick_visual(slide_type, visual_assets, str(slide_def.get("title", ""))), 6.7, 5.55, 2.0, Inches)
                _render_concept_grid(slide, labels, bullets, Inches, colors)
            else:
                label = labels[0] if labels else ""
                if label:
                    label_box = slide.shapes.add_textbox(Inches(0.7), Inches(1.8), Inches(2.6), Inches(0.35))
                    label_box.text_frame.text = label
                    _apply_run_style(label_box.text_frame.paragraphs[0], size_pt=12, color=colors["navy"], bold=True)
                body = slide.shapes.add_textbox(Inches(0.7), Inches(1.8), Inches(8.3), Inches(3.8))
                for idx, line in enumerate(bullets[:6]):
                    p = body.text_frame.add_paragraph() if idx > 0 else body.text_frame.paragraphs[0]
                    p.text = line
                    p.level = 0
                    _apply_run_style(p, size_pt=14 if idx == 0 and slide_type == "statement" else 10.5, color=colors["text"] if idx == 0 else colors["muted"], bold=idx == 0 and slide_type == "statement")
                _insert_visual(slide, _pick_visual(slide_type, visual_assets, str(slide_def.get("title", ""))), 6.4, 2.5, 2.4, Inches)

            visual_hint = str(slide_def.get("visual_hint", "")).strip()
            callout = str(slide_def.get("callout", "")).strip() or visual_hint
            _add_callout(slide, callout, Inches, colors)
            speaker_notes = str(slide_def.get("speaker_notes", "")).strip()
            if speaker_notes:
                _set_notes_text(slide, speaker_notes)
            _add_footer(slide, slide_index, Inches, colors)

        while len(prs.slides) > max_slides:
            r_id = prs.slides._sldIdLst[-1].rId  # pylint: disable=protected-access
            prs.part.drop_rel(r_id)
            del prs.slides._sldIdLst[-1]  # pylint: disable=protected-access

        prs.save(str(out_path))
        set_file_times(out_path, generated_local)
        return str(out_path)

    agenda = _add_bullet_slide(
        prs,
        "Agenda",
        [
            titles.get("goals", "Goals"),
            titles.get("topics", "Topics"),
            titles.get("processes", "Processes"),
            titles.get("risks", "Risks"),
            titles.get("actions", "Actions"),
            "Q&A",
        ],
    )

    _add_bullet_slide(prs, titles.get("goals", "Learning Objectives"), _as_lines(summary.get("goals"), 5))
    topic_slide = _add_bullet_slide(prs, titles.get("topics", "Core Topics"), _as_lines(summary.get("topics"), 6))
    process_slide = _add_bullet_slide(prs, titles.get("processes", "Processes"), _as_lines(summary.get("processes"), 6))
    _add_bullet_slide(prs, titles.get("risks", "Risks"), _as_lines(summary.get("risks"), 5))
    _add_bullet_slide(prs, titles.get("actions", "Actions"), _as_lines(summary.get("actions"), 5))
    _add_bullet_slide(prs, titles.get("quiz", "Quiz Questions"), _as_lines(summary.get("quiz"), 5))

    if visual_assets.get("top_terms"):
        vis_slide = prs.slides.add_slide(prs.slide_layouts[5])
        _set_slide_title(vis_slide, "Topic Frequency")
        vis_slide.shapes.add_picture(visual_assets["top_terms"], Inches(0.6), Inches(1.3), width=Inches(8.8))

    if visual_assets.get("process_flow"):
        flow_slide = prs.slides.add_slide(prs.slide_layouts[5])
        _set_slide_title(flow_slide, "Process Flow")
        flow_slide.shapes.add_picture(visual_assets["process_flow"], Inches(0.6), Inches(1.3), width=Inches(8.8))

    # Add a simple drawing-based explanation slide (shapes + arrows) as built-in illustration.
    drawing_slide = prs.slides.add_slide(prs.slide_layouts[5])
    _set_slide_title(drawing_slide, "Training Flow Drawing")

    box1 = drawing_slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.7), Inches(2.0), Inches(2.4), Inches(1.0))
    box2 = drawing_slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(3.6), Inches(2.0), Inches(2.4), Inches(1.0))
    box3 = drawing_slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(6.5), Inches(2.0), Inches(2.4), Inches(1.0))

    for shape, label in [
        (box1, "Analyze"),
        (box2, "Apply"),
        (box3, "Review"),
    ]:
        shape.fill.solid()
        shape.fill.fore_color.rgb = RGBColor(232, 241, 242)
        shape.line.color.rgb = RGBColor(42, 111, 151)
        shape.text_frame.text = label

    arrow1 = drawing_slide.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(2.95), Inches(2.28), Inches(0.55), Inches(0.45))
    arrow2 = drawing_slide.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(5.85), Inches(2.28), Inches(0.55), Inches(0.45))
    for arr in (arrow1, arrow2):
        arr.fill.solid()
        arr.fill.fore_color.rgb = RGBColor(42, 111, 151)

    # Add speaker notes on selected slides.
    _set_notes_text(agenda, "Introduce agenda and expected outcomes.")
    _set_notes_text(topic_slide, "Explain each topic with one concrete example from the transcript.")
    _set_notes_text(process_slide, "Walk through process steps in execution order.")

    closing = prs.slides.add_slide(prs.slide_layouts[1])
    _set_slide_title(closing, "Q&A and Next Steps")
    _set_placeholder_text(closing, 1, "Questions\nRecap key takeaways\nDefine follow-up actions")

    while len(prs.slides) > max_slides:
        # Keep deterministic behavior by dropping the last slides first.
        r_id = prs.slides._sldIdLst[-1].rId  # pylint: disable=protected-access
        prs.part.drop_rel(r_id)
        del prs.slides._sldIdLst[-1]  # pylint: disable=protected-access

    prs.save(str(out_path))
    set_file_times(out_path, generated_local)
    return str(out_path)
