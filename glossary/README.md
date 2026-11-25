# Glossar-Agent

Der Agent `glossary` erstellt bzw. ergänzt `Glossar.docx` aus einer Datei
oder rekursiv aus einem Verzeichnis. Er ermittelt Fachbegriffe und formuliert
Definitionen anhand der Dokumente; das Python-Skript allein extrahiert Texte
und schreibt die vom Agenten ermittelten Einträge, erzeugt aber keine
Definitionen. Bestehende Definitionen werden nur nach expliziter Bestätigung
geändert.

## Voraussetzungen und Grenzen

- Workspace-Umgebung aus `requirements.txt`; Interpreter
  `.\.venv\Scripts\python.exe`.
- Eingaben: `.docx`, `.pdf`, `.txt`, `.md` und `.pptx`; Textdateien in UTF-8.
  Nicht unterstützte Dateien und Lesefehler werden gemeldet.
- PDF-Seiten und PowerPoint-Folien erhalten Quellenangaben mit Nummer.
  Word-Text und Word-Tabellen werden aus dem Dokumentkörper extrahiert.
  Kopf-/Fußzeilen, Notizen, eingebettete Dateien, Bildtext und OCR werden nicht
  verarbeitet. PDFs ohne extrahierbaren Text werden als Fehler gemeldet;
  einzelne leere Seiten und Folien werden als Warnung aufgeführt.
- Symbolische Verzeichnisse werden gemeldet, aber nicht verfolgt, um Schleifen
  zu vermeiden. Die Zieldatei und Extraktionsdatei werden ausgeschlossen.
- Bereits vorhandene Glossare müssen genau eine Tabelle mit der Kopfzeile
  `Begriff`, `Definition`, `Kontext/Hinweis`, `Quellen` enthalten. Andere
  Inhalte im Word-Dokument bleiben erhalten.
- Bei einer abgelehnten Definitionsänderung bleibt der bestehende Eintrag
  einschließlich Kontext und Quellen unverändert.
- Bestehende `Glossar.doc*`- oder `Glossary.doc*`-Dateien in Eingabeverzeichnissen
  werden ignoriert, um Zirkularitäten zu vermeiden.

## Verwendung

Den Agenten in Copilot auswählen und beispielsweise mitteilen:
„Analysiere `C:\Dokumente` und erstelle das Glossar in `C:\Ergebnisse`.“
Alternativ einen einzelnen Dateipfad angeben oder ein Dokument hochladen. Der
Agent fragt nach fehlendem Zielverzeichnis und bei Definitionsänderungen nach.

## Standardformatierung

Der Agent wendet nach jeder Erstellung und Aktualisierung ein einheitliches
Layout an: A4 quer, Calibri, dunkelblaue wiederholte Tabellenkopfzeile,
abwechselnd dezent hinterlegte Datenzeilen, fett hervorgehobene Begriffe,
kleinere graue Quellenangaben und rechtsbündige Seitenzahlen. Die festen
Spaltenbreiten betragen 3,7 / 7,6 / 6,4 / 9,0 cm. Inhalte bleiben dabei
unverändert.

Die genauen Layoutwerte und die abschließende Prüfung sind in der
[Agent-Definition](../.github/agents/glossary.agent.md) verbindlich festgelegt.
Der Agent führt die Formatierung zusätzlich mit `python-docx` aus; der
CLI-Befehl `update` allein formatiert das Glossar nicht entsprechend.

## Verarbeitungsübersicht

Nach jeder Erstellung oder Aktualisierung wird eine Verarbeitungsübersicht
am Ende des Glossar-Dokuments eingefügt (als Markdown nach der Glossar-Tabelle).
Sie enthält:
- Generierungsdatum und -zeit (lokal, Format: TT.MM.YYYY HH:MM:SS)
- Analysierte Verzeichnisse und analysierte Dateien
- Übersprungene oder fehlerhafte Dateien (Namen und Gründe)
- Begriffsstatistik (Anzahl verarbeitete, übersprungene, fehlerhafte Dokumente)
- Falls vorhanden: Warnungen (z. B. leere PDF-Seiten, nicht extrahierbare Teile)

Diese Übersicht wird bei jeder Aktualisierung vollständig ersetzt, nicht
verdoppelt. Der Agent generiert sie mithilfe der Hilfsfunktion
`_generate_processing_summary()` und integriert sie mithilfe von
`_update_processing_summary()` in die Glossar-Datei.

## Technischer Ablauf

```powershell
.\.venv\Scripts\python.exe .\glossary\glossary.py extract C:\Dokumente --glossary C:\Ergebnisse\Glossar.docx --output C:\Temp\extraktion.json
.\.venv\Scripts\python.exe .\glossary\glossary.py show --glossary C:\Ergebnisse\Glossar.docx
.\.venv\Scripts\python.exe .\glossary\glossary.py update --glossary C:\Ergebnisse\Glossar.docx --candidates C:\Temp\begriffe.json --preview
.\.venv\Scripts\python.exe .\glossary\glossary.py update --glossary C:\Ergebnisse\Glossar.docx --candidates C:\Temp\begriffe.json --decisions C:\Temp\entscheidungen.json
```

Die Kandidatendatei ist eine JSON-Liste, zum Beispiel:

```json
[
  {
    "Begriff": "Beispiel",
    "Definition": "Eine quellengestützte Erklärung.",
    "Kontext/Hinweis": "Verwendung im Dokument.",
    "Quellen": "C:\\Dokumente\\Beispiel.pdf, Seite 2"
  }
]
```

Wenn die Vorschau Konflikte meldet, muss für jeden Konflikt eine explizite
Entscheidung vorliegen. Die Werte für `Begriff`, `bisher` und `neu` müssen
unverändert aus der Vorschau stammen:

```json
[
  {
    "Begriff": "Beispiel",
    "bisher": "Bisherige Definition.",
    "neu": "Neue Definition.",
    "übernehmen": false
  }
]
```

Ohne Konflikte kann `--decisions` entfallen. Unvollständige oder veraltete
Entscheidungen verhindern das Schreiben. Die Extraktion liefert auch bei
einzelnen Fehlern eine JSON-Datei und einen Exitcode ungleich null; ein
unvollständiges Ergebnis muss vor der Verwendung ausdrücklich geprüft werden.
Die Extraktionsdatei darf noch nicht existieren und überschreibt weder Eingabe
noch Glossar.
