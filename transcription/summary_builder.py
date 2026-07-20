# -*- coding: utf-8 -*-
"""LLM-driven content generation from transcripts for Word and PowerPoint outputs."""

from __future__ import annotations

import os
from typing import Optional

from github_models import chat_completion, github_models_enabled, github_models_model


def _debug_enabled() -> bool:
    return os.environ.get("TRANSCRIPTION_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}


def _debug_log(message: str) -> None:
    if _debug_enabled():
        print(f"[summary_builder] {message}")


def _get_transcript_max_size() -> int:
    """Get maximum transcript size in characters from environment variable.
    
    Default: 10000 characters (approx. 2500 tokens)
    Can be overridden with TRANSCRIPT_MAX_CHARS environment variable.
    Set to 0 or negative to disable limiting.
    """
    try:
        max_size = int(os.environ.get("TRANSCRIPT_MAX_CHARS", "10000"))
        return max(0, max_size)
    except (ValueError, TypeError):
        return 10000


def _limit_transcript_size(transcript_text: str, max_chars: Optional[int] = None) -> tuple[str, bool]:
    """Limit transcript size and return (limited_transcript, was_truncated).
    
    Args:
        transcript_text: The original transcript.
        max_chars: Maximum characters. If None, uses TRANSCRIPT_MAX_CHARS env var.
    
    Returns:
        Tuple of (limited_transcript, was_truncated).
    """
    if max_chars is None:
        max_chars = _get_transcript_max_size()
    
    if max_chars <= 0:
        return transcript_text, False
    
    if len(transcript_text) <= max_chars:
        return transcript_text, False
    
    # Try to truncate at a sentence boundary for better context
    truncated = transcript_text[:max_chars]
    
    # Find the last complete sentence (ending with . ! or ?)
    for i in range(len(truncated) - 1, max(0, len(truncated) - 500), -1):
        if truncated[i] in ".!?":
            truncated = truncated[:i + 1]
            break
    
    _debug_log(f"Transcript truncated: {len(transcript_text)} → {len(truncated)} chars | was_truncated=True")
    return truncated, True


WORD_SYSTEM_PROMPT = """You are an expert AI assistant specialized in analyzing video transcripts and creating professional Word document summaries.

Your task is to transform a raw transcript text into a clear, well-structured, business-ready summary document. The output will later be converted into a Microsoft Word document, so structure, hierarchy, clarity, and formatting guidance are important.

You must:
1. Analyze the transcript carefully and identify the main topics, key messages, decisions, explanations, examples, risks, open questions, and action items.
2. Create a detailed but concise summary that preserves the meaning of the original transcript.
3. Organize the content using meaningful headings and subheadings.
4. Highlight the most important points using bullet lists where appropriate.
5. Extract terminology, concepts, processes, or relationships that would benefit from visual explanation.
6. Suggest useful graphics, diagrams, or visual representations where they help explain the content.
7. For each suggested graphic, provide a clear description that can be used to generate or draw the graphic later.
8. Do not invent facts that are not supported by the transcript.
9. If something is unclear in the transcript, mark it as unclear instead of guessing.
10. Keep the tone professional, neutral, and suitable for a business or training document.

Output requirements:
- Use clear Markdown-style structure.
- Use heading levels such as:
  - # Document Title
  - ## Main Section
  - ### Subsection
- Include an executive summary near the beginning.
- Include a section for key takeaways.
- Include a section for detailed topic-by-topic summary.
- Include a section for suggested graphics and diagrams.
- Include a section for action items, risks, open questions, or follow-ups if available in the transcript.
- Include a section with relevant keywords or glossary terms if useful.
- Do not include unnecessary filler text.
- Do not mention that you are an AI model.
- Do not expose, repeat, or request any API keys or credentials.

When suggesting graphics, use the following format:

### Suggested Graphic: <Graphic Title>
- Type: <Flowchart | Process diagram | Concept map | Timeline | Table | Architecture diagram | Comparison matrix | Other>
- Purpose: <Why this visual is useful>
- Description: <Detailed visual description>
- Elements to include:
  - <Element 1>
  - <Element 2>
  - <Element 3>
- Suggested placement in document: <Section name>

The final response must be ready to be passed to a Word document generation step."""


WORD_USER_PROMPT_TEMPLATE = '''Analyze the following video transcript and create a structured summary that can be converted into a Microsoft Word document.

The summary should include:
1. A clear document title.
2. An executive summary.
3. The most important key points.
4. A detailed topic-by-topic breakdown.
5. Meaningful headings and subheadings.
6. Important definitions, concepts, examples, or explanations from the transcript.
7. Any decisions, risks, open questions, or action items mentioned.
8. Suggestions for useful graphics or diagrams that help explain the content.
9. For each suggested graphic, provide a detailed description that can be used by a document generation script to create or insert the visual.
10. A short conclusion.

Important instructions:
- Use only information from the transcript.
- Do not add external knowledge unless explicitly stated in the transcript.
- If the transcript contains unclear or incomplete statements, mark them as unclear.
- Preserve the original meaning of the speaker.
- Make the output suitable for a professional Word document.
- Use Markdown-style headings and bullet points.
- Be detailed, but avoid unnecessary repetition.

Transcript:
"""
{{TRANSCRIPT_TEXT}}
"""'''


PPT_SYSTEM_PROMPT = """You are an expert AI assistant specialized in transforming video transcripts into compelling single-slide PowerPoint presentations with strong visual elements.

Your task is to analyze a video transcript and create a detailed specification for exactly ONE professional PowerPoint slide. The slide must be VISUAL-FIRST and show the core content as a graphic, diagram, or structured visual rather than just bullet points.

Critical requirements:
1. The slide must prioritize visual representation over text.
2. Choose the most suitable visual type from the list below based on the transcript content.
3. Provide enough detail so that a PowerPoint generation script can create the actual visual shapes and layouts.
4. Use only information from the transcript—do not add external knowledge.
5. If information is unclear, mark it as unclear rather than guessing.
6. Create content suitable for professional business or training presentations.

VISUAL TYPES YOU CAN USE:
- Process Flow: Sequential steps with arrows connecting boxes horizontally
- Workflow: Similar to process flow, showing sequential steps or work stages
- Timeline: Chronological events shown vertically or horizontally with connecting line and markers
- Concept Map: Central concept with radiating related concepts and connections
- Comparison Framework: Side-by-side or grid-based comparison of items or options
- Decision Tree: Hierarchical tree with root node and decision branches
- Cause and Effect (Fishbone): Central effect with multiple cause branches
- System or Architecture Diagram: Layered boxes showing system components or layers
- Hub and Spoke: Central hub with radiating spokes to related elements
- Value Chain: Sequential flow of value-adding steps

CRITICAL OUTPUT FORMAT (must follow exactly):

# [Slide Title]

## Recommended Visual Type
[One of the visual types above, exactly as listed]

## Slide Purpose
[One clear sentence: what should the viewer understand from this slide?]

## Slide Layout Description
[Describe the visual layout in detail: where are elements positioned, how do they relate, what flows or connections exist]

## Visual Elements
[List each visual element as a separate line. Keep labels SHORT (5-15 words max)]
- Element 1: [description]
- Element 2: [description]
- Element 3: [description]

## Flow or Relationship Logic
[Explain how elements connect: left-to-right flow, top-down hierarchy, radial pattern, cycles, dependencies, etc.]

## Text to Place on the Slide
[Provide ONLY the exact text/labels that appear on the slide. Keep each label SHORT.]

## Speaker Notes
[Optional: brief presenter note if helpful. Keep very short.]

## Design Guidance
- Color Style: [e.g., blue tones, professional grayscale, warm colors]
- Key Visual Elements: [describe shapes, connectors, or special visual treatment]
- Emphasis: [what should stand out most]
- What to Avoid: [what not to include]

IMPORTANT NOTES FOR RENDERING:
- Keep element labels SHORT and scannable (max 5-15 words each)
- Do not include long paragraphs on the slide
- Use visual grouping and hierarchy to show relationships
- Provide clear flow direction (arrows, lines, sequence indicators)
- The generation script will create actual shapes based on your descriptions
"""


PPT_USER_PROMPT_TEMPLATE = '''Analyze the following video transcript and create content for exactly ONE professional PowerPoint slide.

Create the slide specification using this exact structure (each section is required):

# Slide Title
[A clear, concise title that captures the main idea]

## Recommended Visual Type
[Choose ONE from: Process Flow, Timeline, Concept Map, Comparison, Decision Tree, Cause-and-Effect, System Diagram, Hub-and-Spoke, or Other]

## Slide Purpose
[One sentence: what the viewer should understand]

## Visual Elements
[List 4-6 key elements, one per line, as short labels (5-15 words each)]
- Element 1
- Element 2
- Element 3

## Flow or Relationship Logic
[Explain how elements connect: direction, hierarchy, dependencies]

## Text to Place on the Slide
[Only the exact text/labels that appear on the slide - keep SHORT]

## Speaker Notes
[Optional brief presenter note]

## Design Guidance
Color Style: [blue, professional, warm, etc.]
Key Visual Elements: [shapes, connectors, patterns]
Emphasis: [what stands out]
What to Avoid: [don't include]

Remember:
- Keep all labels and text SHORT (5-15 words max)
- Do not add external knowledge beyond the transcript
- Use ONLY information from the transcript
- Make the slide visual-first, not text-heavy

Transcript:
"""
{{TRANSCRIPT_TEXT}}
"""'''


def _strip_markdown_fence(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines:
            lines = lines[1:]
        while lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return cleaned


def generate_word_document_content(
    transcript_text: str,
    llm_model: Optional[str] = None,
) -> Optional[dict[str, str]]:
    if not github_models_enabled():
        _debug_log("Word generation skipped: github_models_enabled() is false")
        return None

    # Apply transcript size limit
    limited_transcript, was_truncated = _limit_transcript_size(transcript_text)
    
    model = llm_model or github_models_model()
    _debug_log(f"Word generation started | model={model} | transcript_chars={len(limited_transcript)} | truncated={was_truncated}")
    
    # Build user prompt with truncation note if necessary
    prompt_text = limited_transcript
    if was_truncated:
        prompt_text = f"[NOTE: The transcript below was truncated to the first {len(limited_transcript)} characters due to size limits. Please work with the available content.]\n\n{limited_transcript}"
    
    user_prompt = WORD_USER_PROMPT_TEMPLATE.replace("{{TRANSCRIPT_TEXT}}", prompt_text)
    output_text = chat_completion(
        model=model,
        messages=[
            {"role": "system", "content": WORD_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
        max_tokens=3200,
    )
    if not output_text:
        _debug_log("Word generation returned empty output from chat_completion")
        return None
    markdown = _strip_markdown_fence(output_text)
    _debug_log(f"Word generation succeeded | output_chars={len(markdown)}")
    return {"markdown": markdown}



def generate_single_slide_content(
    transcript_text: str,
    llm_model: Optional[str] = None,
) -> Optional[dict[str, str]]:
    if not github_models_enabled():
        _debug_log("PPT generation skipped: github_models_enabled() is false")
        return None

    # Apply transcript size limit
    limited_transcript, was_truncated = _limit_transcript_size(transcript_text)
    
    model = llm_model or github_models_model()
    _debug_log(f"PPT generation started | model={model} | transcript_chars={len(limited_transcript)} | truncated={was_truncated}")
    
    # Build user prompt with truncation note if necessary
    prompt_text = limited_transcript
    if was_truncated:
        prompt_text = f"[NOTE: The transcript below was truncated to the first {len(limited_transcript)} characters due to size limits. Please work with the available content.]\n\n{limited_transcript}"
    
    user_prompt = PPT_USER_PROMPT_TEMPLATE.replace("{{TRANSCRIPT_TEXT}}", prompt_text)
    output_text = chat_completion(
        model=model,
        messages=[
            {"role": "system", "content": PPT_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
        max_tokens=2500,  # Increased from 1600 to allow more detailed slide specs
    )
    if not output_text:
        _debug_log("PPT generation returned empty output from chat_completion")
        return None
    
    markdown = _strip_markdown_fence(output_text)
    
    # Validate that we have meaningful content (at least a title)
    if not markdown or len(markdown.strip()) < 20:
        _debug_log(f"PPT generation returned insufficient content | output_chars={len(markdown)} | raw_output_chars={len(output_text)}")
        _debug_log(f"Raw output (first 500 chars): {output_text[:500]}")
        return None
    
    _debug_log(f"PPT generation succeeded | output_chars={len(markdown)}")
    return {"markdown": markdown}
