# README_Transcribe

## Zweck
Das Skript transcribe_video.py transkribiert Sprache aus Video- und Audio-Dateien lokal mit OpenAI Whisper.
Es kann eine einzelne Datei oder alle unterstuetzten Medien-Dateien in einem Verzeichnis verarbeiten.
Unterstuetzte Formate: mp4, mkv, avi, mov, webm, m4v, mp3, wav, m4a, flac, aac, ogg, opus, wma.

## Voraussetzungen
1. Python in einer virtuellen Umgebung (empfohlen).
2. Paket openai-whisper installiert.
3. ffmpeg installiert und im PATH verfuegbar.

Windows Installation ffmpeg (Beispiel):

```powershell
winget install --id Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements
```

## Lokaler Betrieb und Offline-Verhalten
- Die eigentliche Transkription laeuft lokal auf dem Rechner.
- Video und Transkript werden nicht an eine Cloud API gesendet.
- Beim ersten Laden eines noch nicht vorhandenen Whisper-Modells kann ein Download noetig sein.
- Mit Option --offline wird jeder Modell-Download verhindert.
- Wenn das Modell bei --offline nicht lokal vorhanden ist, bricht das Skript mit einer klaren Fehlermeldung ab.

## Aufruf
Grundform:

```powershell
python transcribe_video.py EINGABE_PFAD
```

EINGABE_PFAD kann sein:
- eine einzelne Video- oder Audio-Datei
- ein Verzeichnis mit unterstuetzten Medien-Dateien

Beispiele:

```powershell
python transcribe_video.py C:/videos/meeting.mkv
python transcribe_video.py C:/audio/interview.wav
python transcribe_video.py C:/videos
python transcribe_video.py C:/videos/meeting.mkv --model medium --language de
python transcribe_video.py C:/videos/meeting.mkv --output-dir C:/transcripts --print
python transcribe_video.py C:/videos/meeting.mkv --model base --offline
python transcribe_video.py C:/videos/meeting.mkv --segments
python transcribe_video.py C:/videos/meeting.mkv --no-segments
```

## Alle Aufrufoptionen
### Positionsargument
- input_path
  - Pfad zu einer Video- oder Audio-Datei oder zu einem Verzeichnis mit Medien-Dateien.
  - Erlaubte Dateiendungen: .mp4, .mkv, .avi, .mov, .webm, .m4v, .mp3, .wav, .m4a, .flac, .aac, .ogg, .opus, .wma

### Optionale Argumente
- --model {tiny,base,small,medium,large}
  - Whisper-Modellgroesse.
  - Standard: base
  - Hinweis: groessere Modelle sind genauer, aber langsamer und brauchen mehr RAM.

- --language LANGUAGE
  - Sprachcode, z. B. de oder en.
  - Wenn nicht gesetzt, versucht Whisper die Sprache automatisch zu erkennen.

- --output-dir OUTPUT_DIR
  - Zielordner fuer die Ausgabe-Textdatei.
  - Standard: derselbe Ordner wie die Video-Datei.

- --print
  - Gibt den kompletten transkribierten Text zusaetzlich in der Konsole aus.

- --offline
  - Erzwingt Offline-Betrieb fuer Modell-Downloads.
  - Wenn das ausgewaehlte Modell nicht lokal im Cache liegt, wird mit Fehler beendet.

- --segments
  - Fuegt in der Ausgabe-Datei einen Segment-Abschnitt mit Zeitstempeln hinzu.

- --no-segments
  - Schreibt nur den Volltext ohne Segment-Abschnitt.
  - Hinweis: Aktueller Standard ist ohne Segment-Abschnitt.

## Ausgabe
Das Skript schreibt pro verarbeiteter Medien-Datei eine Datei im Format:

- DATEINAME_transcript_YYYYMMDD_HHMMSS.txt

Inhalt der Datei:
1. Volltext der Transkription.
2. Optionaler Abschnitt Segments mit Zeitstempeln pro Segment (nur mit --segments).

Beispiel Segment-Zeile:

```text
[00012.34s - 00018.90s]  Beispieltext
```

## Interner Ablauf (Code-Dokumentation)
1. main() liest alle CLI-Argumente ein.
2. _collect_media_files(...) bestimmt, ob input_path eine Datei oder ein Verzeichnis ist.
  - Einzeldatei: genau diese Datei wird verarbeitet.
  - Verzeichnis: alle unterstuetzten Video- und Audio-Dateien werden verarbeitet.
3. _load_model(...)
   - prueft ffmpeg-Verfuegbarkeit (ensure_ffmpeg_available)
   - prueft optional Offline-Modellcache (is_model_cached)
   - laedt Whisper-Modell
4. transcribe(...) startet die Transkription je Medien-Datei.
5. save_transcript(...)
   - erzeugt Dateinamen mit Zeitstempel
   - schreibt Volltext und segmentierte Ausgabe in eine Textdatei
6. Bei bekannten Fehlern wird mit einer lesbaren Fehlermeldung beendet.

## Fehlerbehebung
- Error: ffmpeg was not found on PATH
  - ffmpeg installieren und Terminal neu starten.

- Error: Video file not found
  - Pfad zur Video-Datei pruefen.

- Error: Unsupported video format
  - Nur unterstuetzte Dateiendungen verwenden.

- Error in --offline mode (Modell nicht im Cache)
  - Modell einmal ohne --offline laden, danach erneut mit --offline starten.

## End-to-End Workflow: Transcript (Default) + optionale Dokumente

Neues Orchestrierungs-Skript:

- transcription/build_training_package.py

Dieses Skript erstellt pro Eingabedatei standardmaessig:

1. Transcript (.txt)
2. Manifest (.json) mit Artefaktpfaden und Schrittstatus

Optional (nur mit --with-docs):

1. Detaillierte Zusammenfassung als Word-Datei (.docx)
2. Schulungsfolien als PowerPoint (.pptx) mit Visualisierungen

Hinweis zu existierenden Dateien:

- Mit `--overwrite` werden vorhandene Ergebnisse (Transcript/Word/PPT) ueberschrieben.
- Ohne `--overwrite` werden bereits vorhandene Schritte uebersprungen.

### Abhaengigkeiten installieren

Im Projektroot:

```powershell
c:/Users/karen.bugge/GIT/Tools/.venv/Scripts/python.exe -m pip install -r requirements.txt
```

### Beispielaufrufe

Nur Transcript (Default):

```powershell
c:/Users/karen.bugge/GIT/Tools/.venv/Scripts/python.exe transcription/build_training_package.py C:/videos/meeting.mkv
```

Transcript + Word + PPT:

```powershell
c:/Users/karen.bugge/GIT/Tools/.venv/Scripts/python.exe transcription/build_training_package.py C:/videos/meeting.mkv --with-docs --model base --max-slides 12
```

Einzeldatei:

```powershell
c:/Users/karen.bugge/GIT/Tools/.venv/Scripts/python.exe transcription/build_training_package.py C:/videos/meeting.mkv --with-docs --model base --max-slides 12
```

Ordnerverarbeitung mit explizitem Ausgabeordner:

```powershell
c:/Users/karen.bugge/GIT/Tools/.venv/Scripts/python.exe transcription/build_training_package.py C:/videos --output-dir C:/training_output --model small
```

Ordnerverarbeitung mit Ueberschreiben vorhandener Ergebnisse:

```powershell
c:/Users/karen.bugge/GIT/Tools/.venv/Scripts/python.exe transcription/build_training_package.py C:/videos --with-docs --output-dir C:/training_output --overwrite
```

Nur lokale Zusammenfassung ohne LLM:

```powershell
c:/Users/karen.bugge/GIT/Tools/.venv/Scripts/python.exe transcription/build_training_package.py C:/videos/meeting.mkv --with-docs --no-llm
```

Existierende Ergebnisse ueberschreiben:

```powershell
c:/Users/karen.bugge/GIT/Tools/.venv/Scripts/python.exe transcription/build_training_package.py C:/videos/meeting.mkv --with-docs --overwrite
```

### Optionen des Orchestrierungs-Skripts

| Option | Typ | Default | Beschreibung |
|---|---|---|---|
| input_path | Position | - | Pfad zu einer Datei oder einem Ordner mit Medien-Dateien |
| --model | Auswahl | base | Whisper-Modell: tiny, base, small, medium, large |
| --language | String | auto | Sprach-Override, z. B. de oder en |
| --output-dir | Pfad | input_parent/training_package_output | Zielordner fuer Artefakte |
| --offline | Flag | false | Verhindert Modell-Download |
| --max-slides | Zahl | 12 | Maximale Folienanzahl (nur mit --with-docs) |
| --theme | String | standard | Reserviert fuer zukuenftige Themes |
| --no-llm | Flag | false | Deaktiviert LLM-Refinement (nur relevant mit --with-docs) |
| --with-docs | Flag | false | Erzeugt zusaetzlich Word und PowerPoint |
| --overwrite | Flag | false | Ueberschreibt vorhandene Ergebnisse statt Schritte zu ueberspringen |
| --llm-model | String | env/default | GitHub Models Modell-ID |

- --with-docs
  - Aktiviert zusaetzlich Word- und PowerPoint-Generierung.
  - Ohne diese Option werden nur Transcript + Manifest erzeugt.

- --overwrite
  - Prueft je Schritt (Transcript, Word, PPT), ob bereits eine passende Datei existiert.
  - Der Zeitstempel im Dateinamen wird bei der Existenzpruefung ignoriert.
  - overwrite=false (Standard): Schritt wird uebersprungen und gemeldet.
  - overwrite=true: Schritt wird ausgefuehrt und vorhandene Datei wird ueberschrieben.

- --no-llm
  - Deaktiviert LLM-Refinement fuer Summary/Blueprints.
  - Relevant nur zusammen mit --with-docs.

### Manifest-Status pro Schritt

Im Manifest steht pro Datei unter results[].steps der Schrittstatus:

- generated
- overwritten
- skipped
- disabled (bei Word/PPT im Transcript-Only-Default)

### GitHub Copilot / GitHub Models fuer Word und PPT

- Word/PPT werden nur mit --with-docs erzeugt.
- Standard: lokale Strukturierung plus optionale LLM-Generierung ueber GitHub Models
- Fuer LLM-Nutzung setze einen Token mit `models:read`, z. B. als `GITHUB_MODELS_TOKEN`, `GITHUB_TOKEN` oder `GH_TOKEN`
- Optional kann ein Modell ueber `GITHUB_MODELS_MODEL` oder `--llm-model` gesetzt werden, z. B. `openai/gpt-4.1-mini`
- Optional kann ueber `GITHUB_MODELS_ORG` die Nutzung einer Organisation zugeordnet werden
- Wenn kein GitHub-Token vorhanden ist oder der API-Aufruf fehlschlaegt, wird automatisch lokal weitergearbeitet
- Sprache wird standardmaessig automatisch aus dem Transcript abgeleitet (oder ueber --language gesetzt)
