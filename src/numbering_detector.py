from __future__ import annotations

import json
import re
from pathlib import Path

from .models import ContentItem, DetectionResult


ROMAN_VALUES = {"i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x"}


class NumberingDetector:
    """Classifies headings and paragraph numbering without changing the text."""

    def __init__(self, rules_path: str | Path = "config/numbering_rules.json"):
        self.rules_path = Path(rules_path)
        self.rules = json.loads(self.rules_path.read_text(encoding="utf-8"))
        self.patterns = {
            name: re.compile(pattern)
            for name, pattern in self.rules.get("patterns", {}).items()
        }
        self.max_heading_characters = int(self.rules.get("max_heading_characters", 140))
        self.max_heading_words = int(self.rules.get("max_heading_words", 18))
        self.sentence_endings = tuple(self.rules.get("heading_sentence_endings", [".", ";"]))

    def detect(self, item: ContentItem) -> DetectionResult:
        text = self._clean(item.text)
        if not text:
            return DetectionResult("normal", "normal", 1.0, body_text="")

        source_role = self._role_from_source_style(item.style_name)
        if source_role:
            return DetectionResult(
                role=source_role,
                style_key=source_role,
                confidence=0.96,
                body_text=text,
                reason=f"Source style '{item.style_name}' mapped directly",
            )

        lowered = text.lower()
        if self.patterns["warning"].match(text):
            return DetectionResult("warning", "warning", 0.95, body_text=text, reason="Warning label")
        if self.patterns["caution"].match(text):
            return DetectionResult("caution", "caution", 0.95, body_text=text, reason="Caution label")
        if self.patterns["note"].match(text):
            return DetectionResult("note", "note", 0.95, body_text=text, reason="Note label")
        if lowered.startswith(("reference:", "references:", "regulatory reference")):
            return DetectionResult("reference", "reference", 0.9, body_text=text, reason="Reference label")
        if self._looks_like_definition(text):
            return DetectionResult("definition", "definition", 0.8, body_text=text, reason="Definition pattern")

        if self.patterns["chapter"].match(text) or self.patterns["chapter_dash"].match(text):
            return DetectionResult("chapter_heading", "chapter_heading", 0.98, body_text=text, reason="Chapter heading pattern")

        if self.patterns["appendix"].match(text):
            return DetectionResult("appendix_heading", "appendix_heading", 0.98, body_text=text, reason="Appendix/annex heading pattern")

        if self.patterns["section"].match(text) and self._looks_like_heading_text(text, item):
            return DetectionResult("section_heading", "section_heading", 0.88, body_text=text, reason="Section heading pattern")

        numeric_heading = self.patterns["numeric_heading"].match(text)
        if numeric_heading:
            marker = numeric_heading.group("marker")
            body = numeric_heading.group("body")
            level = marker.count(".") + 1
            role = f"heading_{min(level, 6)}"
            if "." in marker:
                confidence = 0.94 if self._looks_like_heading_text(body, item, allow_sentence=False) else 0.78
                warning = "" if confidence >= 0.85 else "Dotted heading pattern found but context is weak"
                return DetectionResult(role, role, confidence, marker=marker, body_text=body, reason="Dotted heading number", warning=warning)

            if self._looks_like_heading_text(body, item, allow_sentence=False):
                return DetectionResult("heading_1", "heading_1", 0.88, marker=marker, body_text=body, reason="Single-number heading context")

        list_result = self._detect_list(text)
        if list_result:
            return list_result

        if self.patterns["bullet"].match(text) or item.style_name.lower().startswith("list bullet"):
            match = self.patterns["bullet"].match(text)
            body = match.group("body") if match else text
            marker = text[0] if match else ""
            return DetectionResult("bullet", "bullet", 0.9, marker=marker, body_text=body, reason="Bullet list pattern")

        if self._looks_like_heading_text(text, item) and item.metadata.get("bold"):
            return DetectionResult("heading_1", "heading_1", 0.72, body_text=text, reason="Bold short heading-like paragraph", warning="Heading inferred from formatting only")

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

    def _detect_list(self, text: str) -> DetectionResult | None:
        upper = self.patterns["upper_alpha_list"].match(text)
        if upper:
            return DetectionResult(
                "paragraph_number_level_1",
                "paragraph_number_level_1",
                0.92,
                marker=upper.group("marker") + ".",
                body_text=upper.group("body"),
                reason="Uppercase alpha paragraph numbering",
            )

        numeric = self.patterns["numeric_list"].match(text)
        if numeric:
            return DetectionResult(
                "paragraph_number_level_2",
                "paragraph_number_level_2",
                0.9,
                marker=numeric.group("marker") + ".",
                body_text=numeric.group("body"),
                reason="Numeric paragraph numbering",
            )

        lower = self.patterns["lower_alpha_list"].match(text)
        if lower and lower.group("marker") not in ROMAN_VALUES:
            return DetectionResult(
                "paragraph_number_level_3",
                "paragraph_number_level_3",
                0.9,
                marker=lower.group("marker") + ".",
                body_text=lower.group("body"),
                reason="Lowercase alpha paragraph numbering",
            )

        roman = self.patterns["roman_list"].match(text)
        if roman and roman.group("marker").lower() in ROMAN_VALUES:
            return DetectionResult(
                "paragraph_number_level_4",
                "paragraph_number_level_4",
                0.9,
                marker=roman.group("marker") + ".",
                body_text=roman.group("body"),
                reason="Roman paragraph numbering",
            )

        lower_paren = self.patterns["lower_alpha_paren"].match(text)
        if lower_paren:
            return DetectionResult(
                "paragraph_number_level_5",
                "paragraph_number_level_5",
                0.9,
                marker=lower_paren.group("marker") + ")",
                body_text=lower_paren.group("body"),
                reason="Lowercase alpha parenthesized paragraph numbering",
            )
        return None

    def _role_from_source_style(self, style_name: str) -> str:
        normalized = (style_name or "").strip().lower()
        if not normalized:
            return ""
        if normalized == "chapter heading":
            return "chapter_heading"
        if normalized.startswith("heading "):
            parts = normalized.split()
            if len(parts) >= 2 and parts[1].isdigit():
                level = min(max(int(parts[1]), 1), 6)
                return f"heading_{level}"
        if normalized in {"caption"}:
            return "caption"
        return ""

    def _looks_like_heading_text(self, text: str, item: ContentItem, allow_sentence: bool = True) -> bool:
        cleaned = self._clean(text)
        if not cleaned:
            return False
        words = cleaned.split()
        if len(cleaned) > self.max_heading_characters or len(words) > self.max_heading_words:
            return False
        if not allow_sentence and cleaned.endswith(self.sentence_endings):
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

    def _looks_like_definition(self, text: str) -> bool:
        if ":" not in text:
            return False
        label, body = text.split(":", 1)
        return 1 <= len(label.split()) <= 8 and bool(body.strip())

    @staticmethod
    def _clean(text: str) -> str:
        return " ".join((text or "").replace("\xa0", " ").split())
