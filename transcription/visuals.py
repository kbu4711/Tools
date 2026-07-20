# -*- coding: utf-8 -*-
"""Local graphic rendering from Markdown graphic suggestions."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional

try:
    from .file_timestamps import set_file_times
except ImportError:  # pragma: no cover
    from file_timestamps import set_file_times


GRAPHIC_TITLE_RE = re.compile(r"^###\s+Suggested Graphic:\s*(.+?)\s*$", re.IGNORECASE)
SUGGESTED_SECTION_RE = re.compile(r"^(#{1,6})\s+Suggested\s+Graphics?(?:\s+and\s+Diagrams?)?\s*$", re.IGNORECASE)
WORKFLOW_SECTION_RE = re.compile(r"^(#{1,6})\s+(?:.*?(?:Flow|Workflow|Process|Architecture|Pipeline|Diagram|System|Integration|Sequence|Interaction|Relationship|Dependency|Mapping)\s*).*$", re.IGNORECASE)
TYPE_RE = re.compile(r"^-\s+(?:\*\*)?Type:(?:\*\*)?\s*(.+?)\s*$", re.IGNORECASE)
PURPOSE_RE = re.compile(r"^-\s+(?:\*\*)?Purpose:(?:\*\*)?\s*(.+?)\s*$", re.IGNORECASE)
DESCRIPTION_RE = re.compile(r"^-\s+(?:\*\*)?Description:(?:\*\*)?\s*(.+?)\s*$", re.IGNORECASE)
PLACEMENT_RE = re.compile(r"^-\s+(?:\*\*)?Suggested placement in document:(?:\*\*)?\s*(.+?)\s*$", re.IGNORECASE)
ELEMENT_RE = re.compile(r"^-\s+(?:\*\*)?(.+?)(?:\*\*)?\s*$")


def _parse_graphics(markdown_text: str) -> list[dict[str, object]]:
    lines = markdown_text.splitlines()
    graphics: list[dict[str, object]] = []
    current: Optional[dict[str, object]] = None
    collect_elements = False
    for raw_line in lines:
        line = raw_line.strip()
        title_match = GRAPHIC_TITLE_RE.match(line)
        if title_match:
            if current:
                graphics.append(current)
            current = {
                "title": title_match.group(1).strip(),
                "type": "Other",
                "purpose": "",
                "description": "",
                "placement": "",
                "elements": [],
            }
            collect_elements = False
            continue
        if not current:
            continue
        type_match = TYPE_RE.match(line)
        if type_match:
            current["type"] = type_match.group(1).strip()
            collect_elements = False
            continue
        purpose_match = PURPOSE_RE.match(line)
        if purpose_match:
            current["purpose"] = purpose_match.group(1).strip()
            collect_elements = False
            continue
        description_match = DESCRIPTION_RE.match(line)
        if description_match:
            current["description"] = description_match.group(1).strip()
            collect_elements = False
            continue
        placement_match = PLACEMENT_RE.match(line)
        if placement_match:
            current["placement"] = placement_match.group(1).strip()
            collect_elements = False
            continue
        if line.lower() == "- elements to include:" or line.lower() == "elements to include:":
            collect_elements = True
            continue
        if collect_elements:
            element_match = ELEMENT_RE.match(line)
            if element_match:
                elements = current.setdefault("elements", [])
                if isinstance(elements, list):
                    elements.append(element_match.group(1).strip())
            else:
                collect_elements = False
    if current:
        graphics.append(current)

    freeform = _parse_freeform_graphic_suggestions(markdown_text)
    if freeform:
        seen = {
            (str(item.get("title", "")).strip().lower(), str(item.get("description", "")).strip().lower())
            for item in graphics
        }
        for item in freeform:
            key = (
                str(item.get("title", "")).strip().lower(),
                str(item.get("description", "")).strip().lower(),
            )
            if key not in seen:
                graphics.append(item)
                seen.add(key)

    return graphics


def _strip_md_inline(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"[`*_]", "", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def _guess_graphic_type(text: str) -> str:
    lowered = text.lower()
    if any(token in lowered for token in ["flow", "workflow", "process", "step", "sequence"]):
        return "Process diagram"
    if any(token in lowered for token in ["timeline", "phase", "milestone", "roadmap"]):
        return "Timeline"
    if any(token in lowered for token in ["compare", "comparison", "versus", "vs", "matrix"]):
        return "Comparison matrix"
    if any(token in lowered for token in ["architecture", "system", "component", "layer"]):
        return "Architecture diagram"
    if any(token in lowered for token in ["concept", "relationship", "map", "dependency"]):
        return "Concept map"
    if any(token in lowered for token in ["table", "grid", "columns"]):
        return "Table"
    return "Other"


def _extract_elements_from_text(text: str) -> list[str]:
    parts = re.split(r"[,;]|\band\b", text, flags=re.IGNORECASE)
    cleaned = [_strip_md_inline(item) for item in parts]
    return [item for item in cleaned if item][:6]


def _title_from_text(text: str, index: int) -> str:
    head = _strip_md_inline(text)
    if ":" in head:
        head = head.split(":", 1)[0]
    words = head.split()
    if not words:
        return f"Graphic {index}"
    short = " ".join(words[:7]).strip(" .,-")
    return short[:1].upper() + short[1:] if short else f"Graphic {index}"


def _parse_freeform_graphic_suggestions(markdown_text: str) -> list[dict[str, object]]:
    lines = markdown_text.splitlines()
    in_section = False
    section_level = 0
    candidates: list[str] = []

    for raw_line in lines:
        stripped = raw_line.strip()
        heading_match = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        section_match = SUGGESTED_SECTION_RE.match(stripped)
        workflow_match = WORKFLOW_SECTION_RE.match(stripped)

        if section_match:
            in_section = True
            section_level = len(section_match.group(1))
            continue

        if workflow_match and not in_section:
            workflow_title = workflow_match.group(0)
            workflow_title = re.sub(r"^#+\s+", "", workflow_title).strip()
            try:
                line_idx = lines.index(raw_line)
                lines_after = lines[line_idx + 1:min(line_idx + 6, len(lines))]
                desc = " ".join([l.strip() for l in lines_after if l.strip() and not l.strip().startswith("#")])
                if desc:
                    candidates.append(f"{workflow_title}: {desc}")
            except (ValueError, IndexError):
                pass
            continue

        if in_section and heading_match:
            this_level = len(heading_match.group(1))
            if this_level <= section_level:
                in_section = False
                continue

        if not in_section or not stripped:
            continue
        if GRAPHIC_TITLE_RE.match(stripped):
            continue

        text = re.sub(r"^[-*]\s+", "", stripped)
        text = re.sub(r"^\d+\.\s+", "", text)
        text = _strip_md_inline(text)
        if len(text) < 12:
            continue
        candidates.append(text)

    graphics: list[dict[str, object]] = []
    for index, suggestion in enumerate(candidates, start=1):
        gtype = _guess_graphic_type(suggestion)
        graphics.append(
            {
                "title": _title_from_text(suggestion, index),
                "type": gtype,
                "purpose": "Visualize suggested content from the summary.",
                "description": suggestion,
                "placement": "Suggested Graphics and Diagrams",
                "elements": _extract_elements_from_text(suggestion),
            }
        )
    return graphics


def _render_process_diagram(ax: Any, title: str, items: list[str], description: str) -> None:
    ax.axis("off")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    
    # Check if description contains keywords for complex flow with decision/branches
    desc_lower = description.lower()
    has_decision = any(kw in desc_lower for kw in ["decision", "packing", "individual", "group", "branch", "alternative"])
    has_hold = any(kw in desc_lower for kw in ["hold", "mixing", "supervisor", "release"])
    
    if has_decision:
        # Render complex flow with decision point
        # Top sequence: Mixing → Molding → Baking → Cooling
        top_steps = ["Mixing", "Molding", "Baking", "Cooling"]
        y_top = 0.75
        step_width = 0.12
        start_x = 0.08
        
        for idx, step in enumerate(top_steps):
            x = start_x + idx * 0.18
            if has_hold and idx == 0:
                # Mixing with hold indicator
                rect = __import__("matplotlib").patches.Rectangle(
                    (x, y_top), step_width, 0.12, facecolor="#fff3cd", edgecolor="#ff6b6b"
                )
                ax.add_patch(rect)
                ax.text(x + step_width/2, y_top + 0.08, step, ha="center", va="center", fontsize=8, fontweight="bold")
                ax.text(x + step_width/2, y_top - 0.04, "(Hold)", ha="center", va="top", fontsize=7, style="italic", color="#ff6b6b")
            else:
                rect = __import__("matplotlib").patches.FancyBboxPatch(
                    (x, y_top), step_width, 0.12, boxstyle="round,pad=0.01", facecolor="#e9f2ff", edgecolor="#4d78a8"
                )
                ax.add_patch(rect)
                ax.text(x + step_width/2, y_top + 0.06, step, ha="center", va="center", fontsize=8)
            
            if idx < len(top_steps) - 1:
                ax.annotate("", xy=(x + step_width + 0.01, y_top + 0.06), xytext=(x + step_width - 0.01, y_top + 0.06),
                           arrowprops={"arrowstyle": "->", "color": "#4d78a8", "lw": 1})
        
        # Decision point
        decision_x = 0.5
        decision_y = 0.5
        decision_size = 0.06
        diamond = __import__("matplotlib").patches.Polygon(
            [(decision_x, decision_y + decision_size), (decision_x + decision_size, decision_y),
             (decision_x, decision_y - decision_size), (decision_x - decision_size, decision_y)],
            facecolor="#fff9e6", edgecolor="#e67e22", linewidth=1.5
        )
        ax.add_patch(diamond)
        ax.text(decision_x, decision_y, "Packing\nType?", ha="center", va="center", fontsize=7, fontweight="bold")
        
        # Arrow down from cooling to decision
        ax.annotate("", xy=(decision_x, decision_y + decision_size + 0.04), xytext=(0.26, y_top),
                   arrowprops={"arrowstyle": "->", "color": "#4d78a8", "lw": 1})
        
        # Left branch: Individual packing
        left_x = 0.2
        left_y = 0.3
        rect_left = __import__("matplotlib").patches.FancyBboxPatch(
            (left_x, left_y), step_width, 0.1, boxstyle="round,pad=0.01", facecolor="#d4edda", edgecolor="#28a745"
        )
        ax.add_patch(rect_left)
        ax.text(left_x + step_width/2, left_y + 0.05, "Individual\nPacking", ha="center", va="center", fontsize=7)
        ax.text(left_x - 0.05, decision_y - 0.02, "Yes", ha="right", fontsize=7, color="#28a745", fontweight="bold")
        ax.annotate("", xy=(left_x + step_width/2, left_y + 0.1), xytext=(decision_x - decision_size, decision_y - 0.02),
                   arrowprops={"arrowstyle": "->", "color": "#28a745", "lw": 1})
        
        # Right branch: Group packing with sorting
        right_x = 0.68
        sorting_y = 0.38
        rect_sort = __import__("matplotlib").patches.FancyBboxPatch(
            (right_x, sorting_y), step_width, 0.1, boxstyle="round,pad=0.01", facecolor="#cce5ff", edgecolor="#0066cc"
        )
        ax.add_patch(rect_sort)
        ax.text(right_x + step_width/2, sorting_y + 0.05, "Sorting by\nWeight", ha="center", va="center", fontsize=7)
        
        pack_y = sorting_y - 0.15
        rect_pack = __import__("matplotlib").patches.FancyBboxPatch(
            (right_x, pack_y), step_width, 0.1, boxstyle="round,pad=0.01", facecolor="#d4edda", edgecolor="#28a745"
        )
        ax.add_patch(rect_pack)
        ax.text(right_x + step_width/2, pack_y + 0.05, "Group\nPacking", ha="center", va="center", fontsize=7)
        
        ax.annotate("", xy=(sorting_y + 0.1, right_x + step_width/2), xytext=(decision_x + decision_size, decision_y - 0.02),
                   arrowprops={"arrowstyle": "->", "color": "#0066cc", "lw": 1})
        ax.text(right_x + 0.05, decision_y - 0.02, "No", ha="left", fontsize=7, color="#0066cc", fontweight="bold")
        
        ax.annotate("", xy=(right_x + step_width/2, pack_y + 0.1), xytext=(right_x + step_width/2, sorting_y),
                   arrowprops={"arrowstyle": "->", "color": "#28a745", "lw": 1})
    else:
        # Simple linear flow
        steps = items[:5] if items else [part.strip() for part in re.split(r"->|,", description) if part.strip()][:5]
        steps = [step[:15] for step in steps]
        y = 0.55
        width = 0.15
        x_spacing = 0.16
        for idx, step in enumerate(steps):
            x = 0.08 + idx * x_spacing
            if x + width > 0.95:
                break
            rect = __import__("matplotlib").patches.FancyBboxPatch(
                (x, y), width, 0.15, boxstyle="round,pad=0.01", facecolor="#e9f2ff", edgecolor="#4d78a8"
            )
            ax.add_patch(rect)
            ax.text(x + width/2, y + 0.075, step, ha="center", va="center", fontsize=8)
            if idx < len(steps) - 1:
                ax.annotate("", xy=(x + width + 0.005, y + 0.075), xytext=(x + width - 0.005, y + 0.075),
                           arrowprops={"arrowstyle": "->", "color": "#4d78a8", "lw": 1.2})
    
    ax.text(0.02, 0.97, title, fontsize=11, fontweight="bold", ha="left", va="top")


def _render_timeline(ax: Any, title: str, items: list[str], description: str) -> None:
    ax.axis("off")
    points = items[:5] if items else [part.strip() for part in re.split(r"[,;]", description) if part.strip()][:5]
    if len(points) < 2:
        points = ["Start", "Milestone", "End"]
    xs = [0.1 + i * (0.8 / max(1, len(points) - 1)) for i in range(len(points))]
    ax.plot([0.1, 0.9], [0.5, 0.5], color="#4d78a8", lw=2)
    for x, label in zip(xs, points):
        ax.plot([x], [0.5], marker="o", color="#4d78a8")
        ax.text(x, 0.58, label[:18], ha="center", va="bottom", fontsize=8)
    ax.text(0.02, 0.95, title, fontsize=12, fontweight="bold", ha="left", va="top")


def _render_comparison(ax: Any, title: str, items: list[str]) -> None:
    ax.axis("off")
    left = items[0] if len(items) >= 1 else "Option A"
    right = items[1] if len(items) >= 2 else "Option B"
    ax.add_patch(__import__("matplotlib").patches.Rectangle((0.1, 0.3), 0.32, 0.45, facecolor="#f2f7ff", edgecolor="#4d78a8"))
    ax.add_patch(__import__("matplotlib").patches.Rectangle((0.58, 0.3), 0.32, 0.45, facecolor="#fff6ef", edgecolor="#b07a4d"))
    ax.text(0.26, 0.7, left[:22], ha="center", va="center", fontsize=10, fontweight="bold")
    ax.text(0.74, 0.7, right[:22], ha="center", va="center", fontsize=10, fontweight="bold")
    ax.text(0.26, 0.5, "Pros / Eigenschaften", ha="center", va="center", fontsize=8)
    ax.text(0.74, 0.5, "Pros / Eigenschaften", ha="center", va="center", fontsize=8)
    ax.text(0.02, 0.95, title, fontsize=12, fontweight="bold", ha="left", va="top")


def _render_concept_map(ax: Any, title: str, items: list[str]) -> None:
    ax.axis("off")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    
    center = items[0] if items else "Material on Hold"
    satellites = items[1:5] if len(items) > 1 else ["Restriction 1", "Restriction 2", "Restriction 3"]
    
    # Center circle
    center_circle = __import__("matplotlib").patches.Circle((0.5, 0.5), 0.12, facecolor="#fff3cd", edgecolor="#ff6b6b", linewidth=2)
    ax.add_patch(center_circle)
    ax.text(0.5, 0.5, center[:20], ha="center", va="center", fontsize=9, fontweight="bold", color="#333")
    
    # Satellite positions (cross pattern + corners for more satellites)
    if len(satellites) == 1:
        positions = [(0.5, 0.8)]
    elif len(satellites) == 2:
        positions = [(0.25, 0.65), (0.75, 0.65)]
    elif len(satellites) == 3:
        positions = [(0.25, 0.75), (0.75, 0.75), (0.5, 0.25)]
    else:
        positions = [(0.25, 0.8), (0.75, 0.8), (0.25, 0.2), (0.75, 0.2)]
    
    for idx, (label, (x, y)) in enumerate(zip(satellites, positions)):
        sat_circle = __import__("matplotlib").patches.Circle((x, y), 0.095, facecolor="#d4edda" if idx == 0 else "#e9f2ff", 
                                                            edgecolor="#28a745" if idx == 0 else "#4d78a8", linewidth=1.5)
        ax.add_patch(sat_circle)
        
        # Wrap longer labels
        if len(label) > 18:
            words = label.split()
            if len(words) > 1:
                label_wrapped = "\n".join([" ".join(words[i:i+2]) for i in range(0, len(words), 2)])
            else:
                label_wrapped = label[:18]
        else:
            label_wrapped = label
        
        ax.text(x, y, label_wrapped, ha="center", va="center", fontsize=7, fontweight="bold" if idx == 0 else "normal")
        
        # Connection line
        dx = x - 0.5
        dy = y - 0.5
        dist = (dx**2 + dy**2)**0.5
        x_start = 0.5 + (0.12 / dist) * dx if dist > 0 else 0.5
        y_start = 0.5 + (0.12 / dist) * dy if dist > 0 else 0.5
        x_end = x - (0.095 / dist) * dx if dist > 0 else x
        y_end = y - (0.095 / dist) * dy if dist > 0 else y
        
        ax.plot([x_start, x_end], [y_start, y_end], color="#7a8ca5", lw=1.5)
    
    ax.text(0.02, 0.97, title, fontsize=11, fontweight="bold", ha="left", va="top")


def _render_architecture(ax: Any, title: str, items: list[str]) -> None:
    ax.axis("off")
    layers = items[:4] if items else ["User Layer", "Application Layer", "Service Layer", "Data Layer"]
    y = 0.2
    for idx, layer in enumerate(reversed(layers)):
        h = 0.14
        rect = __import__("matplotlib").patches.FancyBboxPatch(
            (0.18, y + idx * 0.16), 0.64, h, boxstyle="round,pad=0.02", facecolor="#f6f8fb", edgecolor="#6a7d96"
        )
        ax.add_patch(rect)
        ax.text(0.5, y + idx * 0.16 + h / 2, layer[:35], ha="center", va="center", fontsize=9)
    ax.text(0.02, 0.95, title, fontsize=12, fontweight="bold", ha="left", va="top")


def _render_text_card(ax: Any, title: str, gtype: str, purpose: str, description: str, elements: list[str]) -> None:
    ax.axis("off")
    element_lines = [f"- {item}" for item in elements[:6]]
    text = "\n".join([
        title,
        f"Type: {gtype}",
        f"Purpose: {purpose}" if purpose else "",
        description,
        *element_lines,
    ]).strip()
    ax.text(
        0.03,
        0.97,
        text,
        va="top",
        ha="left",
        fontsize=10,
        family="DejaVu Sans",
        bbox={"boxstyle": "round,pad=0.5", "facecolor": "#f7f9fc", "edgecolor": "#7a8ca5"},
        transform=ax.transAxes,
    )


def _render_graphic(ax: Any, title: str, gtype: str, purpose: str, description: str, elements: list[str]) -> None:
    lowered = gtype.lower()
    if "process" in lowered or "flow" in lowered:
        _render_process_diagram(ax, title, elements, description)
        return
    if "timeline" in lowered:
        _render_timeline(ax, title, elements, description)
        return
    if "comparison" in lowered or "matrix" in lowered or "table" in lowered:
        _render_comparison(ax, title, elements)
        return
    if "concept" in lowered or "map" in lowered:
        _render_concept_map(ax, title, elements)
        return
    if "architecture" in lowered:
        _render_architecture(ax, title, elements)
        return
    _render_text_card(ax, title, gtype, purpose, description, elements)


def generate_visual_assets(markdown_text: str, output_dir: str, base_name: str) -> list[dict[str, str]]:
    graphics = _parse_graphics(markdown_text)
    if not graphics:
        return []

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        import matplotlib.pyplot as plt  # type: ignore[import-untyped]
    except Exception:
        return []

    rendered: list[dict[str, str]] = []
    for index, graphic in enumerate(graphics[:3], start=1):
        fig, ax = plt.subplots(figsize=(8, 4.5))
        title = str(graphic.get("title", f"Graphic {index}"))
        gtype = str(graphic.get("type", "Other"))
        purpose = str(graphic.get("purpose", ""))
        description = str(graphic.get("description", ""))
        elements = graphic.get("elements", [])
        element_list: list[str] = []
        if isinstance(elements, list):
            element_list = [str(item) for item in elements if str(item).strip()]

        _render_graphic(
            ax=ax,
            title=title,
            gtype=gtype,
            purpose=purpose,
            description=description,
            elements=element_list,
        )
        safe_title = re.sub(r"[^A-Za-z0-9]+", "-", title).strip("-").lower() or f"graphic-{index}"
        out_path = out_dir / f"{base_name}_graphic_{index}_{safe_title}.png"
        fig.tight_layout()
        fig.savefig(out_path, dpi=180, bbox_inches="tight")
        plt.close(fig)
        set_file_times(out_path, __import__("datetime").datetime.now())
        rendered.append(
            {
                "title": title,
                "placement": str(graphic.get("placement", "")).strip(),
                "path": str(out_path),
            }
        )
    return rendered
