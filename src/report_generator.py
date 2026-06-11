from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_COUNTS = {
    "body_paragraphs_extracted": 0,
    "total_headings": 0,
    "chapter_heading": 0,
    "heading_1": 0,
    "heading_2": 0,
    "heading_3": 0,
    "heading_4": 0,
    "heading_5": 0,
    "heading_6": 0,
    "paragraph_number_level_1": 0,
    "paragraph_number_level_2": 0,
    "paragraph_number_level_3": 0,
    "paragraph_number_level_4": 0,
    "paragraph_number_level_5": 0,
    "tables": 0,
    "tables_inserted": 0,
    "images": 0,
    "images_inserted": 0,
    "intentionally_blank_pages": 0,
    "section_breaks_inserted": 0,
    "page_breaks_inserted": 0,
    "chapters_detected": 0,
    "appendices_detected": 0,
}


class ReportBuilder:
    """Collects conversion facts without changing source content."""

    def __init__(self, template_path: str, source_path: str, metadata: dict[str, str]):
        self.data: dict[str, Any] = {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "template_path": str(template_path),
            "source_path": str(source_path),
            "metadata": metadata,
            "counts": dict(DEFAULT_COUNTS),
            "skipped_front_matter": {
                "items": 0,
                "pages": [],
                "samples": [],
            },
            "missing_styles": [],
            "missing_placeholders": [],
            "missing_bookmarks": [],
            "unreplaced_placeholders": [],
            "unmapped_content": [],
            "numbering_conflicts": [],
            "intentionally_blank_pages": [],
            "generated": {
                "lep": "not_run",
                "ror": "not_run",
                "roa": "not_run",
                "definitions": "not_run",
                "abbreviations": "not_run",
                "conformance": "not_run",
                "approval": "not_run",
                "page_numbering": "not_run",
            },
            "quality_control": [],
            "warnings": [],
            "errors": [],
            "outputs": {},
        }

    def increment(self, key: str, amount: int = 1) -> None:
        self.data["counts"][key] = self.data["counts"].get(key, 0) + amount

    def add_warning(self, message: str) -> None:
        if message and message not in self.data["warnings"]:
            self.data["warnings"].append(message)

    def add_error(self, message: str) -> None:
        if message and message not in self.data["errors"]:
            self.data["errors"].append(message)

    def add_missing_style(self, style_name: str, role: str) -> None:
        item = {"style": style_name, "role": role}
        if item not in self.data["missing_styles"]:
            self.data["missing_styles"].append(item)

    def add_missing_placeholder(self, placeholder: str) -> None:
        if placeholder not in self.data["missing_placeholders"]:
            self.data["missing_placeholders"].append(placeholder)

    def add_missing_bookmark(self, bookmark: str) -> None:
        if bookmark not in self.data["missing_bookmarks"]:
            self.data["missing_bookmarks"].append(bookmark)

    def add_unreplaced_placeholder(self, placeholder: str) -> None:
        if placeholder not in self.data["unreplaced_placeholders"]:
            self.data["unreplaced_placeholders"].append(placeholder)

    def add_unmapped(self, sample: str, reason: str) -> None:
        item = {"sample": sample, "reason": reason}
        if item not in self.data["unmapped_content"]:
            self.data["unmapped_content"].append(item)

    def add_numbering_conflict(self, sample: str, reason: str) -> None:
        item = {"sample": sample, "reason": reason}
        if item not in self.data["numbering_conflicts"]:
            self.data["numbering_conflicts"].append(item)

    def record_skipped(self, samples: list[str], pages: list[int] | None = None) -> None:
        self.data["skipped_front_matter"]["items"] += len(samples)
        self.data["skipped_front_matter"]["samples"].extend(samples[:25])
        if pages:
            current = set(self.data["skipped_front_matter"]["pages"])
            current.update(pages)
            self.data["skipped_front_matter"]["pages"] = sorted(current)

    def set_output(self, key: str, value: str) -> None:
        self.data["outputs"][key] = value

    def add_quality_check(self, item: str, status: str, detail: str = "") -> None:
        row = {"item": item, "status": status, "detail": detail}
        self.data["quality_control"].append(row)

    def to_dict(self) -> dict[str, Any]:
        return self.data

    def write_json(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.data, indent=2), encoding="utf-8")

    def write_text(self, path: str | Path) -> None:
        Path(path).write_text(self.to_text(), encoding="utf-8")

    def to_text(self) -> str:
        lines = [
            "Airblue Technical Publications Conversion Report",
            f"Created: {self.data['created_at']}",
            f"Template: {self.data['template_path']}",
            f"Source: {self.data['source_path']}",
            "",
            "Metadata",
        ]
        for key, value in self.data["metadata"].items():
            if value:
                lines.append(f"- {key}: {value}")

        lines.extend(["", "Detected Content Counts"])
        labels = {
            "body_paragraphs_extracted": "Total body paragraphs extracted",
            "total_headings": "Total headings detected",
            "chapter_heading": "Chapter headings detected",
            "heading_1": "Heading 1 items detected",
            "heading_2": "Heading 2 items detected",
            "heading_3": "Heading 3 items detected",
            "heading_4": "Heading 4 items detected",
            "heading_5": "Heading 5 items detected",
            "heading_6": "Heading 6 items detected",
            "paragraph_number_level_1": "Paragraph numbering Level 1 items detected",
            "paragraph_number_level_2": "Paragraph numbering Level 2 items detected",
            "paragraph_number_level_3": "Paragraph numbering Level 3 items detected",
            "paragraph_number_level_4": "Paragraph numbering Level 4 items detected",
            "paragraph_number_level_5": "Paragraph numbering Level 5 items detected",
            "tables": "Total tables extracted",
            "tables_inserted": "Total tables inserted",
            "images": "Total images extracted",
            "images_inserted": "Total images inserted",
            "intentionally_blank_pages": "Intentionally Left Blank pages detected",
            "section_breaks_inserted": "Section breaks inserted",
            "page_breaks_inserted": "Page breaks inserted",
            "chapters_detected": "Chapters detected",
            "appendices_detected": "Appendices detected",
        }
        for key, label in labels.items():
            lines.append(f"- {label}: {self.data['counts'].get(key, 0)}")

        skipped = self.data["skipped_front_matter"]
        lines.extend(
            [
                "",
                "Skipped Old Front Matter",
                f"- Items skipped: {skipped['items']}",
                f"- Pages/sections skipped: {', '.join(map(str, skipped['pages'])) if skipped['pages'] else 'Not page-detectable or none'}",
            ]
        )
        if skipped["samples"]:
            lines.append("- Samples skipped:")
            lines.extend(f"  - {sample}" for sample in skipped["samples"][:20])

        lines.extend(["", "Generated Front Matter / Numbering Status"])
        for key, value in self.data["generated"].items():
            lines.append(f"- {key}: {value}")

        sections = [
            ("Missing Styles", "missing_styles"),
            ("Missing Placeholders", "missing_placeholders"),
            ("Missing Bookmarks", "missing_bookmarks"),
            ("Unreplaced Placeholders", "unreplaced_placeholders"),
            ("Unmapped or Low-Confidence Content", "unmapped_content"),
            ("Numbering Conflicts", "numbering_conflicts"),
            ("Warnings", "warnings"),
            ("Errors", "errors"),
        ]
        for title, key in sections:
            lines.extend(["", title])
            values = self.data[key]
            if not values:
                lines.append("- None")
                continue
            for value in values:
                if isinstance(value, dict):
                    lines.append("- " + "; ".join(f"{k}: {v}" for k, v in value.items()))
                else:
                    lines.append(f"- {value}")

        lines.extend(["", "Final Review Checklist"])
        if self.data["quality_control"]:
            for row in self.data["quality_control"]:
                suffix = f" - {row['detail']}" if row.get("detail") else ""
                lines.append(f"- [{row['status']}] {row['item']}{suffix}")
        else:
            lines.append("- Not run")

        lines.extend(["", "Outputs"])
        if self.data["outputs"]:
            for key, value in self.data["outputs"].items():
                lines.append(f"- {key}: {value}")
        else:
            lines.append("- None yet")
        return "\n".join(lines) + "\n"
