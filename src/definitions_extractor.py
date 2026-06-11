from __future__ import annotations

import re

from .models import ContentItem, ExtractedSection


class DefinitionsExtractor:
    """Finds definitions/glossary content in the source manual without rewriting it."""

    HEADING_PATTERNS = [
        r"^definitions?$",
        r"^terms\s+and\s+definitions$",
        r"^glossary$",
    ]

    STOP_PATTERNS = [
        r"^abbreviations?$",
        r"^acronyms?$",
        r"^list\s+of\s+abbreviations$",
        r"^conformance\s+table",
        r"^compliance\s+(matrix|table)",
        r"^chapter\s+",
        r"^appendix\s+",
        r"^annex\s+",
    ]

    def extract(self, items: list[ContentItem]) -> ExtractedSection:
        start = self._find_heading(items, self.HEADING_PATTERNS)
        if start is None:
            return ExtractedSection("definitions", "missing", warning="No definitions section detected in source manual.")
        end = self._find_next_stop(items, start + 1)
        section_items = items[start + 1 : end]
        source_indices = {int(item.metadata.get("source_index", -1)) for item in [items[start], *section_items]}
        source_indices.discard(-1)
        return ExtractedSection(
            "definitions",
            "found",
            heading=items[start].text,
            items=[item for item in section_items if item.type != "page_break"],
            source_indices=source_indices,
        )

    def _find_heading(self, items: list[ContentItem], patterns: list[str]) -> int | None:
        for index, item in enumerate(items):
            if item.type != "paragraph":
                continue
            text = self._clean(item.text)
            if any(re.match(pattern, text, flags=re.I) for pattern in patterns):
                return index
        return None

    def _find_next_stop(self, items: list[ContentItem], start: int) -> int:
        for index in range(start, len(items)):
            item = items[index]
            if item.type != "paragraph":
                continue
            text = self._clean(item.text)
            if any(re.match(pattern, text, flags=re.I) for pattern in self.STOP_PATTERNS):
                return index
            if item.style_name.lower().startswith("heading ") and index > start:
                return index
        return len(items)

    @staticmethod
    def _clean(text: str) -> str:
        return " ".join((text or "").split()).strip()
