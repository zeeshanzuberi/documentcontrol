import unittest

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml import OxmlElement

from src.abbreviations_extractor import AbbreviationsExtractor
from src.definitions_extractor import DefinitionsExtractor
from src.front_matter_updater import FrontMatterUpdater
from src.models import ContentItem, DetectionResult
from src.report_generator import ReportBuilder
from src.section_break_manager import SectionBreakManager
from src.style_mapper import StyleMapper


class ExtractorsAndSectionsTests(unittest.TestCase):
    def test_definitions_and_abbreviations_capture_source_indices(self):
        items = [
            ContentItem(type="paragraph", text="Definitions", metadata={"source_index": 0}),
            ContentItem(type="paragraph", text="MEL: Minimum Equipment List", metadata={"source_index": 1}),
            ContentItem(type="paragraph", text="Abbreviations", metadata={"source_index": 2}),
            ContentItem(type="table", rows=[["MEL", "Minimum Equipment List"]], metadata={"source_index": 3}),
            ContentItem(type="paragraph", text="CHAPTER 1 GENERAL", metadata={"source_index": 4}),
        ]
        definitions = DefinitionsExtractor().extract(items)
        abbreviations = AbbreviationsExtractor().extract(items)
        self.assertTrue(definitions.found)
        self.assertTrue(abbreviations.found)
        self.assertIn(1, definitions.source_indices)
        self.assertIn(3, abbreviations.source_indices)

    def test_section_prefixes_for_chapter_and_appendix(self):
        manager = SectionBreakManager("config/manual_sections.json")
        chapter = DetectionResult("chapter_heading", "chapter_heading", 1.0)
        appendix = DetectionResult("appendix_heading", "appendix_heading", 1.0)
        self.assertEqual(manager.prefix_for("Chapter One General", chapter), "1")
        self.assertEqual(manager.prefix_for("CHAPTER 2 OPERATIONS", chapter), "2")
        self.assertEqual(manager.prefix_for("Chapter – 12: Rules of the Air", chapter), "12")
        self.assertEqual(manager.prefix_for("Appendix A Forms", appendix), "A")

    def test_front_matter_sample_text_on_section_break_paragraph_is_cleared(self):
        doc = Document()
        doc.add_paragraph("Definitions")
        sample = doc.add_paragraph("Template sample definition that must not remain")
        p_pr = sample._p.get_or_add_pPr()
        p_pr.append(OxmlElement("w:sectPr"))

        report = ReportBuilder("template.docx", "source.docx", {})
        mapper = StyleMapper(doc, "config/style_map.json", report)
        updater = FrontMatterUpdater("config/manual_sections.json", "config/front_matter_rules.json")
        updater.update(
            doc,
            mapper,
            {},
            {"definitions": None},
            {},
            {
                "generate_lep": False,
                "generate_ror": False,
                "generate_roa": False,
                "extract_definitions": True,
                "extract_abbreviations": False,
                "extract_conformance": False,
            },
            report,
        )

        self.assertNotIn("Template sample definition that must not remain", [p.text for p in doc.paragraphs])
        self.assertGreater(report.to_dict()["counts"]["template_paragraphs_removed"], 0)

    def test_toc_style_rows_are_not_front_matter_boundaries(self):
        doc = Document()
        paragraph = doc.add_paragraph("List of Effective Pages (LEP)")
        doc.styles.add_style("toc synthetic", WD_STYLE_TYPE.PARAGRAPH)
        paragraph.style = "toc synthetic"

        updater = FrontMatterUpdater("config/manual_sections.json", "config/front_matter_rules.json")
        self.assertFalse(updater._is_front_matter_boundary(paragraph))


if __name__ == "__main__":
    unittest.main()
