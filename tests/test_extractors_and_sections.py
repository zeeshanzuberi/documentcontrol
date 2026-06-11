import unittest

from src.abbreviations_extractor import AbbreviationsExtractor
from src.definitions_extractor import DefinitionsExtractor
from src.models import ContentItem, DetectionResult
from src.section_break_manager import SectionBreakManager


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
        self.assertEqual(manager.prefix_for("Appendix A Forms", appendix), "A")


if __name__ == "__main__":
    unittest.main()
