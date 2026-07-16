# -*- coding: utf-8 -*-
"""Generates local visual assets (charts/diagrams) for training slides."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def _slugify(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-")


def _theme() -> dict[str, str]:
    return {
        "navy": "#0B1F3A",
        "blue": "#1757A6",
        "blue_soft": "#DCEBFF",
        "muted": "#5B677A",
        "line": "#D8E2EC",
        "callout": "#FFF7ED",
        "callout_text": "#9A3412",
        "white": "#FFFFFF",
    }


def _save_figure(fig, path: str) -> str:
    fig.tight_layout()
    fig.savefig(path, dpi=160, facecolor="white", bbox_inches="tight")
    return path


def generate_visual_assets(
    summary: dict[str, Any],
    output_dir: str,
    base_name: str,
) -> dict[str, str]:
    """Create PNG visuals from summary content and return paths."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    base = _slugify(base_name) or "training"

    try:
        import matplotlib.pyplot as plt  # type: ignore[import-untyped]
        from matplotlib.patches import Rectangle  # type: ignore[import-untyped]
    except Exception:
        return {}

    assets: dict[str, str] = {}
    colors = _theme()

    keywords = summary.get("keywords", [])
    terms: list[str] = []
    counts: list[int] = []
    for item in keywords[:8]:
        if isinstance(item, dict):
            term = str(item.get("term", ""))
            count = int(item.get("count", 0))
        else:
            term = str(item[0]) if len(item) > 0 else ""
            count = int(item[1]) if len(item) > 1 else 0
        if term and count > 0:
            terms.append(term)
            counts.append(count)

    if terms and counts:
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.barh(terms[::-1], counts[::-1], color=colors["blue"])
        ax.set_title("Top Terms")
        ax.set_xlabel("Frequency")
        bar_path = os.path.join(output_dir, f"{base}_top_terms.png")
        _save_figure(fig, bar_path)
        plt.close(fig)
        assets["top_terms"] = bar_path

    process_steps = summary.get("processes", [])
    if isinstance(process_steps, list) and process_steps:
        fig, ax = plt.subplots(figsize=(12, 3.5))
        ax.axis("off")

        x_positions = [0.1, 0.4, 0.7]
        labels = [str(step) for step in process_steps[:3]]
        while len(labels) < 3:
            labels.append("Step")

        for idx, (x, label) in enumerate(zip(x_positions, labels)):
            ax.text(
                x,
                0.5,
                label,
                ha="center",
                va="center",
                fontsize=11,
                bbox={"boxstyle": "round,pad=0.4", "fc": colors["blue_soft"], "ec": colors["blue"]},
                wrap=True,
            )
            if idx < 2:
                ax.annotate(
                    "",
                    xy=(x_positions[idx + 1] - 0.09, 0.5),
                    xytext=(x + 0.09, 0.5),
                    arrowprops={"arrowstyle": "->", "lw": 2, "color": colors["blue"]},
                )

        flow_path = os.path.join(output_dir, f"{base}_process_flow.png")
        _save_figure(fig, flow_path)
        plt.close(fig)
        assets["process_flow"] = flow_path

        # Create a branching decision diagram similar to the example deck.
        fig, ax = plt.subplots(figsize=(12, 4.2))
        ax.axis("off")
        nodes = [
            (0.12, 0.52, "Cooling"),
            (0.37, 0.52, "Packart?"),
            (0.68, 0.72, "Individual\nPacking"),
            (0.68, 0.32, "Sorting /\nWeighing"),
            (0.9, 0.32, "Group\nPacking"),
        ]
        for x, y, label in nodes:
            ax.text(
                x,
                y,
                label,
                ha="center",
                va="center",
                fontsize=12,
                color=colors["navy"],
                bbox={"boxstyle": "round,pad=0.45", "fc": colors["blue_soft"], "ec": colors["blue"]},
            )
        arrows = [
            ((0.18, 0.52), (0.31, 0.52)),
            ((0.43, 0.57), (0.6, 0.68)),
            ((0.43, 0.47), (0.6, 0.36)),
            ((0.76, 0.32), (0.84, 0.32)),
        ]
        for start, end in arrows:
            ax.annotate("", xy=end, xytext=start, arrowprops={"arrowstyle": "->", "lw": 2.2, "color": colors["blue"]})
        decision_path = os.path.join(output_dir, f"{base}_decision_tree.png")
        _save_figure(fig, decision_path)
        plt.close(fig)
        assets["decision_tree"] = decision_path

        # Create a hold/release state illustration.
        fig, ax = plt.subplots(figsize=(10.5, 3.4))
        ax.axis("off")
        hold_nodes = [
            (0.12, 0.5, "Mixing"),
            (0.38, 0.5, "Hold"),
            (0.64, 0.5, "Release by\nSupervisor"),
            (0.88, 0.5, "Continue\nProduction"),
        ]
        fills = [colors["blue_soft"], colors["callout"], colors["blue_soft"], colors["blue_soft"]]
        edges = [colors["blue"], colors["callout_text"], colors["blue"], colors["blue"]]
        for (x, y, label), fill, edge in zip(hold_nodes, fills, edges):
            ax.text(
                x,
                y,
                label,
                ha="center",
                va="center",
                fontsize=11,
                color=colors["navy"],
                bbox={"boxstyle": "round,pad=0.45", "fc": fill, "ec": edge},
            )
        for start, end, color in [((0.18, 0.5), (0.31, 0.5), colors["blue"]), ((0.44, 0.5), (0.57, 0.5), colors["callout_text"]), ((0.71, 0.5), (0.82, 0.5), colors["blue"])]:
            ax.annotate("", xy=end, xytext=start, arrowprops={"arrowstyle": "->", "lw": 2.2, "color": color})
        hold_path = os.path.join(output_dir, f"{base}_hold_release.png")
        _save_figure(fig, hold_path)
        plt.close(fig)
        assets["hold_release"] = hold_path

    # Comparison visual for route variants.
    topics = summary.get("topics", []) if isinstance(summary.get("topics"), list) else []
    if topics:
        fig, ax = plt.subplots(figsize=(12, 4.8))
        ax.axis("off")
        columns = [
            (0.05, "Variante A: Direkter Pfad", ["Nach Cooling direkt zu Packing", "Weniger Zwischenschritte", "Linearer Endpfad"]),
            (0.53, "Variante B: Erweiterter Pfad", ["Sorting / Weighing vor Packing", "Nicht-sequenzielle Aktivitaeten", "Mehr Entscheidungslogik"]),
        ]
        for left, header, lines in columns:
            ax.add_patch(Rectangle((left, 0.15), 0.4, 0.68, facecolor=colors["blue_soft"], edgecolor=colors["line"], linewidth=1.5))
            ax.text(left + 0.02, 0.76, header, fontsize=14, color=colors["navy"], weight="bold", va="top")
            for idx, line in enumerate(lines):
                ax.text(left + 0.03, 0.62 - idx * 0.16, f"• {line}", fontsize=11, color=colors["muted"], va="top")
        comparison_path = os.path.join(output_dir, f"{base}_variant_comparison.png")
        _save_figure(fig, comparison_path)
        plt.close(fig)
        assets["variant_comparison"] = comparison_path

    # Non-sequential sorting illustration.
    fig, ax = plt.subplots(figsize=(9.5, 4.6))
    ax.axis("off")
    positions = [(0.2, 0.72), (0.45, 0.55), (0.28, 0.28), (0.58, 0.78)]
    for idx, (x, y) in enumerate(positions, start=1):
        ax.text(
            x,
            y,
            f"Cookie {idx}",
            ha="center",
            va="center",
            fontsize=12,
            color=colors["navy"],
            bbox={"boxstyle": "circle,pad=0.35", "fc": colors["blue_soft"], "ec": colors["blue"]},
        )
    ax.text(0.82, 0.52, "Sorting /\nWeighing", ha="center", va="center", fontsize=13, color=colors["navy"], bbox={"boxstyle": "round,pad=0.5", "fc": colors["callout"], "ec": colors["callout_text"]})
    for x, y in positions:
        ax.annotate("", xy=(0.74, 0.52), xytext=(x + 0.05, y), arrowprops={"arrowstyle": "->", "lw": 2, "color": colors["blue"]})
    sorting_path = os.path.join(output_dir, f"{base}_non_sequential_sorting.png")
    _save_figure(fig, sorting_path)
    plt.close(fig)
    assets["non_sequential_sorting"] = sorting_path

    return assets
