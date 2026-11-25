"""Extract document text and update a reviewable Word glossary."""

from __future__ import annotations

import argparse
from collections.abc import Iterable
from datetime import datetime
import json
import os
from pathlib import Path
import sys
import tempfile
from zipfile import BadZipFile

from docx import Document
from docx.document import _Body
from docx.opc.exceptions import PackageNotFoundError as DocxPackageNotFoundError
from docx.table import Table, _Cell
from docx.text.paragraph import Paragraph
from lxml.etree import XMLSyntaxError
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.exc import PackageNotFoundError as PptxPackageNotFoundError
from pptx.shapes.base import BaseShape
from pypdf import PdfReader
from pypdf.errors import PdfReadError


HEADERS = ("Begriff", "Definition", "Kontext/Hinweis", "Quellen")
FORMATS = {".docx", ".pdf", ".txt", ".md", ".pptx"}


def _docx_text(container: _Body | _Cell) -> list[str]:
    lines: list[str] = []
    for item in container.iter_inner_content():
        if isinstance(item, Paragraph):
            if item.text.strip():
                lines.append(item.text.strip())
        elif isinstance(item, Table):
            for row in item.rows:
                for cell in row.cells:
                    lines.extend(_docx_text(cell))
    return lines


def _shape_text(shapes: Iterable[BaseShape]) -> list[str]:
    lines: list[str] = []
    for shape in shapes:
        if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            lines.extend(_shape_text(shape.shapes))
        elif shape.has_table:
            for row in shape.table.rows:
                lines.extend(cell.text.strip() for cell in row.cells if cell.text.strip())
        elif shape.has_text_frame and shape.text.strip():
            lines.append(shape.text.strip())
    return lines


def extract_file(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    suffix = path.suffix.casefold()
    if suffix in {".txt", ".md"}:
        parts = [("Dokument", path.read_text(encoding="utf-8-sig"))]
    elif suffix == ".docx":
        document = Document(str(path))
        parts = [("Dokument", "\n".join(_docx_text(document._body)))]
    elif suffix == ".pptx":
        presentation = Presentation(str(path))
        parts = [
            (f"Folie {index}", "\n".join(_shape_text(slide.shapes)))
            for index, slide in enumerate(presentation.slides, 1)
        ]
    elif suffix == ".pdf":
        reader = PdfReader(str(path))
        parts = [(f"Seite {index}", page.extract_text() or "") for index, page in enumerate(reader.pages, 1)]
    else:
        raise ValueError(f"Nicht unterstütztes Format: {path}")
    units = [{"location": location, "text": text.strip()} for location, text in parts if text.strip()]
    if not units:
        raise ValueError("Kein Text extrahierbar (ggf. OCR erforderlich)")
    return units, [location for location, text in parts if not text.strip()]


def extract(input_path: Path, glossary_path: Path, output_path: Path) -> dict:
    source = input_path.resolve()
    if not source.exists():
        raise ValueError(f"Eingabe nicht gefunden: {source}")
    glossary_name = glossary_path.resolve().name.lower()
    excluded = {glossary_path.resolve(), output_path.resolve()}
    glossary_patterns = {name.lower() for name in [glossary_name, "glossar.doc", "glossar.docx", "glossary.doc", "glossary.docx"]}
    errors: list[dict[str, str]] = []
    skipped: list[str] = []
    warnings: list[str] = []
    documents: list[dict] = []

    def on_error(error: OSError) -> None:
        errors.append({"path": str(error.filename or source), "error": str(error)})

    if source.is_file():
        files = [source]
    elif source.is_dir():
        files = []
        for root, dirs, names in os.walk(source, onerror=on_error, followlinks=False):
            for name in sorted(dirs):
                directory = Path(root) / name
                if directory.is_symlink():
                    skipped.append(f"{directory} (symbolisches Verzeichnis)")
            dirs[:] = sorted(name for name in dirs if not (Path(root) / name).is_symlink())
            files.extend(Path(root) / name for name in sorted(names))
    else:
        raise ValueError(f"Eingabe ist keine Datei und kein Verzeichnis: {source}")

    for path in files:
        if path.resolve() in excluded:
            continue
        if path.name.startswith("~$"):
            skipped.append(f"{path} (Word-Sperrdatei)")
        elif path.suffix.casefold() not in FORMATS:
            skipped.append(f"{path} (nicht unterstütztes Format)")
        elif (path.name.lower() in glossary_patterns or 
              (path.suffix.casefold() in {".doc", ".docx"} and ("glossar" in path.name.lower() or "glossary" in path.name.lower()))):
            skipped.append(f"{path} (bestehende Glossar-Datei)")
        else:
            try:
                units, empty_locations = extract_file(path)
                documents.append({"path": str(path.resolve()), "units": units})
                for location in empty_locations:
                    warnings.append(f"{path}: {location}: kein Text extrahierbar (ggf. OCR erforderlich)")
            except (OSError, ValueError, UnicodeError, BadZipFile, XMLSyntaxError, PdfReadError,
                    DocxPackageNotFoundError, PptxPackageNotFoundError, KeyError) as error:
                errors.append({"path": str(path), "error": str(error)})
    return {"documents": documents, "skipped": skipped, "warnings": warnings, "errors": errors}


def _generate_processing_summary(extract_result: dict, input_path: Path, output_path: Path, glossary_path: Path) -> str:
    """Generiere Verarbeitungsübersicht als Markdown."""
    documents = extract_result.get("documents", [])
    skipped = extract_result.get("skipped", [])
    warnings = extract_result.get("warnings", [])
    errors = extract_result.get("errors", [])

    summary_lines = [
        "## Verarbeitungsübersicht",
        "",
        f"**Datum:** {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}",
        "",
        "### Verarbeitete Verzeichnisse und Dokumente",
        ""
    ]

    input_resolved = input_path.resolve()
    if input_path.is_dir():
        summary_lines.append(f"- Eingabeverzeichnis: {input_resolved}")
    else:
        summary_lines.append(f"- Eingabedatei: {input_resolved}")
    summary_lines.append(f"- Zielverzeichnis: {output_path.resolve()}")
    summary_lines.append("")

    summary_lines.append("### Verarbeitete Dokumente")
    if documents:
        summary_lines.extend(f"- {Path(doc['path']).name}" for doc in documents)
    else:
        summary_lines.append("- (keine)")
    summary_lines.append("")

    summary_lines.append("### Übersprungene/Fehlerhafte Dokumente")
    if skipped or errors:
        summary_lines.extend(skipped)
        summary_lines.extend(f"- {err['path']}: {err['error']}" for err in errors)
    else:
        summary_lines.append("- (keine)")
    summary_lines.append("")

    summary_lines.append("### Statistik")
    summary_lines.append(f"- Verarbeitete Dokumente: {len(documents)}")
    summary_lines.append(f"- Übersprungene Dokumente: {len(skipped)}")
    summary_lines.append(f"- Fehlerhafte Dokumente: {len(errors)}")
    if warnings:
        summary_lines.append(f"- Warnungen: {len(warnings)}")
        for warning in warnings:
            summary_lines.append(f"  - {warning}")
    summary_lines.append("")

    return "\n".join(summary_lines)


def _sort_glossary_table(table) -> None:
    """Sortiere Glossar-Tabellenzeilfen alphabetisch nach Begriff (Spalte 0)."""
    # Extrahiere alle Datenzeilen (nicht den Header)
    rows = list(table.rows[1:])
    
    # Speichere die Zellinhalte aller Zeilen
    row_data = []
    for row in rows:
        row_data.append([cell.text for cell in row.cells])
    
    # Sortiere die Daten nach Begriff (Index 0) mit Groß-/Kleinschreibung-Ignoranz
    row_data.sort(key=lambda row: row[0].strip().lower())
    
    # Entferne alle Datenzeilen
    for row in rows:
        row._element.getparent().remove(row._element)
    
    # Füge die sortierten Zeilen wieder hinzu
    for cell_data in row_data:
        new_row = table.add_row()
        for new_cell, text in zip(new_row.cells, cell_data):
            new_cell.text = text


def _key(term: str) -> str:
    return " ".join(term.split()).casefold()


def _load_candidates(path: Path) -> list[dict[str, str]]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, list):
        raise ValueError("Die Kandidatendatei muss eine JSON-Liste sein.")
    candidates = []
    seen: set[str] = set()
    for item in data:
        if not isinstance(item, dict) or any(not isinstance(item.get(field), str) or not item[field].strip() for field in HEADERS):
            raise ValueError(f"Jeder Kandidat benötigt nichtleere Textfelder: {', '.join(HEADERS)}")
        candidate = {field: item[field].strip() for field in HEADERS}
        key = _key(candidate["Begriff"])
        if key in seen:
            raise ValueError(f"Doppelter Kandidat: {candidate['Begriff']}")
        seen.add(key)
        candidates.append(candidate)
    if not candidates:
        raise ValueError("Keine Glossarbegriffe gefunden; das Glossar wird nicht geändert.")
    return candidates


def _load_glossary(path: Path):
    if not path.exists():
        document = Document()
        document.add_heading("Glossar", 0)
        table = document.add_table(rows=1, cols=4)
        table.style = "Table Grid"
        for cell, header in zip(table.rows[0].cells, HEADERS):
            cell.text = header
        return document, table, {}
    document = Document(str(path))
    tables = [table for table in document.tables if table.rows and tuple(cell.text.strip() for cell in table.rows[0].cells) == HEADERS]
    if len(tables) != 1:
        raise ValueError("Das bestehende Glossar muss genau eine Tabelle mit den vier Glossar-Spalten enthalten.")
    table = tables[0]
    rows = {}
    for row in table.rows[1:]:
        if len(row.cells) != 4 or not row.cells[0].text.strip():
            raise ValueError("Ungültige Glossarzeile: Vier Spalten und ein Begriff sind erforderlich.")
        key = _key(row.cells[0].text)
        if key in rows:
            raise ValueError(f"Doppelter Begriff im bestehenden Glossar: {row.cells[0].text}")
        rows[key] = row
    return document, table, rows


def _append_unique(original: str, addition: str) -> str:
    values = [line.strip() for line in original.splitlines() if line.strip()]
    existing = {line.casefold() for line in values}
    for line in addition.splitlines():
        if line.strip() and line.strip().casefold() not in existing:
            values.append(line.strip())
            existing.add(line.strip().casefold())
    return "\n".join(values)


def _update_processing_summary(document, summary_text: str) -> None:
    """Ersetze oder füge Verarbeitungsübersicht am Ende des Dokuments ein."""
    # Finde die Glossar-Tabelle
    glossar_table_index = None
    body = document.element.body
    
    for i, element in enumerate(list(body)):
        if element.tag.endswith("tbl"):
            glossar_table_index = i
            break
    
    if glossar_table_index is None:
        raise ValueError("Glossar-Tabelle nicht gefunden.")
    
    # Entferne bestehende Verarbeitungsübersicht (alle Absätze nach der Tabelle, bis auf sectPr)
    # sectPr ist das letzte Element und muss erhalten bleiben
    elements_to_check = list(body)[glossar_table_index + 1:]
    start_remove = None
    
    for i, element in enumerate(elements_to_check):
        # Überspringe sectPr (Section Properties)
        if element.tag.endswith("sectPr"):
            continue
        
        para_text = "".join(element.itertext()) if element.tag.endswith("p") else ""
        
        # Prüfe auf Verarbeitungsübersicht-Anfang
        if "Verarbeitungsübersicht" in para_text and start_remove is None:
            start_remove = glossar_table_index + 1 + i
            break
    
    # Entferne alle Absätze ab start_remove bis vor sectPr
    if start_remove is not None:
        # Finde sectPr
        sect_pr_index = None
        for i, element in enumerate(list(body)):
            if element.tag.endswith("sectPr"):
                sect_pr_index = i
                break
        
        # Entferne Absätze zwischen start_remove und sectPr
        if sect_pr_index is not None:
            for i in range(sect_pr_index - 1, start_remove - 1, -1):
                if not list(body)[i].tag.endswith("sectPr"):
                    list(body)[i].getparent().remove(list(body)[i])
    
    # Füge neue Absätze am Ende ein (vor sectPr)
    # Finde sectPr erneut (da die Indizes sich geändert haben)
    sect_pr_index = None
    for i, element in enumerate(list(body)):
        if element.tag.endswith("sectPr"):
            sect_pr_index = i
            break
    
    if sect_pr_index is None:
        sect_pr_index = len(list(body))
    
    for line in summary_text.strip().split("\n"):
        new_para = document.add_paragraph(line)
        body.insert(sect_pr_index, new_para._element)
        sect_pr_index += 1
    
    # Füge Leerzeile am Ende hinzu
    empty_para = document.add_paragraph("")
    body.insert(sect_pr_index, empty_para._element)


def update(glossary_path: Path, candidates: list[dict[str, str]], decisions: list[dict] | None, preview: bool) -> dict:
    document, table, rows = _load_glossary(glossary_path)
    conflicts = []
    added = []
    for candidate in candidates:
        row = rows.get(_key(candidate["Begriff"]))
        if row is None:
            added.append(candidate["Begriff"])
        elif row.cells[1].text.strip() != candidate["Definition"]:
            conflicts.append({
                "Begriff": candidate["Begriff"],
                "bisher": row.cells[1].text.strip(),
                "neu": candidate["Definition"],
            })
    result = {"glossary": str(glossary_path.resolve()), "new_terms": added, "conflicts": conflicts}
    if preview:
        return result

    if decisions is None:
        decisions = []
    if not isinstance(decisions, list):
        raise ValueError("Die Entscheidungen müssen eine JSON-Liste sein.")
    approved: dict[str, bool] = {}
    expected = {_key(conflict["Begriff"]): conflict for conflict in conflicts}
    for decision in decisions:
        if not isinstance(decision, dict) or not isinstance(decision.get("Begriff"), str):
            raise ValueError("Ungültige Entscheidung.")
        key = _key(decision["Begriff"])
        conflict = expected.get(key)
        if key in approved or conflict is None or decision.get("bisher") != conflict["bisher"] or decision.get("neu") != conflict["neu"] or type(decision.get("übernehmen")) is not bool:
            raise ValueError(f"Ungültige oder veraltete Entscheidung für: {decision['Begriff']}")
        approved[key] = decision["übernehmen"]
    if set(approved) != set(expected):
        raise ValueError("Für jede Definitionsänderung ist eine ausdrückliche Entscheidung erforderlich; zuerst --preview ausführen.")

    for candidate in candidates:
        key = _key(candidate["Begriff"])
        row = rows.get(key)
        if row is None:
            row = table.add_row()
            for cell, header in zip(row.cells, HEADERS):
                cell.text = candidate[header]
        elif key in approved and not approved[key]:
            continue
        else:
            if key in approved:
                row.cells[1].text = candidate["Definition"]
            for index, header in ((2, "Kontext/Hinweis"), (3, "Quellen")):
                merged = _append_unique(row.cells[index].text, candidate[header])
                if merged != row.cells[index].text:
                    row.cells[index].text = merged
    
    # Sortiere Glossar alphabetisch nach Begriff
    _sort_glossary_table(table)
    
    glossary_path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".docx", dir=glossary_path.parent, delete=False) as handle:
            temporary = Path(handle.name)
        document.save(str(temporary))
        os.replace(temporary, glossary_path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    extract_parser = commands.add_parser("extract")
    extract_parser.add_argument("input", type=Path)
    extract_parser.add_argument("--glossary", type=Path, required=True)
    extract_parser.add_argument("--output", type=Path, required=True)
    show_parser = commands.add_parser("show")
    show_parser.add_argument("--glossary", type=Path, required=True)
    update_parser = commands.add_parser("update")
    update_parser.add_argument("--glossary", type=Path, required=True)
    update_parser.add_argument("--candidates", type=Path, required=True)
    update_parser.add_argument("--preview", action="store_true")
    update_parser.add_argument("--decisions", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "extract":
            if args.output.resolve() == args.glossary.resolve() or args.output.resolve() == args.input.resolve():
                raise ValueError("Die Extraktionsdatei darf nicht mit Eingabe oder Glossar identisch sein.")
            if args.output.exists():
                raise ValueError(f"Die Extraktionsdatei existiert bereits: {args.output}")
            result = extract(args.input, args.glossary, args.output)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps({"output": str(args.output.resolve()), "documents": len(result["documents"]), "skipped": result["skipped"], "warnings": result["warnings"], "errors": result["errors"]}, ensure_ascii=False, indent=2))
            return 1 if result["errors"] or not result["documents"] else 0
        if args.command == "show":
            if not args.glossary.exists():
                print(json.dumps({"exists": False, "entries": []}, ensure_ascii=False, indent=2))
                return 0
            _, _, rows = _load_glossary(args.glossary)
            entries = [{header: cell.text.strip() for header, cell in zip(HEADERS, row.cells)} for row in rows.values()]
            print(json.dumps({"exists": True, "entries": entries}, ensure_ascii=False, indent=2))
            return 0
        candidates = _load_candidates(args.candidates)
        decisions = json.loads(args.decisions.read_text(encoding="utf-8-sig")) if args.decisions else None
        print(json.dumps(update(args.glossary, candidates, decisions, args.preview), ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, BadZipFile, XMLSyntaxError, DocxPackageNotFoundError, KeyError) as error:
        print(f"Fehler: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
