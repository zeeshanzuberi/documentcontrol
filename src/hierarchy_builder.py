from __future__ import annotations

import re

from .models import ContentItem, DetectionResult
from .report_generator import ReportBuilder


FRONT_MATTER_HIERARCHY = [
    "APPROVAL LETTER",
    "TITLE PAGE",
    "APPROVAL PAGE",
    "PREFACE",
    "MANUAL IDENTIFICATION NUMBER",
    "MASTER INDEX",
    "LIST OF EFFECTIVE PAGES",
    "RECORD OF REVISIONS",
    "RECORD OF AMENDMENTS",
    "DEFINITIONS",
    "ABBREVIATIONS",
]


class HierarchyBuilder:
    """Builds the intended section hierarchy from generated front matter and source chapters."""

    CHAPTER_RE = re.compile(r"^chapter[-\s\u2013\u2014]*(\d+)\b\s*:?\s*(.*)", re.I)
    CHAPTER_ZERO_RE = re.compile(r"\badmin(?:istration)?\s*&?\s*control\s+of\s+operations\s+manual\b", re.I)

    def build(
        self,
        decisions: list[tuple[ContentItem, DetectionResult]],
        include_conformance: bool,
        report: ReportBuilder,
    ) -> list[str]:
        hierarchy = list(FRONT_MATTER_HIERARCHY)
        seen: set[str] = set()
        for item, decision in decisions:
            text = " ".join((item.text or "").split())
            if decision.role == "chapter_heading":
                match = self.CHAPTER_RE.match(text)
                if match:
                    label = f"CHAPTER {match.group(1)}"
                elif self.CHAPTER_ZERO_RE.search(text):
                    label = "CHAPTER 0"
                else:
                    label = text.upper()
            elif decision.role == "appendix_heading":
                label = text.upper()
            else:
                continue
            if label not in seen:
                seen.add(label)
                hierarchy.append(label)
        if include_conformance:
            hierarchy.append("CONFORMANCE TABLE")
        report.data["final_hierarchy"] = hierarchy
        if not any(item.startswith("CHAPTER 0") for item in hierarchy):
            report.add_warning("Hierarchy audit did not detect Chapter 0 in the body chapter zone.")
        if not any(item.startswith("CHAPTER 1") for item in hierarchy):
            report.add_warning("Hierarchy audit did not detect Chapter 1 in the body chapter zone.")
        return hierarchy
