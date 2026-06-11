from __future__ import annotations

import json
from pathlib import Path

from .models import ContentItem, DetectionResult
from .report_generator import ReportBuilder
from .section_break_manager import SectionBreakManager


class LEPGenerator:
    """Builds a best-effort List of Effective Pages from the detected structure."""

    def __init__(self, config_path: str | Path = "config/generated_tables.json"):
        self.config = json.loads(Path(config_path).read_text(encoding="utf-8")).get("lep", {})
        self.section_manager = SectionBreakManager()

    def generate(self, decisions: list[tuple[ContentItem, DetectionResult]], metadata: dict[str, str], report: ReportBuilder) -> list[list[str]]:
        columns = self.config.get("columns", ["Section", "Page", "Edition", "Revision", "Effective Date", "Remarks"])
        rows = [columns]
        remark = self.config.get("review_remark", "Review after Word pagination update.")
        rows.append(["Front Matter", "0-1", metadata.get("edition_number", ""), metadata.get("revision_number", ""), metadata.get("effective_date", ""), remark])

        seen: set[str] = set()
        for item, decision in decisions:
            if decision.role not in {"chapter_heading", "appendix_heading"}:
                continue
            prefix = self.section_manager.prefix_for(item.text, decision)
            if prefix in seen:
                continue
            seen.add(prefix)
            rows.append([
                item.text,
                f"{prefix}-1",
                metadata.get("edition_number", ""),
                metadata.get("revision_number", ""),
                metadata.get("effective_date", ""),
                remark,
            ])

        report.data["generated"]["lep"] = "generated_best_effort"
        report.add_warning("LEP is generated from detected document structure. Final LEP must be reviewed after Word updates pagination.")
        return rows
