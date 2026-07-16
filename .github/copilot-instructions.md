# Copilot Workspace Instructions

## Python Environment
- Use the workspace virtual environment interpreter:
  - c:/Users/karen.bugge/GIT/Tools/.venv/Scripts/python.exe

## Transcription + Training Package Workflow
- Primary orchestrator: transcription/build_training_package.py
- Reuse transcription helpers from transcription/transcribe_video.py where possible.
- Default output language behavior: auto-detect from transcript content unless user provides --language.

## Output Conventions
- Store generated artifacts under the selected output directory.
- For each media file, produce:
  - transcript .txt
  - detailed summary .docx
  - training slides .pptx
- Also write one manifest .json for the full run.

## Reliability Requirements
- LLM refinement is optional. If OpenAI API settings are missing or fail, continue with local summary generation.
- Keep processing resilient per file; one failed file should not prevent other files from completing.
