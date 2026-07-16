Generate a full training package from media input.

Required input:
- Media path (single file or folder)

Optional input:
- Whisper model: tiny | base | small | medium | large (default: base)
- Language code override (otherwise auto detect)
- Output directory
- Max slide count (default: 12)
- Disable LLM refinement

Expected outputs:
- Transcript text file
- Detailed Word summary file
- Training PowerPoint file with visuals
- JSON manifest listing all produced artifacts
