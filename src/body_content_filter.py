from __future__ import annotations

import re

from .models import ContentItem
from .report_generator import ReportBuilder


class BodyContentFilter:
    """Keeps only chapter/annex body blocks eligible for body heading detection."""

    REJECT_PATTERNS = [
        re.compile(r"^table\s+of\s+contents\s*:\s*chapter", re.I),
        re.compile(r"^chapter\s*[-\u2013\u2014]?\s*\d+\s*:\s*table\s+of\s+contents$", re.I),
        re.compile(r"^(para|chap)\s+description\b", re.I),
        re.compile(r"^master\s+index\b", re.I),
        re.compile(r"^list\s+of\s+annexes\b", re.I),
        re.compile(r"^annexes[-\s]*\d+\b", re.I),
        re.compile(r"^annex\s+no\s+description\b", re.I),
        re.compile(r"^distribution\s+list\b", re.I),
        re.compile(r"^record\s+of\s+(revisions?|amendments?|temporary\s+revisions?)\b", re.I),
        re.compile(r"^list\s+of\s+effective\s+pages\b", re.I),
        re.compile(r"^title\s+page$", re.I),
        re.compile(r"^approval\s+letter$", re.I),
        re.compile(r"^preface$", re.I),
        re.compile(r"^manual\s+identification\s+number$", re.I),
    ]
    TOC_STYLE_PREFIX = "toc"
    NOISE_WORDS = {"wise", "no"}

    def filter(self, items: list[ContentItem], report: ReportBuilder) -> list[ContentItem]:
        kept: list[ContentItem] = []
        rejected: list[str] = []
        for item in items:
            if self._reject(item):
                if item.sample():
                    rejected.append(item.sample())
                continue
            kept.append(item)
        if rejected:
            report.data.setdefault("zone_extraction", {}).setdefault("body_filter_rejected", [])
            report.data["zone_extraction"]["body_filter_rejected"].extend(rejected[:200])
            report.add_warning(f"Body content filter removed {len(rejected)} old front-matter/TOC/noise blocks before heading detection.")
        return kept

    def _reject(self, item: ContentItem) -> bool:
        if item.type != "paragraph":
            return False
        style = (item.style_name or "").lower()
        text = " ".join((item.text or "").split()).strip()
        if not text:
            return False
        if style.startswith(self.TOC_STYLE_PREFIX):
            return True
        if any(pattern.search(text) for pattern in self.REJECT_PATTERNS):
            return True
        if text.lower() in self.NOISE_WORDS:
            return True
        return False
