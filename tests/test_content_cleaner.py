import unittest

from src.content_cleaner import ContentCleaner
from src.models import ContentItem
from src.numbering_detector import NumberingDetector
from src.report_generator import ReportBuilder


class ContentCleanerTests(unittest.TestCase):
    def test_skips_old_control_pages_but_keeps_definitions(self):
        items = [
            ContentItem(type="paragraph", text="Title Page"),
            ContentItem(type="paragraph", text="Record of Revisions"),
            ContentItem(type="paragraph", text="Definitions"),
            ContentItem(type="paragraph", text="Dispatch Release: A document issued before flight."),
        ]
        report = ReportBuilder("template.docx", "source.docx", {})
        cleaner = ContentCleaner(NumberingDetector("config/numbering_rules.json"))
        cleaned = cleaner.clean(items, report)
        self.assertEqual(cleaned[0].text, "Definitions")
        self.assertEqual(report.to_dict()["skipped_front_matter"]["items"], 2)


if __name__ == "__main__":
    unittest.main()
