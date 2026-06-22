import unittest

from docx import Document

from src.models import ContentItem
from src.report_generator import ReportBuilder
from src.validation_report import ContentSourceValidator


class ContentSourceValidatorTests(unittest.TestCase):
    def test_fails_when_template_phrase_is_absent_from_source(self):
        doc = Document()
        doc.add_paragraph("2. Departure Functions")
        report = ReportBuilder("template.docx", "source.docx", {"manual_abbreviation": "OM-A"})

        with self.assertRaises(ValueError):
            ContentSourceValidator("config/audit_rules.json").validate(doc, [], {"manual_abbreviation": "OM-A"}, report)

        self.assertEqual(report.to_dict()["generated"]["content_source_audit"], "failed")
        self.assertTrue(report.to_dict()["content_audit"]["contamination_findings"])

    def test_allows_phrase_that_exists_in_source(self):
        doc = Document()
        doc.add_paragraph("Director Terminal Operations eCopy")
        source = [ContentItem(type="paragraph", text="Director Terminal Operations eCopy")]
        report = ReportBuilder("template.docx", "source.docx", {"manual_abbreviation": "OM-A"})

        ContentSourceValidator("config/audit_rules.json").validate(doc, source, {"manual_abbreviation": "OM-A"}, report)

        self.assertEqual(report.to_dict()["generated"]["content_source_audit"], "passed")
        self.assertFalse(report.to_dict()["content_audit"]["contamination_findings"])


if __name__ == "__main__":
    unittest.main()
