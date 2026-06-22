from __future__ import annotations

import re
from dataclasses import dataclass, field

from .models import ContentItem
from .report_generator import ReportBuilder


ZONE_NAMES = [
    "approval_letter",
    "title_page",
    "approval_page",
    "preface",
    "manual_identification_number",
    "old_master_index",
    "old_lep",
    "old_ror",
    "old_roa",
    "old_definitions",
    "old_abbreviations",
    "old_chapter_tocs",
    "body_chapters",
    "annexes",
    "conformance_tables",
    "intentionally_left_blank_pages",
    "ignored_old_front_matter_sections",
    "distribution_list",
    "record_of_temporary_revisions",
]


@dataclass
class ZoneResult:
    zones: dict[str, list[ContentItem]] = field(default_factory=lambda: {name: [] for name in ZONE_NAMES})
    transitions: list[dict[str, str | int]] = field(default_factory=list)
    ordered_body_items: list[ContentItem] = field(default_factory=list)

    def body_items(self) -> list[ContentItem]:
        return list(self.ordered_body_items)

    def zone_items(self, name: str) -> list[ContentItem]:
        return self.zones.get(name, [])


class ZoneClassifier:
    """Splits the old manual into source zones before conversion decisions are made."""

    BLANK_PATTERN = re.compile(r"^(this page is\s+)?intentionally\s+left\s+blank\.?$", re.I)
    TOC_PATTERN = re.compile(
        r"^(?:table\s+of\s+contents\s*:\s*chapter[-\s]*(\d+|[A-Za-z]+)|chapter\s*[-\u2013\u2014]?\s*(\d+|[A-Za-z]+)\s*:\s*table\s+of\s+contents)",
        re.I,
    )
    CHAPTER_PATTERN = re.compile(
        r"^chapter[-\s\u2013\u2014]*(\d+|zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|[A-Z])\b",
        re.I,
    )
    ANNEX_PATTERN = re.compile(r"^(appendix|annex|annexe)[-\s]*[A-Z0-9]+", re.I)

    SPECIAL_HEADINGS = [
        ("approval_letter", re.compile(r"^approval\s+letter$", re.I)),
        ("title_page", re.compile(r"^title\s+page$", re.I)),
        ("approval_page", re.compile(r"^(operations\s+manual.*approval|approval\s+page)$", re.I)),
        ("preface", re.compile(r"^preface$", re.I)),
        ("manual_identification_number", re.compile(r"^manual\s+identification\s+number$", re.I)),
        ("old_master_index", re.compile(r"^(master\s+index|master\s+index\s+of\s+.+)$", re.I)),
        ("old_abbreviations", re.compile(r"^(list\s+of\s+abbreviations|abbreviations)$", re.I)),
        ("old_definitions", re.compile(r"^definitions?$", re.I)),
        ("old_ror", re.compile(r"^record\s+of\s+revisions?\b", re.I)),
        ("record_of_temporary_revisions", re.compile(r"^record\s+of\s+temporary\s+revisions?\b", re.I)),
        ("old_lep", re.compile(r"^list\s+of\s+effective\s+pages\b", re.I)),
        ("old_roa", re.compile(r"^record\s+of\s+amendments?\b", re.I)),
        ("distribution_list", re.compile(r"^distribution\s+list\b", re.I)),
        ("conformance_tables", re.compile(r"^conformance\s+table", re.I)),
    ]

    def classify(self, items: list[ContentItem], report: ReportBuilder) -> ZoneResult:
        result = ZoneResult()
        active_zone = "ignored_old_front_matter_sections"
        in_body = False

        for item in items:
            text = self._clean(item.text)
            if item.type == "paragraph":
                if self._is_blank_marker(text):
                    self._add(result, "intentionally_left_blank_pages", item)
                    if active_zone in {"body_chapters", "annexes"}:
                        self._add(result, active_zone, item)
                    continue

                if self._is_chapter_toc_start(text):
                    active_zone = "old_chapter_tocs"
                    self._transition(result, active_zone, item)
                    self._add(result, active_zone, item)
                    continue

                if self._is_actual_chapter_heading(item, text):
                    active_zone = "body_chapters"
                    in_body = True
                    self._transition(result, active_zone, item)
                    self._add(result, active_zone, item)
                    continue

                if in_body and self._is_actual_annex_heading(item, text):
                    active_zone = "annexes"
                    self._transition(result, active_zone, item)
                    self._add(result, active_zone, item)
                    continue

                special_zone = self._special_zone(item, text)
                if special_zone:
                    active_zone = special_zone
                    self._transition(result, active_zone, item)
                    self._add(result, active_zone, item)
                    continue

                if active_zone == "old_chapter_tocs":
                    if self._looks_like_toc_row(item):
                        self._add(result, active_zone, item)
                        continue
                    active_zone = "body_chapters"
                    in_body = True
                    self._transition(result, active_zone, item)

            if active_zone == "old_chapter_tocs" and item.type == "paragraph" and self._looks_like_toc_row(item):
                self._add(result, active_zone, item)
                continue
            if active_zone == "old_chapter_tocs" and item.type == "paragraph" and not self._looks_like_toc_row(item):
                active_zone = "body_chapters" if in_body else "ignored_old_front_matter_sections"

            self._add(result, active_zone, item)

        self._report(result, report)
        return result

    def _add(self, result: ZoneResult, zone: str, item: ContentItem) -> None:
        item.metadata["zone"] = zone
        result.zones.setdefault(zone, []).append(item)
        if zone in {"body_chapters", "annexes"}:
            result.ordered_body_items.append(item)

    def _transition(self, result: ZoneResult, zone: str, item: ContentItem) -> None:
        result.transitions.append(
            {
                "zone": zone,
                "source_index": int(item.metadata.get("source_index", -1)),
                "sample": item.sample(),
            }
        )

    def _special_zone(self, item: ContentItem, text: str) -> str:
        style = (item.style_name or "").strip().lower()
        if style.startswith("toc"):
            return ""
        top_level = style in {"heading 1", "center heading 1"} or bool(item.metadata.get("all_caps"))
        if not top_level:
            return ""
        for zone, pattern in self.SPECIAL_HEADINGS:
            if pattern.search(text):
                return zone
        return ""

    def _is_actual_chapter_heading(self, item: ContentItem, text: str) -> bool:
        if not self.CHAPTER_PATTERN.match(text):
            return False
        if self._is_chapter_toc_start(text):
            return False
        style = (item.style_name or "").lower()
        if style.startswith("toc"):
            return False
        return (
            style.startswith("heading")
            or style == "chapter heading"
            or text.startswith("CHAPTER")
            or bool(item.metadata.get("all_caps"))
        )

    def _is_actual_annex_heading(self, item: ContentItem, text: str) -> bool:
        if not self.ANNEX_PATTERN.match(text):
            return False
        style = (item.style_name or "").lower()
        if style.startswith("toc"):
            return False
        return style.startswith("heading") or text.startswith(("ANNEX", "ANNEXE", "APPENDIX"))

    def _is_chapter_toc_start(self, text: str) -> bool:
        return bool(self.TOC_PATTERN.match(text))

    def _looks_like_toc_row(self, item: ContentItem) -> bool:
        style = (item.style_name or "").lower()
        text = self._clean(item.text)
        if style.startswith("toc"):
            return True
        if text in {"", "----------xxx----------"}:
            return True
        if style in {"plain text", "body text indent", "normal"}:
            letters = [char for char in text if char.isalpha()]
            mostly_upper = bool(letters) and sum(1 for char in letters if char.isupper()) / len(letters) > 0.75
            if mostly_upper and len(text.split()) <= 12:
                return True
        return bool(re.match(r"^(para|chap)\s+description\b", text, flags=re.I))

    def _is_blank_marker(self, text: str) -> bool:
        stacked = " ".join(text.split())
        return bool(self.BLANK_PATTERN.match(stacked))

    def _report(self, result: ZoneResult, report: ReportBuilder) -> None:
        zone_counts = {
            zone: {
                "items": len(items),
                "paragraphs": sum(1 for item in items if item.type == "paragraph"),
                "tables": sum(1 for item in items if item.type == "table"),
                "images": sum(1 for item in items if item.type == "image"),
            }
            for zone, items in result.zones.items()
        }
        report.data["zone_extraction"] = {
            "zones": zone_counts,
            "transitions": result.transitions[:80],
            "body_source": "zone_based",
        }

    @staticmethod
    def _clean(text: str) -> str:
        return " ".join((text or "").replace("\xa0", " ").split()).strip()
