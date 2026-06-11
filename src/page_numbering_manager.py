from __future__ import annotations

import json
import re
import shutil
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from .report_generator import ReportBuilder


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"

ET.register_namespace("w", W_NS)
ET.register_namespace("r", R_NS)


class PageNumberingManager:
    """Patches DOCX section headers with chapter-page PAGE fields where possible."""

    HEADER_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/header"
    HEADER_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"

    def __init__(self, config_path: str | Path = "config/page_numbering_rules.json"):
        self.config = json.loads(Path(config_path).read_text(encoding="utf-8"))

    def patch_docx(self, docx_path: str | Path, sections_info: list[dict[str, str]], metadata: dict[str, str], mode: str, report: ReportBuilder) -> None:
        if not sections_info:
            report.add_warning("No chapter or appendix sections were detected; chapter-page numbering could not be applied.")
            return
        if mode == "static":
            report.add_warning("Static page-number fallback selected. Page number prefixes were prepared, but final page numbers must be verified in Word.")

        docx_path = Path(docx_path)
        work_path = docx_path.with_suffix(".numbering.tmp.docx")
        shutil.copyfile(docx_path, work_path)

        try:
            with zipfile.ZipFile(work_path, "r") as zin:
                files = {name: zin.read(name) for name in zin.namelist()}
            self._patch_files(files, sections_info, metadata, mode, report)
            with zipfile.ZipFile(docx_path, "w", zipfile.ZIP_DEFLATED) as zout:
                for name, data in files.items():
                    zout.writestr(name, data)
        finally:
            if work_path.exists():
                work_path.unlink()

        report.data["generated"]["page_numbering"] = "best_effort_word_fields" if mode != "static" else "static_fallback"
        report.add_warning(
            "Chapter-page numbering is prepared with section restarts and header PAGE fields. "
            "Open the document in Microsoft Word, press Ctrl+A then F9, and verify every header/footer before release."
        )

    def _patch_files(self, files: dict[str, bytes], sections_info: list[dict[str, str]], metadata: dict[str, str], mode: str, report: ReportBuilder) -> None:
        document = ET.fromstring(files["word/document.xml"])
        rels_path = "word/_rels/document.xml.rels"
        rels = ET.fromstring(files[rels_path])
        content_types = ET.fromstring(files["[Content_Types].xml"])
        section_props = document.findall(f".//{{{W_NS}}}sectPr")

        rel_targets = {
            rel.get("Id"): rel.get("Target")
            for rel in rels.findall(f"{{{PKG_REL_NS}}}Relationship")
            if rel.get("Type") == self.HEADER_REL_TYPE
        }
        existing_header_numbers = self._existing_numbers(files, "word/header", ".xml")
        next_header_number = max(existing_header_numbers or [0]) + 1
        next_rid = self._next_rid(rels)

        for info in sections_info:
            index = int(info["section_index"])
            if index >= len(section_props):
                report.add_warning(f"Could not patch header for section index {index}; section was not found in document.xml.")
                continue
            sect_pr = section_props[index]
            header_ref = self._default_header_ref(sect_pr)
            if header_ref is None:
                previous_ref = self._nearest_previous_header(section_props, index)
                if previous_ref is None:
                    report.add_warning(f"No template header reference was available for section {info.get('title', index)}.")
                    continue
                header_ref = previous_ref

            source_rid = header_ref.get(f"{{{R_NS}}}id")
            source_target = rel_targets.get(source_rid or "")
            if not source_target:
                report.add_warning(f"Header relationship for section {info.get('title', index)} could not be resolved.")
                continue

            source_header_path = "word/" + source_target.lstrip("/")
            source_header = files.get(source_header_path)
            if not source_header:
                report.add_warning(f"Header part {source_header_path} was not found.")
                continue

            new_header_name = f"header{next_header_number}.xml"
            next_header_number += 1
            new_header_path = f"word/{new_header_name}"
            files[new_header_path] = self._header_with_page_field(source_header, info["prefix"], metadata, mode)

            old_rels_path = f"word/_rels/{Path(source_target).name}.rels"
            if old_rels_path in files:
                files[f"word/_rels/{new_header_name}.rels"] = files[old_rels_path]

            new_rid = f"rId{next_rid}"
            next_rid += 1
            rel = ET.Element(f"{{{PKG_REL_NS}}}Relationship")
            rel.set("Id", new_rid)
            rel.set("Type", self.HEADER_REL_TYPE)
            rel.set("Target", new_header_name)
            rels.append(rel)
            rel_targets[new_rid] = new_header_name

            default_ref = self._default_header_ref(sect_pr)
            if default_ref is None:
                default_ref = ET.Element(f"{{{W_NS}}}headerReference")
                default_ref.set(f"{{{W_NS}}}type", "default")
                sect_pr.insert(0, default_ref)
            default_ref.set(f"{{{R_NS}}}id", new_rid)

            self._ensure_pgnum_start(sect_pr)
            self._ensure_content_type(content_types, f"/word/{new_header_name}")

        files["word/document.xml"] = ET.tostring(document, encoding="utf-8", xml_declaration=True)
        files[rels_path] = ET.tostring(rels, encoding="utf-8", xml_declaration=True)
        files["[Content_Types].xml"] = ET.tostring(content_types, encoding="utf-8", xml_declaration=True)

    def _header_with_page_field(self, header_xml: bytes, prefix: str, metadata: dict[str, str], mode: str) -> bytes:
        root = ET.fromstring(header_xml)
        table_cells = root.findall(f".//{{{W_NS}}}tc")
        target_cell = table_cells[-1] if table_cells else None
        target_paragraph = None
        if target_cell is not None:
            paragraphs = target_cell.findall(f".//{{{W_NS}}}p")
            target_paragraph = paragraphs[-1] if paragraphs else None
        if target_paragraph is None:
            target_paragraph = ET.SubElement(root, f"{{{W_NS}}}p")

        for child in list(target_paragraph):
            target_paragraph.remove(child)

        text = self.config.get("header_metadata_format", "E-{edition} R-{revision} {prefix}-").format(
            edition=metadata.get("edition_number", ""),
            revision=metadata.get("revision_number", ""),
            prefix=prefix,
        )
        self._append_text_run(target_paragraph, text)
        if mode == "static":
            self._append_text_run(target_paragraph, "1")
        else:
            self._append_page_field(target_paragraph)
        return ET.tostring(root, encoding="utf-8", xml_declaration=True)

    def _append_text_run(self, paragraph, text: str) -> None:
        run = ET.SubElement(paragraph, f"{{{W_NS}}}r")
        t = ET.SubElement(run, f"{{{W_NS}}}t")
        t.text = text

    def _append_page_field(self, paragraph) -> None:
        begin_run = ET.SubElement(paragraph, f"{{{W_NS}}}r")
        begin = ET.SubElement(begin_run, f"{{{W_NS}}}fldChar")
        begin.set(f"{{{W_NS}}}fldCharType", "begin")
        instr_run = ET.SubElement(paragraph, f"{{{W_NS}}}r")
        instr = ET.SubElement(instr_run, f"{{{W_NS}}}instrText")
        instr.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        instr.text = " PAGE "
        sep_run = ET.SubElement(paragraph, f"{{{W_NS}}}r")
        sep = ET.SubElement(sep_run, f"{{{W_NS}}}fldChar")
        sep.set(f"{{{W_NS}}}fldCharType", "separate")
        self._append_text_run(paragraph, "1")
        end_run = ET.SubElement(paragraph, f"{{{W_NS}}}r")
        end = ET.SubElement(end_run, f"{{{W_NS}}}fldChar")
        end.set(f"{{{W_NS}}}fldCharType", "end")

    def _default_header_ref(self, sect_pr):
        for header_ref in sect_pr.findall(f"{{{W_NS}}}headerReference"):
            if header_ref.get(f"{{{W_NS}}}type", "default") == "default":
                return header_ref
        refs = sect_pr.findall(f"{{{W_NS}}}headerReference")
        return refs[0] if refs else None

    def _nearest_previous_header(self, section_props, index: int):
        for prev in range(index - 1, -1, -1):
            header_ref = self._default_header_ref(section_props[prev])
            if header_ref is not None:
                return header_ref
        return None

    def _ensure_pgnum_start(self, sect_pr) -> None:
        pg_num = sect_pr.find(f"{{{W_NS}}}pgNumType")
        if pg_num is None:
            pg_num = ET.Element(f"{{{W_NS}}}pgNumType")
            sect_pr.append(pg_num)
        pg_num.set(f"{{{W_NS}}}start", "1")

    def _ensure_content_type(self, content_types, part_name: str) -> None:
        for override in content_types.findall(f"{{{CT_NS}}}Override"):
            if override.get("PartName") == part_name:
                return
        override = ET.Element(f"{{{CT_NS}}}Override")
        override.set("PartName", part_name)
        override.set("ContentType", self.HEADER_CONTENT_TYPE)
        content_types.append(override)

    def _existing_numbers(self, files: dict[str, bytes], prefix: str, suffix: str) -> list[int]:
        numbers: list[int] = []
        pattern = re.compile(rf"{re.escape(prefix)}(\d+){re.escape(suffix)}$")
        for name in files:
            match = pattern.match(name)
            if match:
                numbers.append(int(match.group(1)))
        return numbers

    def _next_rid(self, rels) -> int:
        max_id = 0
        for rel in rels.findall(f"{{{PKG_REL_NS}}}Relationship"):
            rid = rel.get("Id", "")
            match = re.match(r"rId(\d+)$", rid)
            if match:
                max_id = max(max_id, int(match.group(1)))
        return max_id + 1
