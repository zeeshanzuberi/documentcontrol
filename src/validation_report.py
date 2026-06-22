from __future__ import annotations

import json
import re
from pathlib import Path

from docx.document import Document as DocxDocument
from docx.text.paragraph import Paragraph

from .models import ContentItem
from .report_generator import ReportBuilder


class ContentSourceValidator:
    """Fails closed when target/template-only content contaminates the output."""

    def __init__(self, config_path: str | Path = "config/audit_rules.json"):
        self.config_path = Path(config_path)
        self.config = json.loads(self.config_path.read_text(encoding="utf-8")) if self.config_path.exists() else {}

    def validate(
        self,
        document: DocxDocument,
        source_items: list[ContentItem],
        metadata: dict[str, str],
        report: ReportBuilder,
    ) -> None:
        if not self._enabled_for_manual(metadata):
            report.data["generated"]["content_source_audit"] = "not_required_for_manual"
            return

        source_text = self._source_text(source_items)
        output_entries = self._document_entries(document)
        output_text = "\n".join(text for _, text in output_entries)
        failed_phrases: list[str] = []

        strict_count_phrases = set(self.config.get("strict_count_phrases", []))
        for phrase in self.config.get("fdm_contamination_phrases", []):
            source_count = self._count(source_text, phrase)
            output_count = self._count(output_text, phrase)
            if output_count == 0:
                continue
            if source_count == 0 or (phrase in strict_count_phrases and output_count > source_count):
                locations = self._locations(output_entries, phrase)
                report.add_contamination_finding(phrase, output_count, source_count, locations)
                failed_phrases.append(phrase)

        if failed_phrases:
            report.data["generated"]["content_source_audit"] = "failed"
            message = (
                "Content source validation failed. The output contains target/template or FDM content "
                "that is not present in the old approved source manual: "
                + ", ".join(failed_phrases[:8])
            )
            report.add_error(message)
            raise ValueError(message)

        report.data["generated"]["content_source_audit"] = "passed"
        report.add_quality_check("FDM/template contamination check", "PASS", "No configured contamination phrase exceeded source occurrence count.")

    def _enabled_for_manual(self, metadata: dict[str, str]) -> bool:
        abbreviation = (metadata.get("manual_abbreviation") or "").strip().upper()
        return bool(self.config.get("no_fdm_in_oma", True) and abbreviation == "OM-A")

    def _source_text(self, source_items: list[ContentItem]) -> str:
        chunks: list[str] = []
        for item in source_items:
            if item.type == "paragraph" and item.text:
                chunks.append(item.text)
            elif item.type == "table":
                for row in item.rows:
                    chunks.append(" ".join(row))
        return "\n".join(chunks)

    def _document_entries(self, document: DocxDocument) -> list[tuple[str, str]]:
        entries: list[tuple[str, str]] = []
        for index, paragraph in enumerate(document.paragraphs, start=1):
            self._append_entry(entries, f"body paragraph {index}", paragraph.text)
        for table_index, table in enumerate(document.tables, start=1):
            for row_index, row in enumerate(table.rows, start=1):
                for cell_index, cell in enumerate(row.cells, start=1):
                    self._append_entry(entries, f"table {table_index} row {row_index} cell {cell_index}", cell.text)
        for section_index, section in enumerate(document.sections, start=1):
            stories = [
                ("header", section.header),
                ("footer", section.footer),
                ("first page header", section.first_page_header),
                ("first page footer", section.first_page_footer),
                ("even page header", section.even_page_header),
                ("even page footer", section.even_page_footer),
            ]
            for story_name, story in stories:
                for paragraph_index, paragraph in enumerate(story.paragraphs, start=1):
                    self._append_entry(
                        entries,
                        f"section {section_index} {story_name} paragraph {paragraph_index}",
                        paragraph.text,
                    )
                for table_index, table in enumerate(story.tables, start=1):
                    for row_index, row in enumerate(table.rows, start=1):
                        for cell_index, cell in enumerate(row.cells, start=1):
                            self._append_entry(
                                entries,
                                f"section {section_index} {story_name} table {table_index} row {row_index} cell {cell_index}",
                                cell.text,
                            )
        return entries

    def _append_entry(self, entries: list[tuple[str, str]], location: str, text: str) -> None:
        cleaned = " ".join((text or "").split())
        if cleaned:
            entries.append((location, cleaned))

    def _locations(self, entries: list[tuple[str, str]], phrase: str) -> list[str]:
        pattern = re.compile(re.escape(phrase), flags=re.I)
        locations: list[str] = []
        for location, text in entries:
            if pattern.search(text):
                locations.append(f"{location}: {text[:220]}")
        return locations

    def _count(self, text: str, phrase: str) -> int:
        return len(re.findall(re.escape(phrase), text or "", flags=re.I))
