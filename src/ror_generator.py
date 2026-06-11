from __future__ import annotations

import json
from pathlib import Path

from .report_generator import ReportBuilder


class RORGenerator:
    """Builds the current Record of Revisions row from metadata."""

    def __init__(self, config_path: str | Path = "config/generated_tables.json"):
        self.config = json.loads(Path(config_path).read_text(encoding="utf-8")).get("ror", {})

    def generate(self, metadata: dict[str, str], report: ReportBuilder) -> list[list[str]]:
        columns = self.config.get("columns", ["Revision", "Date", "Description", "Inserted By", "Approved By"])
        description = metadata.get("revision_description") or self.config.get("default_description", "Converted to new Airblue manual template format.")
        rows = [
            columns,
            [
                metadata.get("revision_number", ""),
                metadata.get("effective_date") or metadata.get("issue_date", ""),
                description,
                metadata.get("prepared_by", ""),
                metadata.get("approved_by", ""),
            ],
        ]
        report.data["generated"]["ror"] = "generated_from_metadata"
        return rows
