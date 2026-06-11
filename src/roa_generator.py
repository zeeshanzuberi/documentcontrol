from __future__ import annotations

import json
from pathlib import Path

from .report_generator import ReportBuilder


class ROAGenerator:
    """Builds a current Record of Amendments entry from available metadata."""

    def __init__(self, config_path: str | Path = "config/generated_tables.json"):
        self.config = json.loads(Path(config_path).read_text(encoding="utf-8")).get("roa", {})

    def generate(self, metadata: dict[str, str], report: ReportBuilder) -> list[list[str]]:
        columns = self.config.get("columns", ["Amendment", "Date", "Affected Pages", "Inserted By"])
        affected = self.config.get("default_affected_pages", "Generated manual; review LEP after Word pagination update.")
        rows = [
            columns,
            [
                f"Edition {metadata.get('edition_number', '')}, Revision {metadata.get('revision_number', '')}".strip(", "),
                metadata.get("effective_date") or metadata.get("issue_date", ""),
                affected,
                metadata.get("prepared_by", ""),
            ],
        ]
        report.data["generated"]["roa"] = "generated_from_metadata"
        return rows
