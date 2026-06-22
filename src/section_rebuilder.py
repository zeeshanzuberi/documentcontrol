from __future__ import annotations

from dataclasses import dataclass, field

from .models import ContentItem, DetectionResult
from .report_generator import ReportBuilder
from .section_break_manager import SectionBreakManager


@dataclass
class RebuildSection:
    """A rebuild unit inserted as one manual section instead of one long stream."""

    kind: str
    title: str
    prefix: str
    role: str
    decisions: list[tuple[ContentItem, DetectionResult]] = field(default_factory=list)


class SectionRebuilder:
    """Groups body content into chapter/annex sections before DOCX construction."""

    SECTION_ROLES = {"chapter_heading", "appendix_heading"}

    def __init__(self, section_manager: SectionBreakManager):
        self.section_manager = section_manager

    def build(
        self,
        decisions: list[tuple[ContentItem, DetectionResult]],
        report: ReportBuilder,
    ) -> list[RebuildSection]:
        sections: list[RebuildSection] = []
        current: RebuildSection | None = None

        for item, decision in decisions:
            if item.type == "paragraph" and decision.role in self.SECTION_ROLES:
                current = self._new_section(item, decision)
                sections.append(current)
                continue

            if current is None:
                current = RebuildSection(
                    kind="body_preamble",
                    title="Body Content Before First Chapter",
                    prefix="",
                    role="body_preamble",
                )
                sections.append(current)
                report.add_warning(
                    "Body content was found before the first detected chapter/annex section and was rebuilt as a preamble section."
                )
            current.decisions.append((item, decision))

        self._report(sections, report)
        return sections

    def _new_section(self, item: ContentItem, decision: DetectionResult) -> RebuildSection:
        kind = "chapter" if decision.role == "chapter_heading" else "annex"
        title = " ".join((item.text or "").split())
        prefix = self.section_manager.prefix_for(title, decision)
        return RebuildSection(
            kind=kind,
            title=title,
            prefix=prefix,
            role=decision.role,
            decisions=[(item, decision)],
        )

    def _report(self, sections: list[RebuildSection], report: ReportBuilder) -> None:
        report.data["section_rebuild"] = {
            "mode": "section_by_section",
            "section_count": len(sections),
            "sections": [
                {
                    "kind": section.kind,
                    "prefix": section.prefix,
                    "title": section.title,
                    "items": len(section.decisions),
                }
                for section in sections
            ],
        }
