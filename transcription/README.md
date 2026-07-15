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
