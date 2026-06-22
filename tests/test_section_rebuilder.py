import unittest

from src.models import ContentItem, DetectionResult
from src.report_generator import ReportBuilder
from src.section_break_manager import SectionBreakManager
from src.section_rebuilder import SectionRebuilder


class SectionRebuilderTests(unittest.TestCase):
    def test_groups_body_into_chapter_and_annex_sections(self):
        decisions = [
            (
                ContentItem(type="paragraph", text="CHAPTER-0 ADMINISTRATION", metadata={"zone": "body_chapters"}),
                DetectionResult("chapter_heading", "chapter_heading", 1.0),
            ),
            (
                ContentItem(type="paragraph", text="0.1 Introduction", metadata={"zone": "body_chapters"}),
                DetectionResult("heading_1", "heading_1", 0.9),
            ),
            (
                ContentItem(type="paragraph", text="CHAPTER-1 ORGANISATION", metadata={"zone": "body_chapters"}),
                DetectionResult("chapter_heading", "chapter_heading", 1.0),
            ),
            (
                ContentItem(type="paragraph", text="ANNEXE-1A | Organogram", metadata={"zone": "annexes"}),
                DetectionResult("appendix_heading", "appendix_heading", 1.0),
            ),
        ]
        report = ReportBuilder("new.docx", "old.docx", {})

        sections = SectionRebuilder(SectionBreakManager("config/manual_sections.json")).build(decisions, report)

        self.assertEqual([section.kind for section in sections], ["chapter", "chapter", "annex"])
        self.assertEqual([section.prefix for section in sections], ["0", "1", "1A"])
        self.assertEqual([len(section.decisions) for section in sections], [2, 1, 1])
        self.assertEqual(report.to_dict()["section_rebuild"]["mode"], "section_by_section")

    def test_reports_body_content_before_first_chapter(self):
        decisions = [
            (
                ContentItem(type="paragraph", text="Unexpected body line", metadata={"zone": "body_chapters"}),
                DetectionResult("body", "body", 0.8),
            )
        ]
        report = ReportBuilder("new.docx", "old.docx", {})

        sections = SectionRebuilder(SectionBreakManager("config/manual_sections.json")).build(decisions, report)

        self.assertEqual(sections[0].kind, "body_preamble")
        self.assertTrue(any("before the first detected chapter" in warning for warning in report.to_dict()["warnings"]))


if __name__ == "__main__":
    unittest.main()
