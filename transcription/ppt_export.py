# -*- coding: utf-8 -*-
"""Single-slide PowerPoint export from transcript-derived Markdown."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from pathlib import Path
import re

try:
    from .file_timestamps import set_file_times
except ImportError:  # pragma: no cover
    from file_timestamps import set_file_times


HEADING_RE = re.compile(r"^#{1,6}\s+(.*)$")
INLINE_MD_RE = re.compile(r"(\*\*[^*]+\*\*|__[^_]+__|\*[^*]+\*|_[^_]+_)")


def _extract_visual_type(markdown_text: str) -> str:
    """Extract the recommended visual type from LLM output."""
    for line in markdown_text.splitlines():
        if "recommended visual type" in line.lower():
            # Look at next lines for the type
            lines = markdown_text.splitlines()
            idx = next((i for i, l in enumerate(lines) if "recommended visual type" in l.lower()), -1)
            if idx >= 0 and idx + 1 < len(lines):
                next_line = lines[idx + 1].strip()
                if next_line and not next_line.startswith("#"):
                    return next_line.lower()
    return "process flow"


def _extract_section_content(markdown_text: str, section_name: str) -> list[str]:
    """Extract content from a named section in the markdown."""
    lines = markdown_text.splitlines()
    section_start = -1
    section_end = len(lines)
    
    for idx, line in enumerate(lines):
        if section_name.lower() in line.lower() and line.strip().startswith("#"):
            section_start = idx + 1
        elif section_start > 0 and line.strip().startswith("#") and idx > section_start:
            section_end = idx
            break
    
    if section_start < 0:
        return []
    
    result = []
    for line in lines[section_start:section_end]:
        line = line.strip()
        if line and not line.startswith("#"):
            result.append(line)
    
    return result


def _parse_markdown(markdown_text: str) -> tuple[str, list[str], list[str]]:
    """Parse markdown into slide title, elements, and steps."""
    lines = [line.strip() for line in markdown_text.splitlines() if line.strip()]
    if not lines:
        return "Slide", [], []

    # Find title (first heading or first line)
    title = ""
    for line in lines:
        if line.startswith("#") and not line.startswith("##"):  # Only top-level heading
            title = re.sub(r"^#+\s+", "", line).strip()
            break
    title = title or "Slide"
    
    # Strategy 1: Extract from structured sections
    elements = _extract_section_content(markdown_text, "Visual Elements")
    if not elements:
        elements = _extract_section_content(markdown_text, "Text to Place")
    
    steps = _extract_section_content(markdown_text, "Flow or Relationship Logic")
    if not steps:
        steps = _extract_section_content(markdown_text, "Layout Description")
    
    # Strategy 2: Fallback to collecting bullet points and numbered items
    if not elements:
        elements = []
        for line in lines:
            if line.startswith("- ") or line.startswith("* "):
                clean = line[2:].strip()
                if clean and not clean.startswith("["):  # Skip markdown links
                    elements.append(clean)
            elif re.match(r"^\d+\.\s+", line):
                clean = re.sub(r"^\d+\.\s+", "", line).strip()
                if clean and not clean.lower().startswith("element"):
                    elements.append(clean)
    
    if not steps:
        # Collect any non-heading, non-empty, non-title lines as steps
        steps = []
        found_title = False
        for line in lines:
            if line.startswith("#"):
                found_title = True
                continue
            if found_title and line and not line.startswith("#"):
                # Take up to first 100 chars per line as a step
                if len(line) < 80:
                    steps.append(line)
    
    # Ensure we have at least something to show
    if not elements and not steps:
        # Last resort: use all non-heading lines as elements
        elements = [line for line in lines[1:] if line and not line.startswith("#")][:8]
    
    return title, elements[:8], steps[:6]


def _apply_inline_markdown_runs(
    paragraph: object,
    text: str,
    *,
    font_name: str,
    font_size: object,
    default_bold: bool,
    font_color: object,
) -> None:
    # Clear auto-created runs from paragraph.text assignment and write explicit formatted runs.
    pos = 0
    matches = list(INLINE_MD_RE.finditer(text))
    if not matches:
        run = paragraph.add_run()
        run.text = text
        run.font.name = font_name
        run.font.size = font_size
        run.font.bold = default_bold
        run.font.color.rgb = font_color
        return

    for match in matches:
        start, end = match.span()
        if start > pos:
            run = paragraph.add_run()
            run.text = text[pos:start]
            run.font.name = font_name
            run.font.size = font_size
            run.font.bold = default_bold
            run.font.color.rgb = font_color

        token = match.group(0)
        if (token.startswith("**") and token.endswith("**")) or (token.startswith("__") and token.endswith("__")):
            token_text = token[2:-2]
            token_bold = True
            token_italic = False
        elif (token.startswith("*") and token.endswith("*")) or (token.startswith("_") and token.endswith("_")):
            token_text = token[1:-1]
            token_bold = default_bold
            token_italic = True
        else:
            token_text = token
            token_bold = default_bold
            token_italic = False

        run = paragraph.add_run()
        run.text = token_text
        run.font.name = font_name
        run.font.size = font_size
        run.font.bold = token_bold
        run.font.italic = token_italic
        run.font.color.rgb = font_color
        pos = end

    if pos < len(text):
        run = paragraph.add_run()
        run.text = text[pos:]
        run.font.name = font_name
        run.font.size = font_size
        run.font.bold = default_bold
        run.font.color.rgb = font_color



def export_training_presentation(markdown_text: str, media_path: str, output_dir: str, output_path: str | None = None) -> str:
    from pptx import Presentation  # type: ignore[import-untyped]
    from pptx.dml.color import RGBColor  # type: ignore[import-untyped]
    from pptx.enum.shapes import MSO_SHAPE  # type: ignore[import-untyped]
    from pptx.util import Inches, Pt  # type: ignore[import-untyped]

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    base_name = Path(media_path).stem
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = Path(output_path) if output_path else out_dir / f"{base_name}_training_slides_generated_{timestamp}.pptx"

    title, elements, steps = _parse_markdown(markdown_text)
    visual_type = _extract_visual_type(markdown_text)

    prs = Presentation()
    prs.slide_width = Inches(10)
    prs.slide_height = Inches(7.5)
    slide = prs.slides.add_slide(prs.slide_layouts[5])
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = RGBColor(248, 250, 252)

    # Add title
    title_box = slide.shapes.add_textbox(Inches(0.6), Inches(0.35), Inches(8.8), Inches(0.7))
    title_frame = title_box.text_frame
    title_paragraph = title_frame.paragraphs[0]
    _apply_inline_markdown_runs(
        title_paragraph,
        title,
        font_name="Aptos Display",
        font_size=Pt(28),
        default_bold=True,
        font_color=RGBColor(11, 31, 58),
    )

    # Render visual based on detected type
    _render_visual_layout(slide, visual_type, elements, steps)

    # Add notes with full markdown for reference
    notes = slide.notes_slide.notes_text_frame
    if notes is not None:
        notes.text = markdown_text

    generated_local = datetime.now().astimezone()
    generated_utc = generated_local.astimezone(timezone.utc)
    core = prs.core_properties
    core.created = generated_utc
    core.modified = generated_utc
    prs.save(str(out_path))
    set_file_times(out_path, generated_local)
    return str(out_path)


def _render_visual_layout(slide: object, visual_type: str, elements: list[str], steps: list[str]) -> None:
    """Render visual layout based on the detected visual type."""
    from pptx.dml.color import RGBColor  # type: ignore[import-untyped]
    from pptx.enum.shapes import MSO_SHAPE  # type: ignore[import-untyped]
    from pptx.util import Inches, Pt  # type: ignore[import-untyped]

    visual_type_lower = visual_type.lower()
    
    # Process Flow, Workflow, Steps → Horizontal flow with arrows
    if any(x in visual_type_lower for x in ["process flow", "workflow", "step", "steps"]):
        _render_process_flow(slide, elements or steps)
    
    # Timeline → Vertical or horizontal timeline
    elif "timeline" in visual_type_lower:
        _render_timeline(slide, elements or steps)
    
    # Concept Map → Central concept with radiating elements
    elif "concept" in visual_type_lower:
        _render_concept_map(slide, elements or steps)
    
    # Comparison, Matrix → Grid-based layout
    elif any(x in visual_type_lower for x in ["comparison", "matrix", "framework"]):
        _render_comparison_matrix(slide, elements)
    
    # Decision Tree → Hierarchical tree
    elif "decision" in visual_type_lower or "tree" in visual_type_lower:
        _render_decision_tree(slide, elements or steps)
    
    # Cause and Effect → Cause-effect diagram
    elif any(x in visual_type_lower for x in ["cause", "effect", "fishbone"]):
        _render_cause_effect(slide, elements or steps)
    
    # System, Architecture → Box-based architecture diagram
    elif any(x in visual_type_lower for x in ["system", "architecture", "diagram"]):
        _render_architecture(slide, elements)
    
    # Hub and Spoke → Central hub with radiating spokes
    elif any(x in visual_type_lower for x in ["hub", "spoke"]):
        _render_hub_and_spoke(slide, elements or steps)
    
    # Default: Bullet list fallback
    else:
        _render_bullet_list(slide, elements or steps)


def _render_process_flow(slide: object, items: list[str]) -> None:
    """Render a horizontal process flow with arrows between boxes."""
    from pptx.dml.color import RGBColor  # type: ignore[import-untyped]
    from pptx.enum.shapes import MSO_SHAPE  # type: ignore[import-untyped]
    from pptx.util import Inches, Pt  # type: ignore[import-untyped]

    if not items:
        return
    
    num_items = min(len(items), 5)
    box_width = 1.4
    gap = 0.25
    total_width = num_items * box_width + (num_items - 1) * gap
    start_left = (10 - total_width) / 2
    top = 2.2
    
    colors = [
        RGBColor(220, 235, 255),
        RGBColor(210, 230, 255),
        RGBColor(200, 225, 255),
        RGBColor(190, 220, 255),
        RGBColor(180, 215, 255),
    ]
    
    for idx, item in enumerate(items[:num_items]):
        left = start_left + idx * (box_width + gap)
        
        # Add rounded rectangle box
        box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(left), Inches(top), Inches(box_width), Inches(1.2))
        box.fill.solid()
        box.fill.fore_color.rgb = colors[idx % len(colors)]
        box.line.color.rgb = RGBColor(23, 87, 166)
        box.line.width = Pt(2)
        
        # Add text
        frame = box.text_frame
        frame.word_wrap = True
        frame.margin_left = Inches(0.1)
        frame.margin_right = Inches(0.1)
        frame.margin_top = Inches(0.1)
        frame.margin_bottom = Inches(0.1)
        para = frame.paragraphs[0]
        para.text = item
        para.font.size = Pt(10)
        para.font.bold = True
        para.font.color.rgb = RGBColor(11, 31, 58)
        para.font.name = "Aptos"
        
        # Add arrow to next box
        if idx < num_items - 1:
            arrow_left = left + box_width
            arrow = slide.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(arrow_left), Inches(top + 0.45), Inches(gap - 0.05), Inches(0.3))
            arrow.fill.solid()
            arrow.fill.fore_color.rgb = RGBColor(23, 87, 166)
            arrow.line.color.rgb = RGBColor(23, 87, 166)


def _render_timeline(slide: object, items: list[str]) -> None:
    """Render a vertical timeline."""
    from pptx.dml.color import RGBColor  # type: ignore[import-untyped]
    from pptx.enum.shapes import MSO_SHAPE  # type: ignore[import-untyped]
    from pptx.util import Inches, Pt  # type: ignore[import-untyped]

    if not items:
        return
    
    num_items = min(len(items), 6)
    left_line = 2.0
    left_circle = 1.75
    left_text = 2.8
    top_start = 1.5
    spacing = 0.85
    
    # Draw vertical line
    line = slide.shapes.add_connector(1, Inches(left_line), Inches(top_start), Inches(left_line), Inches(top_start + spacing * num_items))
    line.line.color.rgb = RGBColor(23, 87, 166)
    line.line.width = Pt(2)
    
    for idx, item in enumerate(items[:num_items]):
        top = top_start + idx * spacing
        
        # Draw circle at timeline point
        circle = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(left_circle), Inches(top - 0.15), Inches(0.5), Inches(0.5))
        circle.fill.solid()
        circle.fill.fore_color.rgb = RGBColor(23, 87, 166)
        circle.line.color.rgb = RGBColor(11, 31, 58)
        circle.line.width = Pt(2)
        
        # Add text label
        text_box = slide.shapes.add_textbox(Inches(left_text), Inches(top - 0.2), Inches(6.2), Inches(0.6))
        frame = text_box.text_frame
        frame.word_wrap = True
        para = frame.paragraphs[0]
        para.text = item
        para.font.size = Pt(12)
        para.font.bold = True if idx == 0 else False
        para.font.color.rgb = RGBColor(11, 31, 58)
        para.font.name = "Aptos"


def _render_concept_map(slide: object, items: list[str]) -> None:
    """Render a concept map with central concept and radiating elements."""
    from pptx.dml.color import RGBColor  # type: ignore[import-untyped]
    from pptx.enum.shapes import MSO_SHAPE  # type: ignore[import-untyped]
    from pptx.util import Inches, Pt  # type: ignore[import-untyped]
    import math

    if not items:
        return
    
    center_x = 5.0
    center_y = 3.5
    center_radius = 0.4
    outer_radius = 2.0
    num_items = min(len(items) - 1, 6) if len(items) > 1 else 0
    
    # Central circle (main concept)
    if items:
        center = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(center_x - center_radius), Inches(center_y - center_radius), Inches(center_radius * 2), Inches(center_radius * 2))
        center.fill.solid()
        center.fill.fore_color.rgb = RGBColor(23, 87, 166)
        center.line.color.rgb = RGBColor(11, 31, 58)
        center.line.width = Pt(2)
        
        frame = center.text_frame
        frame.word_wrap = True
        para = frame.paragraphs[0]
        para.text = items[0]
        para.font.size = Pt(8)
        para.font.bold = True
        para.font.color.rgb = RGBColor(255, 255, 255)
        para.alignment = 1  # Center alignment
    
    # Radiating elements
    if num_items > 0:
        angle_step = 360 / num_items
        for idx in range(num_items):
            angle = (idx * angle_step) * math.pi / 180
            x = center_x + outer_radius * math.cos(angle)
            y = center_y + outer_radius * math.sin(angle)
            
            # Draw connection line
            conn = slide.shapes.add_connector(1, Inches(center_x), Inches(center_y), Inches(x), Inches(y))
            conn.line.color.rgb = RGBColor(150, 180, 220)
            conn.line.width = Pt(1)
            
            # Draw outer circle
            outer = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x - 0.35), Inches(y - 0.35), Inches(0.7), Inches(0.7))
            outer.fill.solid()
            outer.fill.fore_color.rgb = RGBColor(220, 235, 255)
            outer.line.color.rgb = RGBColor(23, 87, 166)
            outer.line.width = Pt(1.5)
            
            frame = outer.text_frame
            frame.word_wrap = True
            para = frame.paragraphs[0]
            para.text = items[idx + 1]
            para.font.size = Pt(8)
            para.font.bold = True
            para.font.color.rgb = RGBColor(11, 31, 58)
            para.alignment = 1


def _render_comparison_matrix(slide: object, items: list[str]) -> None:
    """Render a 2x3 or 3x3 comparison matrix."""
    from pptx.dml.color import RGBColor  # type: ignore[import-untyped]
    from pptx.enum.shapes import MSO_SHAPE  # type: ignore[import-untyped]
    from pptx.util import Inches, Pt  # type: ignore[import-untyped]

    if not items:
        _render_bullet_list(slide, items)
        return
    
    # Create a simple 2x3 grid
    grid_left = 1.0
    grid_top = 1.8
    cell_width = 2.6
    cell_height = 0.9
    gap = 0.2
    
    grid_items = items[:6]
    cols = min(3, max(2, len(grid_items) // 2))
    
    for idx, item in enumerate(grid_items):
        row = idx // cols
        col = idx % cols
        left = grid_left + col * (cell_width + gap)
        top = grid_top + row * (cell_height + gap)
        
        # Draw cell
        cell = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(left), Inches(top), Inches(cell_width), Inches(cell_height))
        cell.fill.solid()
        cell.fill.fore_color.rgb = RGBColor(220, 235, 255) if idx % 2 == 0 else RGBColor(200, 225, 255)
        cell.line.color.rgb = RGBColor(23, 87, 166)
        cell.line.width = Pt(1)
        
        # Add text
        frame = cell.text_frame
        frame.word_wrap = True
        frame.margin_left = Inches(0.1)
        frame.margin_right = Inches(0.1)
        para = frame.paragraphs[0]
        para.text = item
        para.font.size = Pt(10)
        para.font.bold = True
        para.font.color.rgb = RGBColor(11, 31, 58)
        para.font.name = "Aptos"


def _render_decision_tree(slide: object, items: list[str]) -> None:
    """Render a simple decision tree."""
    from pptx.dml.color import RGBColor  # type: ignore[import-untyped]
    from pptx.enum.shapes import MSO_SHAPE  # type: ignore[import-untyped]
    from pptx.util import Inches, Pt  # type: ignore[import-untyped]

    if not items:
        return
    
    # Root at top
    root_x = 5.0
    root_y = 1.5
    box_width = 1.2
    box_height = 0.6
    
    # Root box
    root = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(root_x - box_width / 2), Inches(root_y), Inches(box_width), Inches(box_height))
    root.fill.solid()
    root.fill.fore_color.rgb = RGBColor(23, 87, 166)
    root.line.color.rgb = RGBColor(11, 31, 58)
    frame = root.text_frame
    frame.word_wrap = True
    para = frame.paragraphs[0]
    para.text = items[0] if items else "Decision"
    para.font.size = Pt(10)
    para.font.bold = True
    para.font.color.rgb = RGBColor(255, 255, 255)
    para.alignment = 1
    
    # Child branches
    if len(items) > 1:
        child_y = 2.5
        num_children = min(len(items) - 1, 3)
        spacing_x = 7.0 / (num_children + 1)
        
        for idx in range(num_children):
            child_x = 1.5 + (idx + 1) * spacing_x
            
            # Draw connection line
            conn = slide.shapes.add_connector(1, Inches(root_x), Inches(root_y + box_height), Inches(child_x), Inches(child_y))
            conn.line.color.rgb = RGBColor(150, 180, 220)
            conn.line.width = Pt(1.5)
            
            # Draw child box
            child = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(child_x - box_width / 2), Inches(child_y), Inches(box_width), Inches(box_height))
            child.fill.solid()
            child.fill.fore_color.rgb = RGBColor(220, 235, 255)
            child.line.color.rgb = RGBColor(23, 87, 166)
            frame = child.text_frame
            frame.word_wrap = True
            para = frame.paragraphs[0]
            para.text = items[idx + 1]
            para.font.size = Pt(9)
            para.font.bold = True
            para.font.color.rgb = RGBColor(11, 31, 58)
            para.alignment = 1


def _render_cause_effect(slide: object, items: list[str]) -> None:
    """Render a cause-and-effect (fishbone) diagram."""
    from pptx.dml.color import RGBColor  # type: ignore[import-untyped]
    from pptx.enum.shapes import MSO_SHAPE  # type: ignore[import-untyped]
    from pptx.util import Inches, Pt  # type: ignore[import-untyped]

    if not items:
        return
    
    # Effect (head) on the right
    effect_x = 8.5
    effect_y = 3.75
    
    # Draw effect box
    effect = slide.shapes.add_shape(MSO_SHAPE.DIAMOND, Inches(effect_x - 0.5), Inches(effect_y - 0.35), Inches(1.0), Inches(0.7))
    effect.fill.solid()
    effect.fill.fore_color.rgb = RGBColor(220, 100, 100)
    effect.line.color.rgb = RGBColor(150, 30, 30)
    effect.line.width = Pt(2)
    frame = effect.text_frame
    frame.word_wrap = True
    para = frame.paragraphs[0]
    para.text = items[0] if items else "Effect"
    para.font.size = Pt(9)
    para.font.bold = True
    para.font.color.rgb = RGBColor(255, 255, 255)
    para.alignment = 1
    
    # Main spine from left to right
    spine = slide.shapes.add_connector(1, Inches(1.0), Inches(effect_y), Inches(effect_x - 0.5), Inches(effect_y))
    spine.line.color.rgb = RGBColor(80, 80, 80)
    spine.line.width = Pt(2)
    
    # Causes (branches)
    num_causes = min(len(items) - 1, 4)
    if num_causes > 0:
        spacing_y = 1.5 / num_causes
        for idx in range(num_causes):
            branch_y = effect_y - 0.75 + idx * spacing_y
            branch_x = 4.0
            
            # Branch line
            branch = slide.shapes.add_connector(1, Inches(branch_x), Inches(branch_y), Inches(5.5), Inches(effect_y))
            branch.line.color.rgb = RGBColor(120, 120, 120)
            branch.line.width = Pt(1.5)
            
            # Cause label
            label = slide.shapes.add_textbox(Inches(1.5), Inches(branch_y - 0.2), Inches(2.2), Inches(0.4))
            frame = label.text_frame
            frame.word_wrap = True
            para = frame.paragraphs[0]
            para.text = items[idx + 1]
            para.font.size = Pt(9)
            para.font.bold = True
            para.font.color.rgb = RGBColor(11, 31, 58)


def _render_architecture(slide: object, items: list[str]) -> None:
    """Render a system/architecture diagram with stacked layers."""
    from pptx.dml.color import RGBColor  # type: ignore[import-untyped]
    from pptx.enum.shapes import MSO_SHAPE  # type: ignore[import-untyped]
    from pptx.util import Inches, Pt  # type: ignore[import-untyped]

    if not items:
        return
    
    num_items = min(len(items), 5)
    box_width = 4.0
    box_height = 0.8
    gap = 0.1
    start_left = 3.0
    start_top = 1.5
    
    colors = [
        RGBColor(220, 235, 255),
        RGBColor(200, 225, 255),
        RGBColor(180, 215, 255),
        RGBColor(160, 205, 255),
        RGBColor(140, 195, 255),
    ]
    
    for idx, item in enumerate(items[:num_items]):
        top = start_top + idx * (box_height + gap)
        
        # Draw box
        box = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(start_left), Inches(top), Inches(box_width), Inches(box_height))
        box.fill.solid()
        box.fill.fore_color.rgb = colors[idx % len(colors)]
        box.line.color.rgb = RGBColor(23, 87, 166)
        box.line.width = Pt(2)
        
        # Add text
        frame = box.text_frame
        frame.word_wrap = True
        frame.margin_left = Inches(0.15)
        para = frame.paragraphs[0]
        para.text = item
        para.font.size = Pt(12)
        para.font.bold = True
        para.font.color.rgb = RGBColor(11, 31, 58)
        para.font.name = "Aptos"


def _render_hub_and_spoke(slide: object, items: list[str]) -> None:
    """Render hub-and-spoke diagram (same as concept map)."""
    _render_concept_map(slide, items)


def _render_bullet_list(slide: object, items: list[str]) -> None:
    """Render a simple bullet list as fallback."""
    from pptx.dml.color import RGBColor  # type: ignore[import-untyped]
    from pptx.util import Inches, Pt  # type: ignore[import-untyped]

    if not items:
        return
    
    body = slide.shapes.add_textbox(Inches(0.8), Inches(1.6), Inches(8.2), Inches(5.0))
    frame = body.text_frame
    frame.word_wrap = True
    
    for idx, item in enumerate(items[:8]):
        if idx == 0:
            para = frame.paragraphs[0]
        else:
            para = frame.add_paragraph()
        
        para.text = item
        para.level = 0
        para.font.size = Pt(13 if idx == 0 else 12)
        para.font.bold = (idx == 0)
        para.font.color.rgb = RGBColor(17, 24, 39 if idx == 0 else 91)
        para.font.name = "Aptos"
        para.space_before = Pt(6)
        para.space_after = Pt(4)
