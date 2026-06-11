from __future__ import annotations

import json
import re
from pathlib import Path

from docx.enum.section import WD_SECTION
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from .models import DetectionResult
from .report_generator import ReportBuilder


NUMBER_WORDS = {
    "zero": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
}


class SectionBreakManager:
    """Adds controlled manual section breaks for chapters and appendices."""

    def __init__(self, config_path: str | Path = "config/manual_sections.json"):
        self.config = json.loads(Path(config_path).read_text(encoding="utf-8"))

    def should_start_section(self, decision: DetectionResult) -> bool:
        return decision.role in {"chapter_heading", "appendix_heading"}

    def start_manual_section(self, document, text: str, decision: DetectionResult, report: ReportBuilder) -> dict[str, str]:
        prefix = self.prefix_for(text, decision)
        section = document.add_section(WD_SECTION.NEW_PAGE)
        self.restart_page_numbering(section)
        report.increment("section_breaks_inserted")
        if decision.role == "chapter_heading":
            report.increment("chapters_detected")
        elif decision.role == "appendix_heading":
            report.increment("appendices_detected")
        return {
            "section_index": len(document.sections) - 1,
            "prefix": prefix,
            "title": text,
            "role": decision.role,
        }

    def restart_page_numbering(self, section) -> None:
        sect_pr = section._sectPr
        pg_num = sect_pr.find(qn("w:pgNumType"))
        if pg_num is None:
            pg_num = OxmlElement("w:pgNumType")
            sect_pr.append(pg_num)
        pg_num.set(qn("w:start"), "1")

    def prefix_for(self, text: str, decision: DetectionResult) -> str:
        cleaned = " ".join((text or "").replace("\u2013", "-").split())
        if decision.role == "appendix_heading":
            match = re.search(r"\b(?:appendix|annex)\s+([A-Z0-9]+)", cleaned, re.I)
            return match.group(1).upper() if match else "A"
        match = re.search(r"\bchapter\s*[-:]?\s*([0-9]+|[A-Za-z]+)", cleaned, re.I)
        if match:
            value = match.group(1).lower()
            return NUMBER_WORDS.get(value, value.upper())
        numeric = re.match(r"^(\d+)(?:\.\d+)*\b", cleaned)
        if numeric:
            return numeric.group(1)
        return "0"
