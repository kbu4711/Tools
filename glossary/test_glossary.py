import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from docx import Document
from pptx import Presentation
from pptx.util import Inches
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

import glossary


class GlossaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.target = self.root / "out" / "Glossar.docx"

    def candidate(self, definition="Erste Definition", source="Quelle A"):
        return {"Begriff": "API", "Definition": definition, "Kontext/Hinweis": "Kontext", "Quellen": source}

    def test_extract_recursive_formats_and_skip_target(self):
        nested = self.root / "nested"
        nested.mkdir()
        (self.root / "notes.txt").write_text("Textquelle", encoding="utf-8")
        (nested / "notes.md").write_text("Markdownquelle", encoding="utf-8")
        (nested / "other.xyz").write_text("nicht unterstützt", encoding="utf-8")
        doc = Document()
        doc.add_paragraph("Wordquelle")
        doc.add_table(rows=1, cols=1).cell(0, 0).text = "Tabellenquelle"
        doc.save(nested / "source.docx")
        ppt = Presentation()
        slide = ppt.slides.add_slide(ppt.slide_layouts[6])
        slide.shapes.add_textbox(Inches(1), Inches(1), Inches(5), Inches(1)).text = "Folienquelle"
        ppt.save(nested / "source.pptx")
        pdf = PdfWriter()
        pdf.add_blank_page(width=100, height=100)
        with (nested / "scan.pdf").open("wb") as file:
            pdf.write(file)
        glossary.update(self.target, [self.candidate()], None, False)
        result = glossary.extract(self.root, self.target, self.root / "extraction.json")
        self.assertEqual(len(result["documents"]), 4)
        self.assertTrue(any("other.xyz" in item for item in result["skipped"]))
        self.assertTrue(any("scan.pdf" in item["path"] for item in result["errors"]))
        self.assertFalse(any(item["path"] == str(self.target) for item in result["documents"]))
        word = next(item for item in result["documents"] if item["path"].endswith("source.docx"))
        self.assertIn("Tabellenquelle", word["units"][0]["text"])
        slide = next(item for item in result["documents"] if item["path"].endswith("source.pptx"))
        self.assertEqual(slide["units"][0]["location"], "Folie 1")
        single = glossary.extract(nested / "source.docx", self.target, self.root / "out.json")
        self.assertEqual(len(single["documents"]), 1)

    def test_review_required_reject_and_accept(self):
        glossary.update(self.target, [self.candidate()], None, False)
        candidate = self.candidate("Neue Definition", "Quelle B")
        preview = glossary.update(self.target, [candidate], None, True)
        conflict = preview["conflicts"][0]
        original = self.target.read_bytes()
        with self.assertRaises(ValueError):
            glossary.update(self.target, [candidate], None, False)
        self.assertEqual(self.target.read_bytes(), original)
        with self.assertRaises(ValueError):
            glossary.update(self.target, [candidate], [{**conflict, "bisher": "veraltet", "übernehmen": True}], False)
        glossary.update(self.target, [candidate], [{**conflict, "übernehmen": False}], False)
        cells = Document(self.target).tables[0].rows[1].cells
        self.assertEqual([cell.text for cell in cells], ["API", "Erste Definition", "Kontext", "Quelle A"])
        glossary.update(self.target, [candidate], [{**conflict, "übernehmen": True}], False)
        cells = Document(self.target).tables[0].rows[1].cells
        self.assertEqual(cells[1].text, "Neue Definition")
        self.assertEqual(cells[3].text, "Quelle A\nQuelle B")

    def test_new_and_existing_terms_preserve_document(self):
        glossary.update(self.target, [self.candidate()], None, False)
        document = Document(self.target)
        document.add_paragraph("Vorhandener Inhalt")
        document.save(self.target)
        glossary.update(self.target, [self.candidate(source="Quelle A\nQuelle B"), {
            "Begriff": "SDK", "Definition": "Werkzeuge", "Kontext/Hinweis": "Nutzung", "Quellen": "Quelle C"
        }], None, False)
        document = Document(self.target)
        self.assertIn("Vorhandener Inhalt", [p.text for p in document.paragraphs])
        self.assertEqual(len(document.tables[0].rows), 3)
        self.assertEqual(document.tables[0].rows[1].cells[3].text, "Quelle A\nQuelle B")

    def test_cli_partial_failure_and_invalid_existing_glossary(self):
        (self.root / "good.txt").write_text("Text", encoding="utf-8")
        (self.root / "bad.docx").write_text("ungültig", encoding="utf-8")
        output = self.root / "extract.json"
        result = subprocess.run([sys.executable, str(Path(glossary.__file__)), "extract", str(self.root),
                                 "--glossary", str(self.target), "--output", str(output)],
                                capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 1)
        data = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(len(data["documents"]), 1)
        self.assertEqual(len(data["errors"]), 1)
        self.target.parent.mkdir()
        Document().save(self.target)
        before = self.target.read_bytes()
        with self.assertRaises(ValueError):
            glossary.update(self.target, [self.candidate()], None, False)
        self.assertEqual(self.target.read_bytes(), before)

    def test_pdf_text_and_empty_page_warning(self):
        writer = PdfWriter()
        page = writer.add_blank_page(width=200, height=200)
        font = DictionaryObject({
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        })
        page[NameObject("/Resources")] = DictionaryObject({
            NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})
        })
        stream = DecodedStreamObject()
        stream.set_data(b"BT /F1 12 Tf 10 100 Td (PDF source) Tj ET")
        page[NameObject("/Contents")] = writer._add_object(stream)
        writer.add_blank_page(width=200, height=200)
        path = self.root / "source.pdf"
        with path.open("wb") as file:
            writer.write(file)
        result = glossary.extract(path, self.target, self.root / "extract.json")
        self.assertEqual(result["documents"][0]["units"][0]["location"], "Seite 1")
        self.assertIn("PDF source", result["documents"][0]["units"][0]["text"])
        self.assertIn("Seite 2", result["warnings"][0])

    def test_cli_show_and_prevent_overwriting_input(self):
        source = self.root / "source.txt"
        source.write_text("Inhalt", encoding="utf-8")
        script = str(Path(glossary.__file__))
        result = subprocess.run([sys.executable, script, "extract", str(source), "--glossary",
                                 str(self.target), "--output", str(source)], capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(source.read_text(encoding="utf-8"), "Inhalt")
        glossary.update(self.target, [self.candidate()], None, False)
        result = subprocess.run([sys.executable, script, "show", "--glossary", str(self.target)],
                                capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["entries"][0]["Begriff"], "API")


if __name__ == "__main__":
    unittest.main()
