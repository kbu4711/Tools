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

## End-to-End Workflow: Transcript + optionale Dokumente

Orchestrierungs-Skript:

- transcription/build_training_package.py

Dieses Skript erstellt pro Eingabedatei standardmaessig:

1. Transcript (.txt)
2. Manifest (.json) mit Artefaktpfaden und Schrittstatus

Optional (nur mit `--with-docs`):

1. Zusammenfassung als Word-Datei (.docx)
2. Genau eine PowerPoint-Folie als .pptx

Hinweis zu existierenden Dateien:

- Mit `--overwrite` werden vorhandene Transcript-Dateien ueberschrieben.
- Ohne `--overwrite` werden bereits vorhandene Transcript-Schritte uebersprungen.

### Abhaengigkeiten installieren

Im Projektroot:

```powershell
c:/Users/karen.bugge/GIT/Tools/.venv/Scripts/python.exe -m pip install -r requirements.txt
```

### Beispielaufrufe

Nur Transcript erzeugen:

```powershell
c:/Users/karen.bugge/GIT/Tools/.venv/Scripts/python.exe transcription/build_training_package.py C:/videos/meeting.mkv --model base
```

Transcript + Word + PowerPoint:

```powershell
c:/Users/karen.bugge/GIT/Tools/.venv/Scripts/python.exe transcription/build_training_package.py C:/videos/meeting.mkv --with-docs --model base
```

Ordnerverarbeitung mit explizitem Ausgabeordner:

```powershell
c:/Users/karen.bugge/GIT/Tools/.venv/Scripts/python.exe transcription/build_training_package.py C:/videos --output-dir C:/training_output --model small
```

Existierende Ergebnisse ueberschreiben:

```powershell
c:/Users/karen.bugge/GIT/Tools/.venv/Scripts/python.exe transcription/build_training_package.py C:/videos/meeting.mkv --overwrite
```

### Optionen des Orchestrierungs-Skripts

| Option | Typ | Default | Beschreibung |
|---|---|---|---|
| input_path | Position | - | Pfad zu einer Datei oder einem Ordner mit Medien-Dateien |
| --model | Auswahl | base | Whisper-Modell: tiny, base, small, medium, large |
| --language | String | auto | Sprach-Override, z. B. de oder en |
| --output-dir | Pfad | input_parent/training_package_output | Zielordner fuer Artefakte |
| --offline | Flag | false | Verhindert Modell-Download |
| --with-docs | Flag | false | Erzeugt zusaetzlich Word und PowerPoint aus dem Transcript |
| --no-llm | Flag | false | Deaktiviert LLM-Erzeugung; Word/PPT werden dann uebersprungen |
| --llm-model | String | env/default | GitHub Models Modell-ID |
| --overwrite | Flag | false | Ueberschreibt vorhandene Transcript-/Word-/PPT-Ergebnisse statt Schritte zu ueberspringen |

- --with-docs
  - Aktiviert zusaetzlich die Erzeugung von Word und PowerPoint.
  - Grundlage ist ausschliesslich das Transcript.

- --no-llm
  - Deaktiviert LLM-Erzeugung.
  - In diesem Fall werden Word und PPT nicht erstellt.

- --llm-model
  - Ueberschreibt `GITHUB_MODELS_MODEL` aus `.env`.
  - Beispiel: `openai/gpt-4.1-mini`

- --overwrite
  - Prueft je Schritt (Transcript, Word, PPT), ob bereits eine passende Datei existiert.
  - Der Zeitstempel im Dateinamen wird bei der Existenzpruefung ignoriert.
  - overwrite=false (Standard): Schritt wird uebersprungen und gemeldet.
  - overwrite=true: Schritt wird ausgefuehrt und vorhandene Datei wird ueberschrieben.

### Manifest-Status pro Schritt

Im Manifest steht pro Datei unter results[].steps der Schrittstatus:

- generated
- overwritten
- skipped

### LLM-Verhalten fuer Word und PPT

- Word und PPT werden nur mit `--with-docs` erzeugt.
- Inhaltsquelle ist ausschliesslich das Transcript.
- Als LLM-Backend wird GitHub Models verwendet.
- Wenn kein GitHub-Models-Token vorhanden ist oder ein LLM-Aufruf fehlschlaegt, werden Word und PPT uebersprungen; das Transcript wird trotzdem erzeugt.
- Bei `unavailable_model` wird automatisch ein Fallback-Modell versucht.
- Bei transienten Fehlern (`429`, `5xx`, Netzwerk, Timeout) werden LLM-Aufrufe mit exponentiellem Backoff erneut versucht.
- Die PowerPoint-Ausgabe enthaelt genau eine Folie.
- Grafiken fuer die Word-Datei werden lokal erzeugt, basierend auf den vom LLM beschriebenen Visualisierungen.

Konfigurierbare Umgebungsvariablen:

- `GITHUB_MODELS_MODEL`
  - Primaeres Modell (Default im Code: `openai/gpt-4.1-mini`).
- `GITHUB_MODELS_FALLBACK_MODEL`
  - Fallback-Modell bei `unavailable_model` (Default: `openai/gpt-4.1-mini`).
- `GITHUB_MODELS_MAX_RETRIES`
  - Anzahl Retries bei transienten Fehlern (Default: `2`).
- `GITHUB_MODELS_RETRY_BASE_SECONDS`
  - Basis-Delay in Sekunden fuer exponentielles Backoff (Default: `1.5`).
- `GITHUB_MODELS_ORG`
  - Optionaler Org-spezifischer Endpoint.
- `TRANSCRIPT_MAX_CHARS`
  - Maximale Groesse des an das LLM uebergebenen Transcripts in Zeichen.
  - Default: `10000` (entspricht ca. 2500 Tokens).
  - Auf `0` oder negative Werte setzen um Begrenzung zu deaktivieren.
  - Transkripte werden intelligent am Ende eines Satzes gekuerzt fuer besseren Kontext.

## Transcript-Groessenbegrenzung

Beim Erzeugen von Word und PowerPoint wird das Transcript vor der Uebergabe an das LLM auf eine konfigurierbare Maximalgoes begrenzt:

**Warum?**
- Groessere Transkripte erhoehen die Latenz und Kosten des LLM-Calls.
- Viele LLMs haben praktische Token-Limits, die beruecksichtigt werden muessen.

**Verhalten:**
- Standard: max. 10.000 Zeichen (ca. 2.500 Tokens).
- Truncation erfolgt intelligent am Ende eines Satzes (`.`, `!`, `?`) statt in der Mitte eines Wortes.
- Das LLM erhaelt eine Notiz, wenn das Transcript gekuerzt wurde.
- Alle Schritte (Transcript, Word, PPT) werden trotzdem ausgefuehrt; nur die LLM-Eingabe wird begrenzt.

**Konfiguration:**

Zu `.env` hinzufuegen:

```
TRANSCRIPT_MAX_CHARS=15000
```

Oder in der Konsole vor dem Aufruf:

```powershell
$env:TRANSCRIPT_MAX_CHARS = "15000"
python transcription/build_training_package.py C:/videos/meeting.mkv --with-docs
```

Begrenzung deaktivieren:

```
TRANSCRIPT_MAX_CHARS=0
```



Dieser Abschnitt beschreibt den technischen Ablauf der Transcript- und optionalen Dokument-Erzeugung.

### 1) Einstieg und Orchestrierung

Der Gesamtfluss startet in `transcription/build_training_package.py`:

1. `build_training_package(...)` sammelt Eingabedateien und laedt das Whisper-Modell.
2. Pro Mediendatei ruft es `_package_single_media(...)` auf.
3. In `_package_single_media(...)` werden Schritte sequenziell ausgefuehrt:
  - Transcript erzeugen oder wiederverwenden
  - optional Word-Markdown per LLM erzeugen
  - optionale lokale Grafiken fuer die Word-Datei erzeugen
  - Word-Datei erzeugen
  - genau eine PPT-Folie erzeugen
4. Das Manifest erhaelt pro Schritt Status (`generated`, `overwritten`, `skipped`).

Wichtig:
- Wenn Dateien existieren und `--overwrite` nicht gesetzt ist, werden Schritte uebersprungen.

### Prompt-Definitionen

Die Prompt-Definitionen liegen in `transcription/summary_builder.py`:

- `WORD_SYSTEM_PROMPT`
- `WORD_USER_PROMPT_TEMPLATE`
- `PPT_SYSTEM_PROMPT`
- `PPT_USER_PROMPT_TEMPLATE`

Die Word-Erzeugung verwendet den festgelegten System- und User-Prompt zur Markdown-Ausgabe fuer die spaetere `.docx`-Erzeugung. Die PPT-Erzeugung verwendet einen separaten System- und User-Prompt fuer genau eine schematische Folie.
