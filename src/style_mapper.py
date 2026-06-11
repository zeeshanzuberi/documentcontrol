from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from docx.document import Document as DocxDocument
from docx.enum.style import WD_STYLE_TYPE


class StyleMapper:
    """Resolves semantic roles to exact styles present in the uploaded template."""

    def __init__(self, document: DocxDocument, config_path: str | Path = "config/style_map.json", report: Any | None = None):
        self.document = document
        self.config_path = Path(config_path)
        self.config = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.report = report
        self.styles = {style.name: style for style in document.styles}
        self.paragraph_styles = {
            style.name for style in document.styles if style.type == WD_STYLE_TYPE.PARAGRAPH
        }
        self.table_styles = {
            style.name for style in document.styles if style.type == WD_STYLE_TYPE.TABLE
        }

    def style_for(self, role: str) -> str:
        configured = self.config.get("target_styles", {}).get(role, "")
        if configured in self.paragraph_styles:
            return configured

        fallback = self.config.get("fallback_style", "Normal")
        if self.report and configured:
            self.report.add_missing_style(configured, role)
        if fallback in self.paragraph_styles:
            return fallback
        return "Normal"

    def table_style(self) -> str | None:
        configured = self.config.get("table_style", "")
        if configured in self.table_styles:
            return configured
        fallback = self.config.get("fallback_table_style", "")
        if self.report and configured:
            self.report.add_missing_style(configured, "table")
        if fallback in self.table_styles:
            return fallback
        return None

    def table_text_style(self) -> str | None:
        style = self.config.get("target_styles", {}).get("table_text", "")
        return style if style in self.paragraph_styles else None

    def source_style_role(self, source_style_name: str) -> str:
        return self.config.get("source_style_map", {}).get(source_style_name, "")

    def style_has_auto_numbering(self, style_name: str) -> bool:
        style = self.styles.get(style_name)
        if not style:
            return False
        return bool(style._element.xpath("./w:pPr/w:numPr"))

    def should_strip_numbering(self) -> bool:
        return bool(self.config.get("strip_numbering_when_style_has_auto_numbering", True))

    def revision_bar_config(self) -> dict[str, str]:
        return self.config.get("revision_bars", {})

    def content_bookmarks(self) -> list[str]:
        return list(self.config.get("content_bookmarks", []))

    def content_placeholders(self) -> list[str]:
        return list(self.config.get("content_placeholders", []))

    def replace_existing_body(self) -> bool:
        return bool(self.config.get("replace_existing_body_after_bookmark", True))

    def update_fields_on_open(self) -> bool:
        return bool(self.config.get("update_fields_on_open", True))
