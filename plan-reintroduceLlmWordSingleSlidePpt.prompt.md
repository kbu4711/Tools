## Plan: Reintroduce LLM Word + Single-Slide PPT

Extend the current transcript-only pipeline so `build_training_package.py` produces transcript + optional Word summary + exactly one PowerPoint slide. Transcript remains the only source of content. GitHub Models is the LLM backend. If no token is available or the LLM call fails, only the transcript is generated and Word/PPT are skipped. For Word graphics, the LLM provides structured visual descriptions and Python renders local diagrams/images that are embedded into the `.docx`.

**Steps**
1. Phase 1: Add orchestration in `build_training_package.py`.
   Add CLI flags for `--with-docs`, `--no-llm`, `--llm-model`, and a single-slide PPT mode contract. Extend `_package_single_media(...)` so it runs transcript generation first, then conditionally Word/PPT generation, and records `transcript`, `word_summary`, `slides`, and optional `visuals` in the manifest. This step blocks all later steps because it defines the integration points.
2. Phase 1: Create GitHub Models client in `transcription/github_models.py`.
   Implement token lookup from `GITHUB_MODELS_TOKEN`, `GITHUB_TOKEN`, `GH_TOKEN`, `.env` loading via `find_dotenv(usecwd=True)` with script-dir fallback, model selection via `GITHUB_MODELS_MODEL`, optional org endpoint via `GITHUB_MODELS_ORG`, and a `chat_completion(...)` helper. This is a dependency for the LLM content generation steps.
3. Phase 2: Create summary/content generation in `transcription/summary_builder.py`.
   Implement direct transcript-to-content LLM functions only, without auxiliary data sources. Use the user-provided Word system prompt exactly as the fixed system prompt for Word generation, and use the user-provided Word user prompt exactly as the fixed user prompt template for the transcript payload with `{{TRANSCRIPT_TEXT}}` replaced by the full transcript. Word prompt output should be Markdown structured for `.docx` rendering and include a dedicated graphics/diagrams section with per-graphic title, type, purpose, description, elements, and suggested placement. Create one separate system prompt and one user prompt for PPT generation. PPT prompt output should be Markdown for exactly one slide with a schematic/process-oriented representation. If the LLM call fails, return `None` so the orchestrator can skip Word/PPT.
4. Phase 2: Create visual generation in `transcription/visuals.py`.
   Parse the Word Markdown graphics section or a narrow intermediate extraction helper and render local graphics from the LLM-provided descriptions. Reuse the repository memory guidance from `/memories/repo/windows-timestamps.md` if file timestamp preservation is reintroduced. Keep the first implementation narrow: support 1-3 deterministic visual types such as process flow, comparison/table-like diagram, and concept map / labeled boxes. This can run in parallel with the early Word export scaffolding once the prompt contract is fixed.
5. Phase 3: Create Word export in `transcription/word_export.py`.
   Render the LLM Markdown into `.docx` headings, paragraphs, and bullets. Append generated local graphics at the correct sections based on suggested placement metadata. Include transcript appendix only if the existing product expectation still requires it; otherwise keep the document focused on the summary. Use `python-docx` and keep output naming consistent with the prior convention `*_summary_<lang>_<timestamp>.docx`.
6. Phase 3: Create PowerPoint export in `transcription/ppt_export.py`.
   Generate exactly one `.pptx` slide. Parse the LLM Markdown into title + schematic content. The renderer should choose a visual layout consistent with the transcript-derived structure, but the LLM prompt should already bias toward a schematic/process representation. Use `python-pptx` and output `*_training_slides_<lang>_<timestamp>.pptx`. This depends on the PPT prompt contract from step 3.
7. Phase 4: Create dependencies and packaging.
   Update `requirements.txt` to add `python-docx`, `python-pptx`, `python-dotenv`, and `matplotlib`. Update `training_package.spec` hidden imports for `docx`, `pptx`, `matplotlib`, and any image dependencies actually used by the recreated visual pipeline. Keep `openai-whisper` unchanged.
8. Phase 4: Update documentation in `transcription/README.md`.
   Dpcument the workflow as transcript by default plus optional `--with-docs`. Describe the exact LLM-only contract: transcript is the sole source, GitHub Models backend, Word/PPT skipped when LLM is unavailable, exactly one PPT slide, and locally rendered Word graphics based on LLM descriptions. Document where the system and user prompts are defined.
9. Phase 5: Verification.
   Validate imports/errors for `build_training_package.py`, `summary_builder.py`, `word_export.py`, `ppt_export.py`, `visuals.py`, and `github_models.py`. Run one narrow end-to-end check with `--with-docs` against a small media file or an existing transcript-backed path if available. Confirm manifest entries, file naming, skip behavior without token, and that PPT output contains exactly one slide.

**Relevant files**
- `c:/Users/karen.bugge/GIT/Tools/transcription/build_training_package.py` — restore orchestration, CLI flags, manifest expansion, and transcript-first/doc-optional control flow
- `c:/Users/karen.bugge/GIT/Tools/transcription/github_models.py` — GitHub Models API client with `.env` loading and token/model resolution
- `c:/Users/karen.bugge/GIT/Tools/transcription/summary_builder.py` — direct LLM prompts and transcript-to-Markdown generation for Word and single-slide PPT
- `c:/Users/karen.bugge/GIT/Tools/transcription/visuals.py` — local rendering of graphics/flowcharts from LLM-provided descriptions for Word embedding
- `c:/Users/karen.bugge/GIT/Tools/transcription/word_export.py` — `.docx` rendering from Markdown + image embedding
- `c:/Users/karen.bugge/GIT/Tools/transcription/ppt_export.py` — exactly one `.pptx` slide from LLM-generated Markdown
- `c:/Users/karen.bugge/GIT/Tools/transcription/README.md` — workflow, prompts, flags, and failure behavior documentation
- `c:/Users/karen.bugge/GIT/Tools/requirements.txt` — restore doc/ppt/dotenv/matplotlib dependencies
- `c:/Users/karen.bugge/GIT/Tools/training_package.spec` — restore packaging imports for rebuilt Word/PPT pipeline
- `c:/Users/karen.bugge/GIT/Tools/transcription/transcribe_video.py` — existing anchor for `_collect_media_files`, `_load_model`, and `transcribe()` reuse

**Verification**
1. Run error checks on the touched Python modules after each phase, starting with `build_training_package.py` immediately after reintroducing orchestration.
2. Verify dependency imports with the workspace interpreter: `c:/Users/karen.bugge/GIT/Tools/.venv/Scripts/python.exe -c "from docx import Document; from pptx import Presentation; import matplotlib; from dotenv import find_dotenv; print('OK')"`.
3. Run a narrow pipeline invocation: `c:/Users/karen.bugge/GIT/Tools/.venv/Scripts/python.exe transcription/build_training_package.py <media_or_folder> --with-docs --model base --output-dir <out>`.
4. Re-run without LLM token and confirm transcript is generated while Word/PPT steps are skipped and reflected in the manifest.
5. Manually open the generated `.pptx` and confirm there is exactly one slide.
6. Inspect the generated `.docx` to confirm Markdown headings/bullets render correctly and locally generated graphics are embedded in the intended section.

**Decisions**
- LLM backend: GitHub Models only.
- Document content source: transcript only, no other data sources.
- Word graphics: LLM describes them; Python renders them locally and embeds them.
- PPT scope: exactly one slide with a schematic representation of transcript content.
- Failure behavior: if no GitHub Models token exists or the LLM call fails, generate only the transcript and skip Word/PPT.
- Included scope: recreation of deleted modules and packaging support needed for the feature.
- Excluded scope: multi-slide decks, external knowledge retrieval, non-transcript enrichment, image generation by the LLM itself.

**Further Considerations**
1. Prompt contract recommendation: keep Word and PPT prompts separate instead of deriving slide content from the Word summary. That keeps the one-slide PPT focused and avoids bloated slide text.
2. Visual generation recommendation: start with deterministic local rendering for process flow, comparison matrix, and concept map only. Expand only after validating the prompt quality on real transcripts.
3. Output naming recommendation: preserve the previous file naming conventions so overwrite/skip logic stays predictable and existing manifests remain easy to compare.
