import unittest

from docx import Document
from docx.enum.style import WD_STYLE_TYPE

from src.master_index_generator import MasterIndexGenerator
from src.models import ContentItem, DetectionResult
from src.report_generator import ReportBuilder
from src.style_mapper import StyleMapper


class NewEditionStyleMapTests(unittest.TestCase):
    def test_controlled_roles_resolve_to_new_edition_styles(self):
        doc = Document()
        for style_name in ["List_Paragraph_A", "Style A.1", "List_Paragraph_i", "i_list paragraph"]:
            if style_name not in [style.name for style in doc.styles]:
                doc.styles.add_style(style_name, WD_STYLE_TYPE.PARAGRAPH)

        mapper = StyleMapper(doc, "config/style_map.json", ReportBuilder("template.docx", "source.docx", {}))

        self.assertEqual(mapper.style_for("controlled_level_3"), "List_Paragraph_A")
        self.assertEqual(mapper.style_for("controlled_level_4"), "Style A.1")
        self.assertEqual(mapper.style_for("controlled_level_5"), "List_Paragraph_i")
        self.assertEqual(mapper.style_for("controlled_level_6"), "i_list paragraph")

    def test_master_index_excludes_controlled_paragraph_roles(self):
        decisions = [
            (
                ContentItem(type="paragraph", text="CHAPTER-0 ADMINISTRATION", metadata={"zone": "body_chapters"}),
                DetectionResult("chapter_heading", "chapter_heading", 1.0, body_text="CHAPTER-0 ADMINISTRATION"),
            ),
            (
                ContentItem(type="paragraph", text="0.1 Purpose", metadata={"zone": "body_chapters"}),
                DetectionResult("heading_1", "heading_1", 0.9, marker="0.1", body_text="Purpose"),
            ),
            (
                ContentItem(type="paragraph", text="0.1.1.1 OM-A is a Controlled Document.", metadata={"zone": "body_chapters"}),
                DetectionResult("controlled_level_3", "controlled_level_3", 0.9, marker="0.1.1.1", body_text="OM-A is a Controlled Document."),
            ),
        ]
        report = ReportBuilder("template.docx", "source.docx", {"manual_abbreviation": "OM-A"})

        rows = MasterIndexGenerator("config/generated_tables.json").generate(decisions, {}, report)
        flat = "\n".join(" | ".join(row) for row in rows)

        self.assertIn("CHAPTER-0 ADMINISTRATION", flat)
        self.assertIn("Purpose", flat)
        self.assertNotIn("OM-A is a Controlled Document", flat)


if __name__ == "__main__":
    unittest.main()
