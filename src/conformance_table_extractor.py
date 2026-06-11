from __future__ import annotations

import re

from .models import ContentItem, ExtractedSection


class ConformanceTableExtractor:
    """Finds conformance/compliance table blocks in the source manual."""

    HEADING_PATTERNS = [
        r"^conformance\s+table",
        r"^compliance\s+matrix",
        r"^compliance\s+table",
        r"^regulatory\s+compliance",
        r"^cross\s+reference\s+table",
        r"^pcaa\s+compliance",
        r"^icao\s+compliance",
        r"^iosa\s+compliance",
    ]

    STOP_PATTERNS = [
        r"^chapter\s+",
        r"^appendix\s+",
        r"^annex\s+",
        r"^definitions?$",
        r"^abbreviations?$",
    ]

    def extract(self, items: list[ContentItem]) -> ExtractedSection:
        start = self._find_heading(items)
        if start is None:
            return ExtractedSection("conformance_tables", "missing", warning="No conformance/compliance tables detected in source manual.")
        end = self._find_next_stop(items, start + 1)
        section_items = items[start + 1 : end]
        source_indices = {int(item.metadata.get("source_index", -1)) for item in [items[start], *section_items]}
        source_indices.discard(-1)
        return ExtractedSection(
            "conformance_tables",
            "found",
            heading=items[start].text,
            items=[item for item in section_items if item.type != "page_break"],
            source_indices=source_indices,
        )

    def _find_heading(self, items: list[ContentItem]) -> int | None:
        for index, item in enumerate(items):
            if item.type != "paragraph":
                continue
            text = " ".join((item.text or "").split()).strip()
            if any(re.match(pattern, text, flags=re.I) for pattern in self.HEADING_PATTERNS):
                return index
        return None

    def _find_next_stop(self, items: list[ContentItem], start: int) -> int:
        for index in range(start, len(items)):
            item = items[index]
            if item.type != "paragraph":
                continue
            text = " ".join((item.text or "").split()).strip()
            if any(re.match(pattern, text, flags=re.I) for pattern in self.STOP_PATTERNS):
                return index
            if item.style_name.lower().startswith("heading ") and index > start:
                return index
        return len(items)
