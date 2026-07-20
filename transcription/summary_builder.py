# -*- coding: utf-8 -*-
"""Builds a detailed training summary from transcripts with optional LLM refinement."""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Optional

from github_models import chat_completion, github_models_enabled, github_models_model


def detect_language(text: str, fallback: Optional[str] = None) -> str:
    """Heuristic language detection for German vs English."""
    if fallback:
        return fallback.lower()

    lowered = text.lower()
    german_markers = [
        " und ",
        " nicht ",
        " ist ",
        " die ",
        " der ",
        " das ",
        " fuer ",
        " ueber ",
        " mit ",
        "schulung",
        "prozess",
        "aenderung",
    ]
    english_markers = [
        " and ",
        " not ",
        " is ",
        " the ",
        " this ",
        " with ",
        " training ",
        " process ",
        " change ",
    ]

    german_score = sum(lowered.count(m) for m in german_markers)
    english_score = sum(lowered.count(m) for m in english_markers)

    if re.search(r"[aeiou]", lowered) and re.search(r"[aeiou]", lowered):
        # Keep heuristic simple and deterministic; marker scores decide final language.
        pass

    return "de" if german_score >= english_score else "en"


def _sentences(text: str) -> list[str]:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return []
    parts = re.split(r"(?<=[.!?])\s+", cleaned)
    return [p.strip() for p in parts if p.strip()]


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z][a-zA-Z\-]{2,}", text.lower())


def _stopwords(language: str) -> set[str]:
    common = {
        "from",
        "into",
        "about",
        "this",
        "that",
        "with",
        "have",
        "will",
        "your",
        "their",
        "also",
        "because",
        "durch",
        "sowie",
    }
    de = {
        "und",
        "der",
        "die",
        "das",
        "ein",
        "eine",
        "ist",
        "mit",
        "fuer",
        "dass",
        "nicht",
        "sich",
        "werden",
        "kann",
        "kannst",
        "oder",
        "aber",
        "zum",
        "zur",
    }
    en = {
        "and",
        "the",
        "for",
        "that",
        "with",
        "this",
        "are",
        "was",
        "were",
        "you",
        "they",
        "can",
        "will",
        "not",
        "from",
        "into",
        "about",
        "then",
    }
    return common | (de if language == "de" else en)


def _top_keywords(text: str, language: str, top_n: int = 12) -> list[tuple[str, int]]:
    words = _tokenize(text)
    blocked = _stopwords(language)
    filtered = [w for w in words if w not in blocked and len(w) > 2]
    counts = Counter(filtered)
    return counts.most_common(top_n)


def _chunk_points(items: list[str], max_items: int) -> list[str]:
    return items[:max_items] if items else []


def _matching_sentences(text: str, patterns: list[str], max_items: int = 3) -> list[str]:
    sentences = _sentences(text)
    if not sentences:
        return []
    matches: list[str] = []
    for sentence in sentences:
        lowered = sentence.lower()
        if any(re.search(pattern, lowered) for pattern in patterns):
            matches.append(sentence)
    return _chunk_points(matches, max_items)


def _section_titles(language: str) -> dict[str, str]:
    if language == "de":
        return {
            "goals": "Kernaussagen",
            "topics": "Inhaltliche Schwerpunkte",
            "processes": "Ablauflogik und Reihenfolge",
            "risks": "Einschraenkungen und Ausnahmen",
            "actions": "Beobachtete Entscheidungen",
            "glossary": "Glossar",
            "quiz": "Prueffragen",
            "summary": "Kurzueberblick",
        }
    return {
        "goals": "Learning Objectives",
        "topics": "Core Topics",
        "processes": "Processes",
        "risks": "Risks and Pitfalls",
        "actions": "Recommended Actions",
        "glossary": "Glossary",
        "quiz": "Quiz Questions",
        "summary": "Overview",
    }


@dataclass
class SummaryResult:
    language: str
    titles: dict[str, str]
    overview: list[str]
    goals: list[str]
    topics: list[str]
    processes: list[str]
    risks: list[str]
    actions: list[str]
    glossary: list[dict[str, str]]
    quiz: list[str]
    keywords: list[tuple[str, int]]
    source: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "language": self.language,
            "titles": self.titles,
            "overview": self.overview,
            "goals": self.goals,
            "topics": self.topics,
            "processes": self.processes,
            "risks": self.risks,
            "actions": self.actions,
            "glossary": self.glossary,
            "quiz": self.quiz,
            "keywords": [{"term": k, "count": c} for k, c in self.keywords],
            "source": self.source,
        }


def _build_local_summary(text: str, language: str) -> SummaryResult:
    titles = _section_titles(language)
    sents = _sentences(text)
    keywords = _top_keywords(text, language)

    top_terms = [k for k, _ in keywords[:6]]
    key_sentences = _chunk_points(sents, 8)

    if language == "de":
        overview = _chunk_points(sents, 3)
        goals = _matching_sentences(
            text,
            [r"\b(ziel|ziele|objective|objectives|purpose|fokus|wichtig)\b"],
        )
        processes = _matching_sentences(
            text,
            [r"\b(schritt|schritte|prozess|ablauf|zuerst|danach|dann|anschlie\u00dfend|anschließend|before|after|next)\b"],
        )
        risks = _matching_sentences(
            text,
            [r"\b(risiko|risiken|problem|probleme|warnung|fehler|achtung|issue|risk|problematic)\b"],
        )
        actions = _matching_sentences(
            text,
            [r"\b(soll|sollte|muss|mussen|müssen|empfehlen|empfohlen|action|act|next step|naechster schritt|nächster schritt)\b"],
        )
    else:
        overview = _chunk_points(sents, 3)
        goals = _matching_sentences(
            text,
            [r"\b(goal|goals|objective|objectives|purpose|important|focus)\b"],
        )
        processes = _matching_sentences(
            text,
            [r"\b(step|steps|process|workflow|first|then|next|after|before)\b"],
        )
        risks = _matching_sentences(
            text,
            [r"\b(risk|risks|problem|problems|warning|issue|error|challenge|caution)\b"],
        )
        actions = _matching_sentences(
            text,
            [r"\b(should|must|recommend|recommended|action|next step|need to|needs to)\b"],
        )

    if not overview:
        overview = _chunk_points(sents, 3)

    topics = _chunk_points(key_sentences, 6)
    glossary = [
        {
            "term": term,
            "definition": (
                f"Im Transkript haeufig verwendeter Begriff."
                if language == "de"
                else "Frequently used term in the transcript."
            ),
        }
        for term, _ in keywords[:8]
    ]

    if language == "de":
        quiz = [
            "Welche drei inhaltlichen Kernaussagen lassen sich direkt aus dem Transkript belegen?",
            "An welchen Stellen verzweigt der beschriebene Ablauf?",
            "Welche Begriffe sind fuer das Verstaendnis unverzichtbar?",
        ]
    else:
        quiz = [
            "What are the three primary objectives of this training?",
            "How does the standard process run from analysis to review?",
            "Which risks occur most often and how should they be mitigated?",
        ]

    return SummaryResult(
        language=language,
        titles=titles,
        overview=overview,
        goals=goals,
        topics=topics,
        processes=processes,
        risks=risks,
        actions=actions,
        glossary=glossary,
        quiz=quiz,
        keywords=keywords,
        source="local",
    )


def _extract_json_blob(raw_text: str) -> Optional[dict[str, Any]]:
    try:
        return json.loads(raw_text)
    except Exception:
        pass

    match = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except Exception:
        return None


def _llm_refine_summary(local_summary: SummaryResult, transcript_text: str, llm_model: str) -> Optional[dict[str, Any]]:
    if not github_models_enabled():
        return None

    language = local_summary.language
    instruction = (
        "Antworte auf Deutsch" if language == "de" else "Respond in English"
    )

    prompt = (
        f"{instruction}. Create a structured, transcript-faithful detailed summary. "
        "Use only information from the transcript. Do not add external context or invented details. "
        "Do not write a training handout. Keep wording factual and anchored in transcript content. "
        "Return valid JSON with keys: overview, goals, topics, processes, risks, actions, glossary. "
        "All keys must contain arrays. glossary must be an array of objects with keys term and definition. "
        "Use clear chapter headings and concise section-friendly phrasing. The language must match the transcript language."
    )

    output_text = chat_completion(
        model=llm_model,
        messages=[
            {
                "role": "system",
                "content": "You transform transcripts into structured, factual summaries for documentation. You use only transcript content, keep the same language as the transcript, and provide clear chapter headings without inventing details.",
            },
            {
                "role": "user",
                "content": (
                    f"Local summary JSON:\n{json.dumps(local_summary.to_dict(), ensure_ascii=False)}\n\n"
                    f"Transcript:\n{transcript_text[:12000]}\n\n{prompt}"
                ),
            },
        ],
        temperature=0.2,
        max_tokens=1800,
        response_format={"type": "json_object"},
    )
    if not output_text:
        return None

    return _extract_json_blob(output_text)


def generate_word_blueprint(
    transcript_text: str,
    preferred_language: Optional[str] = None,
    llm_model: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    if not github_models_enabled():
        return None

    language = detect_language(transcript_text, fallback=preferred_language)
    instruction = "Antworte auf Deutsch" if language == "de" else "Respond in English"
    model = llm_model or github_models_model()
    prompt = (
        f"{instruction}. Create JSON for a structured Word document derived only from the transcript. "
        "Do not use external sources and do not invent any content. Keep it factual, easy to read, and in the same language as the transcript. "
        "Return valid JSON with keys: title, subtitle, overview, sections, takeaways. "
        "overview must be an array of brief summary paragraphs. sections must be an array of objects with keys heading and bullets. "
        "Use clear chapter headings. takeaways must be an array of concise bullet points."
    )

    output_text = chat_completion(
        model=model,
        messages=[
            {"role": "system", "content": "You create structured Word document blueprints from transcripts only. You keep the same language as the transcript and do not invent details."},
            {"role": "user", "content": f"Transcript:\n{transcript_text[:12000]}\n\n{prompt}"},
        ],
        temperature=0.2,
        max_tokens=2200,
        response_format={"type": "json_object"},
    )
    return _extract_json_blob(output_text) if output_text else None


def generate_ppt_blueprint(
    transcript_text: str,
    preferred_language: Optional[str] = None,
    max_slides: int = 12,
    llm_model: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    if not github_models_enabled():
        return None

    language = detect_language(transcript_text, fallback=preferred_language)
    instruction = "Antworte auf Deutsch" if language == "de" else "Respond in English"
    model = llm_model or github_models_model()
    prompt = (
        f"{instruction}. Create JSON for a concise PowerPoint slide based only on the transcript. "
        "Do not use external sources and do not invent any content. Keep it didactically understandable and in the same language as the transcript. "
        "Return valid JSON with keys: title, subtitle, slides. "
        f"slides must contain at most {min(max_slides, 2)} items. "
        "Each slide must be an object with keys: slide_type, title, subtitle, bullets, visual_hint, speaker_notes, callout, labels. "
        "slide_type should be one of: agenda, statement, process, comparison, concept_grid, recap. "
        "Keep the slide content concise, summary-focused, and suitable for a short training slide. "
        "If no suitable graphic can be derived directly from the transcript, use a simple schematic representation or omit the graphic hint."
    )

    output_text = chat_completion(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "You create concise, transcript-only PowerPoint slide blueprints. You keep the same language as the transcript, do not invent details, and only describe graphics that can be directly derived from the transcript.",
            },
            {"role": "user", "content": f"Transcript:\n{transcript_text[:12000]}\n\n{prompt}"},
        ],
        temperature=0.2,
        max_tokens=2200,
        response_format={"type": "json_object"},
    )
    return _extract_json_blob(output_text) if output_text else None


def build_hybrid_summary(
    transcript_text: str,
    preferred_language: Optional[str] = None,
    use_llm: bool = True,
    llm_model: Optional[str] = None,
) -> dict[str, Any]:
    """Build local summary and optionally refine it with LLM output."""
    language = detect_language(transcript_text, fallback=preferred_language)
    local = _build_local_summary(transcript_text, language)

    if not use_llm:
        return local.to_dict()

    model = llm_model or github_models_model()
    refined = _llm_refine_summary(local, transcript_text, llm_model=model)
    if not refined:
        return local.to_dict()

    final = local.to_dict()
    for key in ["overview", "goals", "topics", "processes", "risks", "actions", "glossary", "quiz"]:
        if key in refined and isinstance(refined[key], list) and refined[key]:
            final[key] = refined[key]
    final["source"] = "hybrid"
    return final
