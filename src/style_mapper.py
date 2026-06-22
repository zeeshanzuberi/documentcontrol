from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from docx.document import Document as DocxDocument
from docx.enum.style import WD_STYLE_TYPE

from .xml_utils import xml_xpath


class StyleMapper:
    """Resolves semantic roles to exact styles present in the uploaded template."""

    def __init__(self, document: DocxDocument, config_path: str | Path = "config/style_map.json", report: Any | None = None):
        self.document = document
        self.config_path = Path(config_path)
        self.config = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.new_edition_config = self._load_new_edition_config()
        self.report = report
        self.styles = {style.name: style for style in document.styles}
        self.paragraph_styles = {
            style.name for style in document.styles if style.type == WD_STYLE_TYPE.PARAGRAPH
        }
        self.table_styles = {
            style.name for style in document.styles if style.type == WD_STYLE_TYPE.TABLE
        }
        self.target_styles = self._flatten_target_styles()

    def style_for(self, role: str) -> str:
        configured = self.target_styles.get(role, "")
        for candidate in self._style_candidates(role, configured):
            if candidate in self.paragraph_styles:
                return candidate

        fallback = self.config.get("fallback_style", "Normal")
        if self.report and configured:
            self.report.add_missing_style(configured, role)
        if fallback in self.paragraph_styles:
            return fallback
        return "Normal"

    def table_style(self) -> str | None:
        configured = (
            self.config.get("table_styles", {}).get("default_table", "")
            or self.config.get("table_style", "")
        )
        candidates = [configured, *self.config.get("table_style_aliases", [])]
        for candidate in candidates:
            if candidate in self.table_styles:
                return candidate
        fallback = self.config.get("fallback_table_style", "")
        if self.report and configured:
            self.report.add_missing_style(configured, "table")
        if fallback in self.table_styles:
            return fallback
        return None

    def table_text_style(self) -> str | None:
        style = self.target_styles.get("table_text", "")
        return style if style in self.paragraph_styles else None

    def source_style_role(self, source_style_name: str) -> str:
        return self.config.get("source_style_map", {}).get(source_style_name, "")

    def style_has_auto_numbering(self, style_name: str) -> bool:
        style = self.styles.get(style_name)
        if not style:
            return False
        return bool(xml_xpath(style._element, "./w:pPr/w:numPr"))

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

    def _style_candidates(self, role: str, configured: str) -> list[str]:
        candidates = [configured] if configured else []
        candidates.extend(self.config.get("style_aliases", {}).get(role, []))
        return [candidate for candidate in candidates if candidate]

    def _flatten_target_styles(self) -> dict[str, str]:
        flattened: dict[str, str] = {}
        flattened.update(self.config.get("target_styles", {}))
        def put(role: str, value: str) -> None:
            if value:
                flattened[role] = value

        heading_styles = self.config.get("heading_styles", {})
        put("chapter_heading", heading_styles.get("chapter_heading", ""))
        put("heading_1", heading_styles.get("heading_1", ""))
        put("heading_2", heading_styles.get("heading_2", ""))
        put("heading_3", heading_styles.get("heading_3", ""))
        put("heading_4", heading_styles.get("heading_4", ""))
        put("heading_5", heading_styles.get("heading_5", ""))
        put("heading_6", heading_styles.get("heading_6", ""))
        put("appendix_heading", heading_styles.get("appendix_heading", ""))
        put("section_heading", heading_styles.get("section_heading", ""))

        paragraph_styles = self.config.get("paragraph_styles", {})
        put("body", paragraph_styles.get("body_text", "") or paragraph_styles.get("normal", ""))
        put("normal", paragraph_styles.get("normal", ""))
        put("note", paragraph_styles.get("note", ""))
        put("caution", paragraph_styles.get("caution", ""))
        put("warning", paragraph_styles.get("warning", ""))
        put("caption", paragraph_styles.get("caption", ""))
        put("table_text", paragraph_styles.get("table_text", ""))
        put("definition", paragraph_styles.get("definition", "") or paragraph_styles.get("body_text", ""))
        put("reference", paragraph_styles.get("reference", "") or paragraph_styles.get("body_text", ""))
        put("bullet", paragraph_styles.get("bullet", "") or "List Bullet")

        numbering_styles = self.config.get("paragraph_numbering_styles", {})
        put("paragraph_number_level_1", numbering_styles.get("level_1", ""))
        put("paragraph_number_level_2", numbering_styles.get("level_2", ""))
        put("paragraph_number_level_3", numbering_styles.get("level_3", ""))
        put("paragraph_number_level_4", numbering_styles.get("level_4", ""))
        put("paragraph_number_level_5", numbering_styles.get("level_5", ""))
        controlled_styles = {
            **self.new_edition_config.get("controlled_paragraph_styles", {}),
            **self.config.get("controlled_paragraph_styles", {}),
        }
        put("controlled_level_3", controlled_styles.get("old_heading_3_or_level_3", ""))
        put("controlled_level_4", controlled_styles.get("old_heading_4_or_level_4", ""))
        put("controlled_level_5", controlled_styles.get("old_heading_5_or_level_5", ""))
        put("controlled_level_6", controlled_styles.get("old_heading_6_or_level_6", ""))
        return {key: value for key, value in flattened.items() if value}

    def _load_new_edition_config(self) -> dict[str, Any]:
        path = self.config_path.with_name("new_edition_style_map.json")
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
