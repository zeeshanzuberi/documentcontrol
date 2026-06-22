import unittest

from src.models import ContentItem
from src.numbering_detector import NumberingDetector


class NumberingDetectorTests(unittest.TestCase):
    def setUp(self):
        self.detector = NumberingDetector("config/numbering_rules.json")

    def test_dotted_number_is_heading(self):
        item = ContentItem(type="paragraph", text="1.1 Flight Crew Responsibilities")
        result = self.detector.detect(item)
        self.assertEqual(result.role, "heading_1")
        self.assertEqual(result.marker, "1.1")
        self.assertEqual(result.body_text, "Flight Crew Responsibilities")

    def test_new_edition_dotted_levels_use_controlled_paragraphs(self):
        self.assertEqual(
            self.detector.detect(ContentItem(type="paragraph", text="0.1 Introduction")).role,
            "heading_1",
        )
        self.assertEqual(
            self.detector.detect(ContentItem(type="paragraph", text="0.1.1 General")).role,
            "heading_2",
        )
        self.assertEqual(
            self.detector.detect(ContentItem(type="paragraph", text="0.1.1.1 OM-A is a Controlled Document.")).role,
            "controlled_level_3",
        )
        self.assertEqual(
            self.detector.detect(ContentItem(type="paragraph", text="0.1.1.1.1 Filing instructions apply.")).role,
            "controlled_level_4",
        )

    def test_old_heading_3_source_style_becomes_controlled_paragraph_in_body_zone(self):
        item = ContentItem(
            type="paragraph",
            text="Change Request Form",
            style_name="Heading 3",
            metadata={"zone": "body_chapters"},
        )
        result = self.detector.detect(item)
        self.assertEqual(result.role, "controlled_level_3")

    def test_visible_new_edition_number_overrides_old_heading_3_style(self):
        item = ContentItem(
            type="paragraph",
            text="0.1.1 General",
            style_name="Heading 3",
            metadata={"zone": "body_chapters"},
        )
        result = self.detector.detect(item)
        self.assertEqual(result.role, "heading_2")

    def test_annex_heading_3_style_still_becomes_appendix_section(self):
        item = ContentItem(
            type="paragraph",
            text="ANNEXE-7A | DETAILS OF CREW COMPLEMENT",
            style_name="Heading 3",
            metadata={"zone": "annexes"},
        )
        result = self.detector.detect(item)
        self.assertEqual(result.role, "appendix_heading")

    def test_numbered_sentence_is_list_not_heading(self):
        item = ContentItem(type="paragraph", text="1. The pilot shall review all dispatch documents.")
        result = self.detector.detect(item)
        self.assertEqual(result.role, "paragraph_number_level_2")

    def test_weak_numbered_heading_is_preserved_as_body(self):
        item = ContentItem(type="paragraph", text="1.1 the pilot shall ensure that all operational documents are reviewed.")
        result = self.detector.detect(item)
        self.assertEqual(result.role, "body")
        self.assertIn("Ambiguous", result.warning)

    def test_alpha_and_roman_lists(self):
        self.assertEqual(
            self.detector.detect(ContentItem(type="paragraph", text="a. The following items are required.")).role,
            "paragraph_number_level_3",
        )
        self.assertEqual(
            self.detector.detect(ContentItem(type="paragraph", text="i. First condition applies.")).role,
            "paragraph_number_level_4",
        )
        self.assertEqual(
            self.detector.detect(ContentItem(type="paragraph", text="a) Additional item.")).role,
            "paragraph_number_level_5",
        )

    def test_chapter_and_appendix(self):
        self.assertEqual(
            self.detector.detect(ContentItem(type="paragraph", text="CHAPTER 1 GENERAL")).role,
            "chapter_heading",
        )
        self.assertEqual(
            self.detector.detect(ContentItem(type="paragraph", text="Appendix A Forms")).role,
            "appendix_heading",
        )

    def test_new_edition_toc_heading_is_not_chapter(self):
        item = ContentItem(type="paragraph", text="Chapter – 1: Table of Contents", style_name="Chapter Heading")
        result = self.detector.detect(item)
        self.assertEqual(result.role, "body")

    def test_om_a_chapter_zero_title_is_inferred(self):
        item = ContentItem(
            type="paragraph",
            text="Admin & Control of Operations Manual",
            style_name="Heading 1",
        )
        result = self.detector.detect(item)
        self.assertEqual(result.role, "chapter_heading")


if __name__ == "__main__":
    unittest.main()
