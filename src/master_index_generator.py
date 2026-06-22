from __future__ import annotations

import json
from pathlib import Path

from .models import ContentItem, DetectionResult
from .report_generator import ReportBuilder
from .section_break_manager import SectionBreakManager


class MasterIndexGenerator:
    """Builds a best-effort Master Index from detected source-manual headings."""

    INDEX_ROLES = {
        "chapter_heading",
        "appendix_heading",
        "heading_1",
        "heading_2",
    }

    def __init__(self, config_path: str | Path = "config/generated_tables.json"):
        self.config = json.loads(Path(config_path).read_text(encoding="utf-8")).get("master_index", {})
        self.section_manager = SectionBreakManager()

    def generate(
        self,
        decisions: list[tuple[ContentItem, DetectionResult]],
        metadata: dict[str, str],
        report: ReportBuilder,
    ) -> list[list[str]]:
        columns = self.config.get("columns", ["Section", "Description", "Page"])
        rows = [columns]
        seen: set[tuple[str, str]] = set()
        current_prefix = "0"

        for item, decision in decisions:
            if item.type != "paragraph" or decision.role not in self.INDEX_ROLES:
                continue
            text = " ".join((item.text or "").split())
            if not text:
                continue
            if decision.role in {"chapter_heading", "appendix_heading"}:
                current_prefix = self.section_manager.prefix_for(text, decision)
                section = current_prefix
                page = f"{current_prefix}-1"
            else:
                section = decision.marker or self._leading_number(text) or current_prefix
                page_prefix = section.split(".", 1)[0] if section else current_prefix
                page = f"{page_prefix}-1"

            title = decision.body_text if decision.marker and decision.body_text else text
            key = (section, title)
            if key in seen:
                continue
            seen.add(key)
            rows.append([section, title, page])

        if len(rows) == 1:
            rows.append([
                metadata.get("manual_abbreviation", "Manual"),
                "No source headings detected. Review source manual structure.",
                "",
            ])
            report.add_warning("Master Index generation found no source headings; review source manual heading styles.")
        report.data["generated"]["master_index"] = "generated_from_source_headings"
        return rows

    def _leading_number(self, text: str) -> str:
        for index, char in enumerate(text):
            if not (char.isdigit() or char == "."):
                return text[:index].rstrip(".")
        return ""
