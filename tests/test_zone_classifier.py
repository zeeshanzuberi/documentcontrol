import unittest

from src.body_content_filter import BodyContentFilter
from src.models import ContentItem
from src.report_generator import ReportBuilder
from src.zone_classifier import ZoneClassifier


class ZoneClassifierTests(unittest.TestCase):
    def test_master_index_and_chapter_toc_rows_do_not_start_body(self):
        items = [
            ContentItem(type="paragraph", text="MASTER INDEX OF OM-A", style_name="Heading 1", metadata={"source_index": 0}),
            ContentItem(type="paragraph", text="Annex-7A to 7G", style_name="Body Text Indent", metadata={"source_index": 1}),
            ContentItem(type="paragraph", text="TABLE OF CONTENTS: CHAPTER-0", style_name="Plain Text", metadata={"source_index": 2}),
            ContentItem(type="paragraph", text="CHAPTER-0 ADMINISTRATION 1", style_name="toc 1", metadata={"source_index": 3}),
            ContentItem(type="paragraph", text="CHAPTER-0 ADMINISTRATION", style_name="Heading 1", metadata={"source_index": 4}),
            ContentItem(type="paragraph", text="0.1 Introduction", style_name="Heading 2", metadata={"source_index": 5}),
        ]

        report = ReportBuilder("template.docx", "source.docx", {})
        zones = ZoneClassifier().classify(items, report)
        body = zones.body_items()

        self.assertEqual(body[0].text, "CHAPTER-0 ADMINISTRATION")
        self.assertNotIn("Annex-7A to 7G", [item.text for item in body])
        self.assertNotIn("TABLE OF CONTENTS: CHAPTER-0", [item.text for item in body])
        self.assertEqual(zones.zone_items("old_master_index")[1].text, "Annex-7A to 7G")
        self.assertEqual(zones.zone_items("old_chapter_tocs")[0].text, "TABLE OF CONTENTS: CHAPTER-0")

    def test_blank_page_marker_is_reported_and_kept_for_body_blank_page_handler(self):
        items = [
            ContentItem(type="paragraph", text="CHAPTER-1 GENERAL", style_name="Heading 1", metadata={"source_index": 0}),
            ContentItem(type="paragraph", text="INTENTIONALLY LEFT BLANK", style_name="Normal", metadata={"source_index": 1}),
            ContentItem(type="paragraph", text="1.1 Scope", style_name="Heading 2", metadata={"source_index": 2}),
        ]

        report = ReportBuilder("template.docx", "source.docx", {})
        zones = ZoneClassifier().classify(items, report)

        self.assertEqual(len(zones.zone_items("intentionally_left_blank_pages")), 1)
        self.assertIn("INTENTIONALLY LEFT BLANK", [item.text for item in zones.body_items()])

    def test_body_filter_removes_annex_list_and_toc_noise(self):
        items = [
            ContentItem(type="paragraph", text="CHAPTER-7 FATIGUE MANAGEMENT", style_name="Heading 1"),
            ContentItem(type="paragraph", text="LIST OF ANNEXES: CHAPTER-7", style_name="Heading 2"),
            ContentItem(type="paragraph", text="Annex No Description", style_name="Normal"),
            ContentItem(type="paragraph", text="Annex-7A Details of Crew Complement", style_name="List Paragraph"),
            ContentItem(type="paragraph", text="ANNEX-7A | DETAILS OF CREW COMPLEMENT", style_name="Heading 3"),
        ]
        report = ReportBuilder("template.docx", "source.docx", {})

        filtered = BodyContentFilter().filter(items, report)
        filtered_text = [item.text for item in filtered]

        self.assertNotIn("LIST OF ANNEXES: CHAPTER-7", filtered_text)
        self.assertNotIn("Annex No Description", filtered_text)
        self.assertIn("Annex-7A Details of Crew Complement", filtered_text)
        self.assertIn("ANNEX-7A | DETAILS OF CREW COMPLEMENT", filtered_text)

    def test_new_edition_chapter_toc_releases_to_body(self):
        items = [
            ContentItem(type="paragraph", text="Definitions", style_name="Center Heading 1", metadata={"source_index": 0}),
            ContentItem(type="paragraph", text="The following definitions are used.", style_name="Normal", metadata={"source_index": 1}),
            ContentItem(type="paragraph", text="Chapter – 1: Table of Contents", style_name="Chapter Heading", metadata={"source_index": 2}),
            ContentItem(type="paragraph", text="Admin & Control of Operations Manual", style_name="Heading 1", metadata={"source_index": 3}),
            ContentItem(type="paragraph", text="Para Description Page No", style_name="Normal", metadata={"source_index": 4}),
            ContentItem(type="paragraph", text="0.1 Introduction 0-3", style_name="toc 2", metadata={"source_index": 5}),
            ContentItem(type="paragraph", text="Introduction", style_name="Heading 2", metadata={"source_index": 6}),
        ]

        report = ReportBuilder("template.docx", "source.docx", {})
        zones = ZoneClassifier().classify(items, report)
        body = BodyContentFilter().filter(zones.body_items(), report)
        body_text = [item.text for item in body]

        self.assertEqual(zones.zone_items("old_definitions")[0].text, "Definitions")
        self.assertEqual(zones.zone_items("old_chapter_tocs")[0].text, "Chapter – 1: Table of Contents")
        self.assertIn("Admin & Control of Operations Manual", body_text)
        self.assertIn("Introduction", body_text)
        self.assertNotIn("Para Description Page No", body_text)
        self.assertNotIn("0.1 Introduction 0-3", body_text)

    def test_old_chapter_toc_title_line_does_not_become_body_preamble(self):
        items = [
            ContentItem(type="paragraph", text="TABLE OF CONTENTS: CHAPTER-0", style_name="Plain Text", metadata={"source_index": 0}),
            ContentItem(type="paragraph", text="ADMINISTRATION & CONTROL OF OPERATIONS MANUAL", style_name="Plain Text", metadata={"source_index": 1}),
            ContentItem(type="paragraph", text="Para Description Page No", style_name="Body Text Indent", metadata={"source_index": 2}),
            ContentItem(type="paragraph", text="----------xxx----------", style_name="Body Text Indent", metadata={"source_index": 3}),
            ContentItem(type="paragraph", text="CHAPTER-0 ADMINISTRATION & CONTROL OF OPERATIONS MANUAL", style_name="Heading 1", metadata={"source_index": 4}),
        ]

        report = ReportBuilder("template.docx", "source.docx", {})
        zones = ZoneClassifier().classify(items, report)
        body_text = [item.text for item in zones.body_items()]

        self.assertNotIn("ADMINISTRATION & CONTROL OF OPERATIONS MANUAL", body_text)
        self.assertNotIn("----------xxx----------", body_text)
        self.assertEqual(body_text[0], "CHAPTER-0 ADMINISTRATION & CONTROL OF OPERATIONS MANUAL")


if __name__ == "__main__":
    unittest.main()
