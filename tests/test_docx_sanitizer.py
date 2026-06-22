import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from lxml import etree

from src.docx_sanitizer import DocxSanitizer
from src.page_numbering_manager import PageNumberingManager


WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
MC_NS = "http://schemas.openxmlformats.org/markup-compatibility/2006"


class DocxSanitizerTests(unittest.TestCase):
    def test_sanitizer_removes_bookmarks_and_no_border_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "dirty.docx"
            doc = Document()
            paragraph = doc.add_paragraph("Body")
            start = OxmlElement("w:bookmarkStart")
            start.set(qn("w:id"), "7")
            start.set(qn("w:name"), "BrokenBookmark")
            end = OxmlElement("w:bookmarkEnd")
            end.set(qn("w:id"), "7")
            paragraph._p.insert(0, start)
            paragraph._p.append(end)

            p_bdr = OxmlElement("w:pBdr")
            top = OxmlElement("w:top")
            top.set(qn("w:val"), "none")
            p_bdr.append(top)
            paragraph._p.get_or_add_pPr().append(p_bdr)
            doc.save(path)

            summary = DocxSanitizer().sanitize(path)

            self.assertEqual(summary["bookmark_elements_removed"], 2)
            self.assertEqual(summary["paragraph_border_blocks_removed"], 1)
            with ZipFile(path) as zip_file:
                root = etree.fromstring(zip_file.read("word/document.xml"))
            self.assertFalse(root.xpath(".//w:bookmarkStart | .//w:bookmarkEnd", namespaces={"w": WORD_NS}))
            self.assertFalse(root.xpath(".//w:pBdr", namespaces={"w": WORD_NS}))

    def test_header_page_field_preserves_ignorable_prefixes(self):
        header_xml = (
            b'<w:hdr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
            b'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" '
            b'xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml" '
            b'mc:Ignorable="w14"><w:p /></w:hdr>'
        )

        patched = PageNumberingManager("config/page_numbering_rules.json")._header_with_page_field(
            header_xml,
            "0",
            {"edition_number": "06", "revision_number": "00"},
            "word_fields",
        )

        root = etree.fromstring(patched)
        ignorable = root.get(f"{{{MC_NS}}}Ignorable", "")
        self.assertIn("w14", ignorable.split())
        self.assertIn("w14", root.nsmap)


if __name__ == "__main__":
    unittest.main()
