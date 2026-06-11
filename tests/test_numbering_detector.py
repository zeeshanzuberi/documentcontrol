import unittest

from src.models import ContentItem
from src.numbering_detector import NumberingDetector


class NumberingDetectorTests(unittest.TestCase):
    def setUp(self):
        self.detector = NumberingDetector("config/numbering_rules.json")

    def test_dotted_number_is_heading(self):
        item = ContentItem(type="paragraph", text="1.1 Flight Crew Responsibilities")
        result = self.detector.detect(item)
        self.assertEqual(result.role, "heading_2")
        self.assertEqual(result.marker, "1.1")
        self.assertEqual(result.body_text, "Flight Crew Responsibilities")

    def test_numbered_sentence_is_list_not_heading(self):
        item = ContentItem(type="paragraph", text="1. The pilot shall review all dispatch documents.")
        result = self.detector.detect(item)
        self.assertEqual(result.role, "paragraph_number_level_2")

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


if __name__ == "__main__":
    unittest.main()
