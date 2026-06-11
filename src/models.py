from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ContentItem:
    """A source-document block that can be transferred into the template."""

    type: str
    text: str = ""
    style_name: str = ""
    rows: list[list[str]] = field(default_factory=list)
    image_bytes: bytes | None = None
    image_ext: str = ".png"
    page_number: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def sample(self, limit: int = 160) -> str:
        if self.type == "table":
            text = " | ".join(" / ".join(row) for row in self.rows[:2])
        elif self.type == "image":
            text = f"Image {self.image_ext}"
        else:
            text = self.text
        text = " ".join(text.split())
        return text[:limit] + ("..." if len(text) > limit else "")


@dataclass
class DetectionResult:
    """How a content block should be mapped into the template."""

    role: str
    style_key: str
    confidence: float
    marker: str = ""
    body_text: str = ""
    reason: str = ""
    warning: str = ""

    @property
    def is_heading(self) -> bool:
        return self.role in {
            "chapter_heading",
            "section_heading",
            "appendix_heading",
            "heading_1",
            "heading_2",
            "heading_3",
            "heading_4",
            "heading_5",
            "heading_6",
        }

    @property
    def is_numbered_paragraph(self) -> bool:
        return self.role.startswith("paragraph_number_level_")


@dataclass
class ExtractedSection:
    """A special source section extracted for generated front matter."""

    name: str
    status: str
    heading: str = ""
    items: list[ContentItem] = field(default_factory=list)
    source_indices: set[int] = field(default_factory=set)
    warning: str = ""

    @property
    def found(self) -> bool:
        return self.status == "found"
