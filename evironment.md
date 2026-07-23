# Environment Setup

## Python Virtual Environment

Use the workspace virtual environment interpreter:

- Windows path: `c:/Users/karen.bugge/GIT/Tools/.venv/Scripts/python.exe`

## Whisper Installation

Install Whisper in the workspace environment:

```powershell
c:/Users/karen.bugge/GIT/Tools/.venv/Scripts/python.exe -m pip install --no-cache-dir --upgrade openai_whisper 
```

Verify installation:

```powershell
c:/Users/karen.bugge/GIT/Tools/.venv/Scripts/python.exe -c "import whisper; print(whisper.__version__)"
```
