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
        overview = [
            "Der folgende Inhalt gibt die Aussagen des Transkripts strukturiert und moeglichst nah am Original wieder.",
            "Die Abschnitte sind inhaltlich gegliedert und nicht als Schulungsunterlage formuliert.",
            f"Hauefige Begriffe: {', '.join(top_terms) if top_terms else 'keine eindeutigen Top-Begriffe'}.",
        ]
        goals = [
            "Welche zentralen Aussagen werden im Transkript mehrfach betont?",
            "Welche Themen werden in welcher Reihenfolge behandelt?",
            "Welche Begriffe oder Entscheidungen sind fuer das Gesamtverstaendnis wesentlich?",
        ]
        processes = [
            "Abfolge der im Transkript beschriebenen Schritte und Entscheidungsstellen.",
            "Bedingungen fuer Abzweigungen oder alternative Verlaeufe.",
            "Rueckkehr in den Hauptablauf nach Ausnahmen oder Zusatzschritten.",
        ]
        risks = [
            "Stellen mit unklaren Voraussetzungen oder offenen Annahmen.",
            "Passagen mit potenziell mehrdeutiger Interpretation.",
            "Ausnahmen, die den Standardablauf veraendern.",
        ]
        actions = [
            "Explizit genannte Entscheidungen im Prozessverlauf markieren.",
            "Genannte Optionen und deren Folgen gegeneinander abgrenzen.",
            "Falls vorhanden: Verantwortliche Rollen aus dem Wortlaut herausstellen.",
        ]
    else:
        overview = [
            "The material covers multiple related topics with an operational focus.",
            "The key content has been transformed into a structured training package.",
            f"Frequent terms: {', '.join(top_terms) if top_terms else 'no dominant terms detected'}.",
        ]
        goals = [
            "Identify and explain the core concepts confidently.",
            "Apply process steps in the correct sequence.",
            "Spot risks early and define practical mitigation actions.",
        ]
        processes = [
            "Capture the initial context and constraints.",
            "Translate content into actionable workflow steps.",
            "Review, document, and close the feedback loop.",
        ]
        risks = [
            "Unclear ownership can delay execution.",
            "Lack of standardization can reduce output quality.",
            "Incomplete documentation can block knowledge transfer.",
        ]
        actions = [
            "Define clear ownership and decision points.",
            "Use templates and checklists for repeatability.",
            "Include regular quality reviews in the workflow.",
        ]

    topics = _chunk_points(key_sentences, 6)
    glossary = [
        {
            "term": term,
            "definition": (
                f"Hauefig verwendeter Begriff im Material mit hoher Relevanz fuer die Schulung."
                if language == "de"
                else "Frequently used term in the source material with high relevance for training."
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
        "Do not write a training handout. Keep wording factual and anchored in transcript content. "
        "Return valid JSON with keys: overview, goals, topics, processes, risks, actions, glossary. "
        "All keys must contain arrays. glossary must be an array of objects with keys term and definition. "
        "Use section-friendly phrasing so the output can be used directly as Word document headings and sub-sections."
    )

    output_text = chat_completion(
        model=llm_model,
        messages=[
            {
                "role": "system",
                "content": "You transform transcripts into structured, factual detailed summaries for documentation. You give a detailed point-by-point breakdown and add headings if useful.",
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
        f"{instruction}. Create JSON for a detailed Word document derived from a transcript. "
        "Do not create a training handout. Keep it factual, structured, and close to the transcript. "
        "Return valid JSON with keys: title, subtitle, overview, sections, takeaways. "
        "overview must be an array of paragraphs. sections must be an array of objects with keys heading and bullets. "
        "takeaways must be an array of bullet points."
    )

    output_text = chat_completion(
        model=model,
        messages=[
            {"role": "system", "content": "You create structured Word document blueprints from transcripts."},
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
        f"{instruction}. Create JSON for a PowerPoint deck based on a transcript. "
        "Use a structure similar to a compact German training deck with around 8 to 10 slides: "
        "title slide, learning objectives/agenda, problem framing, reference scenario, key process or hold state, decision point, comparison of variants, operational concept slide, and closing summary/transfer questions. "
        "Return valid JSON with keys: title, subtitle, slides. "
        f"slides must contain at most {max_slides} items. "
        "Each slide must be an object with keys: slide_type, title, subtitle, bullets, visual_hint, speaker_notes, callout, labels. "
        "slide_type should be one of: agenda, statement, process, comparison, concept_grid, recap. "
        "labels should be used for short process steps, comparison headers, or grid labels. "
        "Keep bullets concise and presentation-ready. Prefer concrete, didactic wording over generic summaries."
    )

    output_text = chat_completion(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "You create concise but visually structured training slide blueprints from transcripts. Use explicit slide progression and output content suitable for layouted presentation slides.",
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
