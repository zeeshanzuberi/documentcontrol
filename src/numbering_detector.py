from __future__ import annotations

import json
import re
from pathlib import Path

from .models import ContentItem, DetectionResult


ROMAN_VALUES = {"i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x"}


class NumberingDetector:
    """Classifies headings and paragraph numbering without changing source text."""

    DEFAULT_MISC_PATTERNS = {
        "bullet": r"^([•\-*])\s+(?P<body>\S.*)$",
        "note": r"^(note|NOTE)\s*:",
        "caution": r"^(caution|CAUTION)\s*:",
        "warning": r"^(warning|WARNING)\s*:",
    }

    def __init__(self, rules_path: str | Path = "config/numbering_rules.json"):
        self.rules_path = Path(rules_path)
        self.rules = json.loads(self.rules_path.read_text(encoding="utf-8"))
        self.new_edition_rules = self._load_new_edition_rules()
        legacy_patterns = self.rules.get("patterns", {})
        self.heading_patterns = self._compile_patterns(
            self.rules.get("heading_patterns") or self._legacy_heading_patterns(legacy_patterns),
            flags=re.I,
        )
        self.paragraph_patterns = self._compile_patterns(
            self.rules.get("paragraph_numbering_patterns") or self._legacy_paragraph_patterns(legacy_patterns),
            flags=re.I,
        )
        self.misc_patterns = self._compile_patterns({**self.DEFAULT_MISC_PATTERNS, **legacy_patterns}, flags=re.I)
        self.classification_rules = self.rules.get("classification_rules", {})
        self.max_heading_characters = int(self.rules.get("max_heading_characters", 140))
        self.max_heading_words = int(self.rules.get("max_heading_words", 18))
        self.sentence_endings = tuple(self.rules.get("heading_sentence_endings", [".", ";"]))

    def detect(self, item: ContentItem) -> DetectionResult:
        text = self._clean(item.text)
        if not text:
            return DetectionResult("normal", "normal", 1.0, body_text="")

        if self.classification_rules.get("do_not_classify_table_text_as_heading", True) and item.metadata.get("inside_table"):
            return DetectionResult("body", "body", 0.9, body_text=text, reason="Table cell text")

        source_role = self._role_from_source_style(item.style_name, item)
        if source_role == "chapter_heading" and re.search(r"\btable\s+of\s+contents\b", text, flags=re.I):
            return DetectionResult(
                "body",
                "body",
                0.8,
                body_text=text,
                reason="Chapter TOC heading preserved as non-body-heading text",
                warning=f"Chapter table-of-contents heading skipped as body chapter heading: {text[:120]}",
            )
        if source_role == "appendix_heading" and re.match(r"^annexes[-\s]*\d+\b", text, flags=re.I):
            return DetectionResult(
                "body",
                "body",
                0.8,
                body_text=text,
                reason="Annex list heading preserved as non-body-heading text",
                warning=f"Annex list heading skipped as appendix heading: {text[:120]}",
            )
        if source_role == "heading_1" and re.search(r"\badmin(?:istration)?\s*&?\s*control\s+of\s+operations\s+manual\b", text, flags=re.I):
            return DetectionResult(
                "chapter_heading",
                "chapter_heading",
                0.94,
                body_text=text,
                reason="OM-A Chapter 0 title inferred from top-level source heading",
            )
        numeric_heading = re.match(r"^(?P<marker>\d+(?:\.\d+){0,6})\s+(?P<body>\S.*)$", text)
        if numeric_heading:
            return self._numbered_section_decision(
                numeric_heading.group("marker"),
                numeric_heading.group("body"),
                text,
                item,
            )

        chapter = self._heading_match("chapter_heading", text)
        if chapter and self._looks_like_major_heading(item, text, "chapter"):
            return DetectionResult("chapter_heading", "chapter_heading", 0.98, body_text=text, reason="Chapter heading pattern")
        if chapter:
            return DetectionResult(
                "body",
                "body",
                0.7,
                body_text=text,
                reason="Chapter-like line lacked a strong heading signal",
                warning=f"Ambiguous chapter heading-like line preserved as body text: {text[:120]}",
            )

        appendix = self._heading_match("appendix_heading", text)
        if appendix and self._looks_like_major_heading(item, text, "appendix"):
            return DetectionResult("appendix_heading", "appendix_heading", 0.98, body_text=text, reason="Appendix heading pattern")
        if appendix:
            return DetectionResult(
                "body",
                "body",
                0.7,
                body_text=text,
                reason="Appendix-like line lacked a strong heading signal",
                warning=f"Ambiguous appendix heading-like line preserved as body text: {text[:120]}",
            )

        explicit_major_heading = (
            source_role in {"heading_1", "heading_2", "heading_3"}
            and (
                self._heading_match("chapter_heading", text)
                or self._heading_match("appendix_heading", text)
            )
        )
        if source_role and not explicit_major_heading:
            return DetectionResult(
                role=source_role,
                style_key=source_role,
                confidence=0.96,
                body_text=text,
                reason=f"Source style '{item.style_name}' mapped directly",
            )

        lowered = text.lower()
        if self._misc("warning").match(text):
            return DetectionResult("warning", "warning", 0.95, body_text=text, reason="Warning label")
        if self._misc("caution").match(text):
            return DetectionResult("caution", "caution", 0.95, body_text=text, reason="Caution label")
        if self._misc("note").match(text):
            return DetectionResult("note", "note", 0.95, body_text=text, reason="Note label")
        if lowered.startswith(("reference:", "references:", "regulatory reference")):
            return DetectionResult("reference", "reference", 0.9, body_text=text, reason="Reference label")
        if self._looks_like_definition(text):
            return DetectionResult("definition", "definition", 0.8, body_text=text, reason="Definition pattern")

        if self._heading_match("section_heading", text) and (
            self._looks_like_heading_text(text, item) or len(text.split()) <= 8
        ):
            return DetectionResult("section_heading", "section_heading", 0.88, body_text=text, reason="Section heading pattern")

        list_result = self._detect_list(text)
        if list_result:
            return list_result

        bullet = self._misc("bullet").match(text)
        if bullet or item.style_name.lower().startswith("list bullet"):
            body = bullet.group("body") if bullet and "body" in bullet.groupdict() else text
            marker = text[0] if bullet else ""
            return DetectionResult("bullet", "bullet", 0.9, marker=marker, body_text=body, reason="Bullet list pattern")

        if self._looks_like_heading_text(text, item) and item.metadata.get("bold"):
            return DetectionResult("heading_1", "heading_1", 0.82, body_text=text, reason="Bold short heading-like paragraph")

        return DetectionResult("body", "body", 0.9, body_text=text, reason="Default body text")

    def is_body_start(self, item: ContentItem) -> bool:
        text = self._clean(item.text).lower()
        if not text:
            return False
        keep_headings = tuple(self.rules.get("body_start_headings", []))
        if text.startswith(keep_headings):
            return True
        detection = self.detect(item)
        return detection.role in {"chapter_heading", "appendix_heading", "section_heading", "heading_1", "heading_2"}

    def is_front_matter_noise(self, item: ContentItem) -> bool:
        text = self._clean(item.text).lower()
        if not text:
            return True
        keywords = self.rules.get("front_matter_keywords", [])
        if any(keyword in text for keyword in keywords):
            return True
        if text in {"intentionally left blank", "this page intentionally left blank"}:
            return True
        if re.fullmatch(r"page\s+\d+(\s+of\s+\d+)?", text):
            return True
        return False

    def _numbered_section_decision(
        self,
        marker: str,
        body: str,
        original_text: str,
        item: ContentItem,
    ) -> DetectionResult:
        role = self._new_edition_role_for_marker(marker)
        if role.startswith("controlled_level_"):
            return DetectionResult(
                role,
                role,
                0.91,
                marker=marker,
                body_text=body,
                reason="New edition controlled paragraph mapping for third-level-or-deeper numbered content",
            )

        allow_sentence = role == "heading_1"
        if self._looks_like_heading_text(body, item, allow_sentence=allow_sentence):
            confidence = 0.94 if role == "heading_2" else 0.88
            return DetectionResult(role, role, confidence, marker=marker, body_text=body, reason="New edition numbered section mapping")

        warning = f"Ambiguous numbered section/list preserved as body text: {original_text[:120]}"
        return DetectionResult(
            "body",
            "body",
            0.7,
            body_text=original_text,
            reason="Numbering pattern matched a new edition section level but context was weak",
            warning=warning,
        )

    def _detect_list(self, text: str) -> DetectionResult | None:
        upper = re.match(r"^(?P<marker>[A-Z])\.\s+(?P<body>\S.*)$", text)
        if upper and self._paragraph_match("level_1", text):
            return DetectionResult(
                "paragraph_number_level_1",
                "paragraph_number_level_1",
                0.92,
                marker=upper.group("marker") + ".",
                body_text=upper.group("body"),
                reason="Uppercase alpha paragraph numbering",
            )

        numeric = re.match(r"^(?P<marker>\d+)[.)]\s+(?P<body>\S.*)$", text)
        if numeric and self._paragraph_match("level_2", text):
            return DetectionResult(
                "paragraph_number_level_2",
                "paragraph_number_level_2",
                0.9,
                marker=numeric.group("marker") + ".",
                body_text=numeric.group("body"),
                reason="Numeric paragraph numbering",
            )

        roman = re.match(r"^(?P<marker>i{1,3}|iv|v|vi{0,3}|ix|x)\.\s+(?P<body>\S.*)$", text, flags=re.I)
        if roman and roman.group("marker").lower() in ROMAN_VALUES and self._paragraph_match("level_4", text):
            return DetectionResult(
                "paragraph_number_level_4",
                "paragraph_number_level_4",
                0.9,
                marker=roman.group("marker") + ".",
                body_text=roman.group("body"),
                reason="Roman paragraph numbering",
            )

        lower = re.match(r"^(?P<marker>[a-z])\.\s+(?P<body>\S.*)$", text)
        if lower and lower.group("marker") not in ROMAN_VALUES and self._paragraph_match("level_3", text):
            return DetectionResult(
                "paragraph_number_level_3",
                "paragraph_number_level_3",
                0.9,
                marker=lower.group("marker") + ".",
                body_text=lower.group("body"),
                reason="Lowercase alpha paragraph numbering",
            )

        lower_paren = re.match(r"^(?P<marker>[a-z])\)\s+(?P<body>\S.*)$", text)
        if lower_paren and self._paragraph_match("level_5", text):
            return DetectionResult(
                "paragraph_number_level_5",
                "paragraph_number_level_5",
                0.9,
                marker=lower_paren.group("marker") + ")",
                body_text=lower_paren.group("body"),
                reason="Lowercase alpha parenthesized paragraph numbering",
            )
        return None

    def _role_from_source_style(self, style_name: str, item: ContentItem | None = None) -> str:
        normalized = (style_name or "").strip().lower()
        if not normalized:
            return ""
        body_zone = (item.metadata.get("zone") if item else "") in {"body_chapters", "annexes"}
        exact = {
            "chapter heading": "chapter_heading",
            "appendix heading": "appendix_heading",
            "annex heading": "appendix_heading",
            "section heading": "section_heading",
            "paragraph level 1": "paragraph_number_level_1",
            "paragraph level 2": "paragraph_number_level_2",
            "paragraph level 3": "paragraph_number_level_3",
            "paragraph level 4": "paragraph_number_level_4",
            "paragraph level 5": "paragraph_number_level_5",
            "caption": "caption",
        }
        if normalized in exact:
            return exact[normalized]
        if normalized.startswith("heading "):
            parts = normalized.split()
            if len(parts) >= 2 and parts[1].isdigit():
                level = min(max(int(parts[1]), 1), 6)
                if body_zone and level >= 3:
                    return self._controlled_role_for_old_heading_level(level)
                return f"heading_{level}"
        return ""

    def _new_edition_role_for_marker(self, marker: str) -> str:
        depth = len([part for part in marker.split(".") if part != ""])
        if depth <= 2:
            return "heading_1"
        if depth == 3:
            return "heading_2"
        return self._controlled_role_for_new_depth(depth)

    def _controlled_role_for_new_depth(self, depth: int) -> str:
        if depth <= 4:
            return "controlled_level_3"
        if depth == 5:
            return "controlled_level_4"
        if depth == 6:
            return "controlled_level_5"
        return "controlled_level_6"

    def _controlled_role_for_old_heading_level(self, level: int) -> str:
        if level <= 3:
            return "controlled_level_3"
        if level == 4:
            return "controlled_level_4"
        if level == 5:
            return "controlled_level_5"
        return "controlled_level_6"

    def _looks_like_heading_text(self, text: str, item: ContentItem, allow_sentence: bool = True) -> bool:
        cleaned = self._clean(text)
        if not cleaned:
            return False
        words = cleaned.split()
        if len(cleaned) > self.max_heading_characters or len(words) > self.max_heading_words:
            return False
        if self.classification_rules.get("do_not_classify_long_sentence_as_heading", True):
            if not allow_sentence and cleaned.endswith(self.sentence_endings):
                return False
            if len(words) > 10 and cleaned.endswith((".", ";", ",")):
                return False
        if cleaned.count(".") > 1 and not re.match(r"^\d+(\.\d+)+\s+", cleaned):
            return False
        if item.metadata.get("bold") or item.metadata.get("all_caps"):
            return True
        letters = [char for char in cleaned if char.isalpha()]
        if letters and sum(1 for char in letters if char.isupper()) / len(letters) > 0.65:
            return True
        title_words = sum(1 for word in words if word[:1].isupper())
        return bool(words and title_words / len(words) >= 0.55 and not cleaned.endswith(self.sentence_endings))

    def _looks_like_major_heading(self, item: ContentItem, text: str, kind: str) -> bool:
        style = (item.style_name or "").strip().lower()
        upper_text = text.upper()
        if style.startswith("toc"):
            return False
        if style.startswith("heading"):
            return True
        if item.metadata.get("bold") or item.metadata.get("all_caps"):
            return True
        if kind == "chapter" and text.startswith("CHAPTER"):
            return True
        if kind == "appendix" and text.startswith(("ANNEX", "ANNEXE", "APPENDIX", "Appendix")):
            return True
        return False

    def _looks_like_definition(self, text: str) -> bool:
        if ":" not in text:
            return False
        label, body = text.split(":", 1)
        return 1 <= len(label.split()) <= 8 and bool(body.strip())

    def _heading_match(self, role: str, text: str) -> bool:
        pattern = self.heading_patterns.get(role)
        return bool(pattern.match(text)) if pattern else False

    def _paragraph_match(self, role: str, text: str) -> bool:
        pattern = self.paragraph_patterns.get(role)
        return bool(pattern.match(text)) if pattern else False

    def _misc(self, role: str):
        return self.misc_patterns.get(role) or re.compile(r"a^")

    def _compile_patterns(self, patterns: dict[str, str], flags: int = 0) -> dict[str, re.Pattern[str]]:
        compiled: dict[str, re.Pattern[str]] = {}
        for name, pattern in patterns.items():
            try:
                compiled[name] = re.compile(pattern, flags=flags)
            except re.error:
                continue
        return compiled

    def _load_new_edition_rules(self) -> dict:
        path = self.rules_path.with_name("new_edition_style_map.json")
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def _legacy_heading_patterns(self, legacy: dict[str, str]) -> dict[str, str]:
        return {
            "chapter_heading": legacy.get("chapter", r"^(Chapter|CHAPTER)\s+(\d+|[A-Za-z]+)"),
            "appendix_heading": legacy.get("appendix", r"^(Appendix|APPENDIX)\s+[A-Z]"),
            "section_heading": legacy.get("section", r"^(Section|SECTION)\s+[0-9A-Za-z]+"),
            "heading_1": r"^\d+\s+[^.].+",
            "heading_2": r"^\d+\.\d+\s+.+",
            "heading_3": r"^\d+\.\d+\.\d+\s+.+",
            "heading_4": r"^\d+\.\d+\.\d+\.\d+\s+.+",
            "heading_5": r"^\d+\.\d+\.\d+\.\d+\.\d+\s+.+",
            "heading_6": r"^\d+\.\d+\.\d+\.\d+\.\d+\.\d+\s+.+",
        }

    def _legacy_paragraph_patterns(self, legacy: dict[str, str]) -> dict[str, str]:
        return {
            "level_1": legacy.get("upper_alpha_list", r"^[A-Z]\.\s+.+"),
            "level_2": legacy.get("numeric_list", r"^\d+[\.)]\s+.+"),
            "level_3": legacy.get("lower_alpha_list", r"^[a-z]\.\s+.+"),
            "level_4": legacy.get("roman_list", r"^(i|ii|iii|iv|v|vi|vii|viii|ix|x)\.\s+.+"),
            "level_5": legacy.get("lower_alpha_paren", r"^[a-z]\)\s+.+"),
        }

    @staticmethod
    def _clean(text: str) -> str:
        return " ".join((text or "").replace("\xa0", " ").split())
