## Plan: Transkript zu Word und Schulungsfolien Agent

Ein Workspace-Agent wird erstellt, der einen End-to-End-Workflow orchestriert: Transkription mit bestehendem transcription/transcribe_video.py, danach hybride Zusammenfassung (lokale Struktur + LLM) als Word-Dokument, danach Schulungs-PowerPoint mit auto-generierten Visualisierungen aus Transcript-Inhalten. Der Ansatz minimiert Risiko durch Wiederverwendung der vorhandenen Transkriptionslogik, klare Artefakt-Pipeline und robuste Fallbacks ohne API.

**Steps**
1. Phase 1: Agent- und Projektkontrakt festlegen
2. Scope und Trigger fuer einen Custom Agent im Workspace definieren in .github/agents/transcript-training.agent.md; Trigger-Phrasen fuer "transkribieren", "Word-Zusammenfassung", "Schulungsfolien" aufnehmen.
3. Workspace-Regeln fuer Interpreter/Outputs in .github/copilot-instructions.md ergaenzen (Pfad zur .venv, Standard-Ausgabeordner, Artefakt-Benennung, Sprache auto-detect). Depends on 1.
4. Phase 2: Orchestrierungs-Skript erstellen
5. Neues Pipeline-Skript transcription/build_training_package.py erstellen, das folgende Schritte strikt sequenziell ausfuehrt: (a) Transkript erzeugen, (b) Summary bauen, (c) Word erzeugen, (d) PPT erzeugen, (e) Manifest schreiben. Depends on 2-3.
6. Bestehende Funktionen aus transcription/transcribe_video.py wiederverwenden statt zu duplizieren: _collect_media_files, _load_model, transcribe, save_transcript; pro Datei Ergebnis-Metadaten sammeln (Sprache, Dauer soweit verfuegbar, Segmentanzahl). Depends on 5.
7. CLI-Parameter fuer Pipeline definieren: input_path, model, output_dir, language(optional), offline, max_slides, theme(optional), --no-llm. Parallel with 6.
8. Phase 3: Hybride Zusammenfassung implementieren
9. Lokale Vorstrukturierung implementieren (Abschnitte: Lernziele, Kernthemen, Prozesse, Risiken, Handlungsempfehlungen, Glossar, Quizfragen) aus Segmenten/Keywords. Depends on 5.
10. Optionalen LLM-Feinschliff per OpenAI API integrieren; falls API-Key fehlt oder Call fehlschlaegt, auf lokale Vorstrukturierung zurueckfallen (kein Pipeline-Abbruch). Depends on 9.
11. Sprache automatisch aus Transcript-Inhalt ableiten (oder Whisper-Language nutzen, falls gesetzt); Summary-Sprache daran ausrichten. Parallel with 9-10.
12. Phase 4: Dokumente erzeugen
13. Word-Generator mit python-docx bauen: Deckblatt, detaillierte Kapitel, Punkt-für-Punkt-Aufschlüsselung,Anhang mit Volltranskript/Segmenten. Depends on 9-11.
14. PPT-Generator mit python-pptx bauen: Agenda, Lernziele, modulare Themenfolien, Uebungsfolie, Q&A, Abschlussfolie. Jede Themenfolie mit Sprecherpunkten, ohne Zeitstempel-Quellen. Depends on 9-11.
15. Auto-Visuals ohne Websuche integrieren: Diagramme/Infografiken lokal aus Inhalt ableiten (z. B. Themenhaeufigkeit, Prozessfluss, Timeline), als PNG rendern und in Folien einbetten. Depends on 14.
16. Platzhalter-/Icon-Strategie fuer Bilder und Zeichnungen definieren (lokale Assets oder generierte Formen), damit Folien immer visuell komplett sind. Parallel with 15.
17. Phase 5: Agent-Ablauf und Nutzbarkeit
18. Agent-Prompt so gestalten, dass er Nutzerinput sammelt (Dateipfad, Zielgruppe, Detailgrad, maximale Folienzahl), dann build_training_package.py ausfuehrt und am Ende alle Artefaktpfade ausgibt. Depends on 5-16.
19. README in transcription/README.md um neuen End-to-End-Workflow erweitern inkl. Beispielkommando, Abhaengigkeiten und Troubleshooting fuer fehlende OpenAI-Credentials. Depends on 18.
20. requirements.txt oder transcription/requirements.txt anlegen/aktualisieren mit openai-whisper, python-docx, python-pptx, matplotlib, openai, python-dotenv. Parallel with 5-19.

**Relevant files**
- c:/Users/karen.bugge/GIT/Tools/transcription/transcribe_video.py — Wiederverwendung von _collect_media_files, _load_model, transcribe, save_transcript als Kernbausteine.
- c:/Users/karen.bugge/GIT/Tools/transcription/README.md — bestehende Dokumentationsstruktur und CLI-Konvention fuer Erweiterung nutzen.
- c:/Users/karen.bugge/GIT/Tools/.github/agents/transcript-training.agent.md — Custom-Agent Definition (neu).
- c:/Users/karen.bugge/GIT/Tools/.github/copilot-instructions.md — Workspace-Regeln fuer Ausfuehrung/Artefakte (neu oder Erweiterung).
- c:/Users/karen.bugge/GIT/Tools/transcription/build_training_package.py — Orchestrator fuer den Gesamtworkflow (neu).
- c:/Users/karen.bugge/GIT/Tools/transcription/summary_builder.py — hybride Zusammenfassung (neu).
- c:/Users/karen.bugge/GIT/Tools/transcription/word_export.py — Word-Erzeugung (neu).
- c:/Users/karen.bugge/GIT/Tools/transcription/ppt_export.py — PowerPoint-Erzeugung (neu).
- c:/Users/karen.bugge/GIT/Tools/transcription/visuals.py — lokale Diagramm-/Visual-Generierung (neu).
- c:/Users/karen.bugge/GIT/Tools/requirements.txt — reproduzierbare Abhaengigkeiten (neu/aktualisiert).

**Verification**
1. Abhaengigkeiten installieren und Imports pruefen (whisper, docx, pptx, matplotlib, openai).
2. Pipeline mit kurzer Test-Audiodatei ausfuehren und pruefen, dass Transcript, .docx und .pptx erzeugt werden.
3. Fallback-Test ohne OPENAI_API_KEY: Pipeline darf nicht abbrechen und muss lokale Summary erzeugen.
4. Sprachtest mit DE/EN Input: Ausgabe-Sprache von Word/PPT muss automatisch passend sein.
5. Visueller Test: PPT enthaelt pro Themenblock mindestens ein visuelles Element (Diagramm, Prozessgrafik oder gezeichnete Form).
6. Agent-Test im Chat: ein einzelner Prompt soll den gesamten Ablauf starten und die finalen Artefaktpfade liefern.

**Decisions**
- AgentScope: Workspace (.github/...)
- SummarySource: Hybrid (lokale Struktur + optional LLM)
- SlideVisuals: Auto-generierte Diagramme aus Transcript-Inhalten (keine verpflichtende Web-Bildsuche)
- OutputLanguage: Automatisch aus Transcript erkennen
- Included scope: End-to-End-Orchestrierung, Word + PPT Export, Agent-Definition, Dokumentation
- Excluded scope: Web-Crawling fuer Stock-Fotos, unternehmensspezifisches Corporate-Design-Template, menschliche Fachredaktion der Inhalte

**Further Considerations**
1. LLM-Modellwahl fuer Summary-Feinschliff als konfigurierbarer Parameter (z. B. gpt-4.1-mini vs. gpt-5-mini), Standard auf kostenbewusste Option.
2. Optionale Wiederverwendung vorhandener Bildordner fuer kundenspezifische Visuals (falls spaeter benoetigt).