================================================================================
  TRAINING PACKAGE - Transkriptions- und Dokumentationswerkzeug
  Version: 1.0  |  Sprachen: Deutsch / Englisch
================================================================================


INSTALLATION
------------
1. Den gesamten Ordner "training_package" auf den Zielrechner kopieren.
   (z.B. nach C:\Tools\training_package\ oder C:\Users\<Name>\Downloads\transcriber\)

2. FFmpeg installieren (PFLICHT - ohne FFmpeg kann die EXE keine Medien verarbeiten):

   Option A – Winget (Windows 10/11, empfohlen):
     > winget install Gyan.FFmpeg

   Option B – Manuell:
     - Download: https://ffmpeg.org/download.html  (Windows builds von gyan.dev)
     - ZIP entpacken, z.B. nach C:\ffmpeg\
     - Den Pfad C:\ffmpeg\bin\ zur System-Umgebungsvariable PATH hinzufügen
     - Neustart des Terminals / der Eingabeaufforderung

   Prüfen ob FFmpeg verfügbar ist:
     > ffmpeg -version

3. Beim ersten Aufruf wird das Whisper-Sprachmodell automatisch heruntergeladen
   (~74 MB fuer "base", ~1,5 GB fuer "large"). Internetzugang wird einmalig benoetigt.

4. Optionale KI-Zusammenfassung (Word/PowerPoint):
   Eine Datei ".env" im gleichen Ordner wie die EXE anlegen mit folgendem Inhalt:
     GITHUB_MODELS_TOKEN=<dein_github_token>
   Ohne Token wird eine lokale Zusammenfassung erstellt (kein Internet noetig).


SCHNELLSTART
------------
Nur Transkript erstellen (Standard):
  > training_package.exe "C:\Videos\meeting.mp4"

Transkript + Word-Zusammenfassung + PowerPoint:
  > training_package.exe "C:\Videos\meeting.mp4" --with-docs

Ganze Ordner verarbeiten:
  > training_package.exe "C:\Videos\Meetings\"

Sprache explizit angeben (schneller, genauer):
  > training_package.exe "C:\Videos\meeting.mp4" --language de
  > training_package.exe "C:\Videos\meeting.mp4" --language en

Besseres Modell fuer lange/komplexe Aufnahmen:
  > training_package.exe "C:\Videos\meeting.mp4" --model medium --language de


AUSGABEDATEIEN
--------------
Die Ergebnisse werden im Unterordner "training_package_output\" neben der
Eingabedatei abgelegt. Dateinamen enthalten Sprachkuerzel und Zeitstempel:

  <dateiname>_transcript_<sprache>_<zeitstempel>.txt      Transkript (immer)
  <dateiname>_summary_<sprache>_<zeitstempel>.docx        Word-Zusammenfassung (--with-docs)
  <dateiname>_training_slides_<sprache>_<zeitstempel>.pptx  PowerPoint (--with-docs)
  training_package_manifest_<zeitstempel>.json            Protokolldatei

Mit --output-dir kann ein beliebiger Ausgabeordner angegeben werden:
  > training_package.exe "C:\Videos\meeting.mp4" --output-dir "C:\Ergebnisse"


ALLE OPTIONEN
-------------

  input_path               Pfad zur Mediendatei oder zu einem Ordner mit Mediendateien
                           Unterstuetzte Formate: .mp4 .mkv .avi .mov .webm .m4v
                                                  .mp3 .wav .m4a .flac .aac .ogg

  --model {tiny,base,small,medium,large}
                           Whisper-Modellgroesse (Standard: base)
                             tiny   ~39M  Parameter  - sehr schnell, weniger genau
                             base   ~74M  Parameter  - Standard, gute Balance
                             small  ~244M Parameter  - genauer, langsamer
                             medium ~769M Parameter  - sehr genau, deutlich langsamer
                             large  ~1.5G Parameter  - hoechste Genauigkeit

  --language LANGUAGE      Sprache der Aufnahme erzwingen, z.B. "de" oder "en"
                           Ohne Angabe: automatische Spracherkennung (etwas langsamer)

  --output-dir OUTPUT_DIR  Ausgabeordner fuer alle erzeugten Dateien

  --transcript-only        Nur Transkript erstellen, kein Word/PowerPoint (Standard)

  --with-docs              Zusaetzlich Word-Zusammenfassung und PowerPoint erstellen

  --overwrite              Vorhandene Dateien gleicher Sprache ueberschreiben
                           Ohne diese Option: bestehende Dateien werden uebersprungen

  --no-llm                 KI-Zusammenfassung deaktivieren; lokale Zusammenfassung
                           wird immer erstellt (kein Internet / Token noetig)

  --llm-model LLM_MODEL    GitHub Models Modell-ID (Standard: openai/gpt-5)
                           Beispiel: --llm-model openai/gpt-4o

  --max-slides N           Maximale Anzahl Folien im PowerPoint (Standard: 2)

  --offline                Kein Modell-Download; bricht ab wenn Modell nicht gecacht

  -h, --help               Diese Hilfe anzeigen


BEISPIELE
---------
  # Deutsches Meeting transkribieren, Standard-Modell
  training_package.exe "C:\Aufnahmen\meeting_2026.mp4" --language de

  # Englisches Webinar, hoehere Genauigkeit, mit Word und Folien
  training_package.exe "C:\Webinare\onboarding.mp4" --language en --model medium --with-docs

  # Ganzen Ordner verarbeiten, Ausgabe in eigenen Ordner
  training_package.exe "C:\Videos\Schulungen\" --language de --output-dir "C:\Transkripte"

  # Bereits vorhandene Dateien erneut verarbeiten (ueberschreiben)
  training_package.exe "C:\Videos\meeting.mp4" --language de --overwrite

  # Ohne Internetzugang (Modell muss bereits heruntergeladen sein)
  training_package.exe "C:\Videos\meeting.mp4" --language de --offline --no-llm


FEHLERBEHEBUNG
--------------
  "ffmpeg not found"
    -> FFmpeg nicht installiert oder nicht im PATH. Siehe Installation oben.

  "model not cached" (mit --offline)
    -> Einmal ohne --offline ausfuehren um das Modell herunterzuladen.

  "No such file or directory: mel_filters.npz"
    -> Alte Version der EXE. Bitte neueste Version des training_package-Ordners
       vom Absender erhalten.

  PowerPoint oder Word wird nicht erstellt
    -> Ohne --with-docs werden diese Dateien nicht erzeugt (Standard: nur Transkript).
    -> Pruefen ob GITHUB_MODELS_TOKEN in der .env-Datei gesetzt ist (fuer LLM).

  Falsche Sprache im Dateinamen (z.B. "en" statt "de")
    -> --language de explizit angeben. Ohne Angabe erkennt Whisper die Sprache
       automatisch, was bei kurzen oder gemischten Aufnahmen abweichen kann.


================================================================================
  Bei Fragen: karen.bugge@accenture.com
================================================================================
