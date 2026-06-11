from __future__ import annotations

from .models import ContentItem
from .numbering_detector import NumberingDetector
from .report_generator import ReportBuilder


class ContentCleaner:
    """Conservatively removes old cover/control pages while keeping manual body content."""

    def __init__(self, detector: NumberingDetector):
        self.detector = detector

    def clean(self, items: list[ContentItem], report: ReportBuilder) -> list[ContentItem]:
        if not items:
            report.add_warning("No source content was extracted from the old manual.")
            return []

        start_index = self._find_body_start(items)
        if start_index == 0:
            return items

        skipped = items[:start_index]
        samples = [item.sample() for item in skipped if item.sample()]
        pages = sorted({item.page_number for item in skipped if item.page_number is not None})
        report.record_skipped(samples, pages)
        if start_index >= len(items):
            report.add_warning("Only old front-matter-like content was detected; nothing was removed to avoid data loss.")
            return items
        return items[start_index:]

    def _find_body_start(self, items: list[ContentItem]) -> int:
        for index, item in enumerate(items):
            if item.type != "paragraph":
                continue
            if self.detector.is_body_start(item):
                return index

        # If no strong body marker exists, skip only consecutive obvious front matter.
        index = 0
        while index < len(items):
            item = items[index]
            if item.type == "paragraph" and self.detector.is_front_matter_noise(item):
                index += 1
                continue
            break
        return min(index, len(items) - 1)
