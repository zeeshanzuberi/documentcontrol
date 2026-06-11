from __future__ import annotations

import re

from docx.enum.text import WD_ALIGN_PARAGRAPH

from .models import ContentItem
from .report_generator import ReportBuilder
from .style_mapper import StyleMapper


class BlankPageHandler:
    """Keeps intentionally blank pages as standalone pages."""

    PATTERN = re.compile(r"^(this page is )?intentionally left blank\.?$", re.I)

    def is_blank_marker(self, item: ContentItem) -> bool:
        if item.type != "paragraph":
            return False
        text = " ".join((item.text or "").split()).strip()
        return bool(self.PATTERN.match(text))

    def insert_blank_page(self, document, item: ContentItem, mapper: StyleMapper, report: ReportBuilder) -> None:
        document.add_page_break()
        report.increment("page_breaks_inserted")
        paragraph = document.add_paragraph()
        style_name = "ILB" if "ILB" in {style.name for style in document.styles} else mapper.style_for("normal")
        try:
            paragraph.style = style_name
        except Exception:
            report.add_missing_style(style_name, "intentionally_left_blank")
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        paragraph.add_run(item.text.strip() or "Intentionally Left Blank")
        document.add_page_break()
        report.increment("page_breaks_inserted")
        report.increment("intentionally_blank_pages")
        report.data["intentionally_blank_pages"].append(item.sample())
