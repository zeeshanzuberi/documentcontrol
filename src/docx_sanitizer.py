from __future__ import annotations

import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from lxml import etree


PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"

IMAGE_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
REL_ATTRS = {
    f"{{{REL_NS}}}id",
    f"{{{REL_NS}}}embed",
    f"{{{REL_NS}}}link",
}

REVIEW_PARTS = {
    "word/comments.xml",
    "word/commentsExtended.xml",
    "word/commentsIds.xml",
    "word/people.xml",
}
REVIEW_REL_TYPES = {
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments",
    "http://schemas.microsoft.com/office/2011/relationships/commentsExtended",
    "http://schemas.microsoft.com/office/2016/09/relationships/commentsIds",
    "http://schemas.microsoft.com/office/2017/10/relationships/people",
}
REVIEW_CONTENT_TYPES = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml",
    "application/vnd.ms-word.commentsExtended+xml",
    "application/vnd.ms-word.commentsIds+xml",
    "application/vnd.ms-word.people+xml",
}


class DocxSanitizer:
    """Removes stale OOXML parts left after using a full manual as a template."""

    def sanitize(self, docx_path: str | Path, report: Any | None = None) -> dict[str, int]:
        path = Path(docx_path)
        with zipfile.ZipFile(path, "r") as zin:
            original_names = {item.filename for item in zin.infolist()}
            files = {
                item.filename: zin.read(item.filename)
                for item in zin.infolist()
                if item.filename not in REVIEW_PARTS
            }

        summary = {
            "review_parts_removed": 0,
            "review_relationships_removed": 0,
            "unused_image_relationships_removed": 0,
            "unused_media_parts_removed": 0,
            "bookmark_elements_removed": 0,
            "paragraph_border_blocks_removed": 0,
            "simple_fields_unwrapped": 0,
            "hyperlinks_unwrapped": 0,
            "rendered_page_breaks_removed": 0,
            "proofing_markers_removed": 0,
            "comment_markers_removed": 0,
        }
        summary["review_parts_removed"] = sum(1 for part in REVIEW_PARTS if part in original_names)

        self._sanitize_relationships(files, summary)
        self._sanitize_content_types(files)
        self._sanitize_document_xml(files, summary)

        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zout:
            for name, data in files.items():
                zout.writestr(name, data)

        if report is not None:
            report.data["docx_sanitizer"] = summary
            if any(summary.values()):
                report.add_warning(
                    "Final DOCX sanitizer removed stale review metadata, invalid bookmarks, "
                    "unused media relationships, and Word repair-prone markup from the rebuilt document."
                )
        return summary

    def _sanitize_relationships(self, files: dict[str, bytes], summary: dict[str, int]) -> None:
        for rels_name in list(files):
            if not rels_name.endswith(".rels"):
                continue
            root = etree.fromstring(files[rels_name])
            base = self._relationship_base(rels_name)
            owner = self._owner_part_for_rels(rels_name)
            used_ids = self._used_relationship_ids(files, owner)
            changed = False

            for rel in list(root.findall(f"{{{PKG_REL_NS}}}Relationship")):
                rel_type = rel.get("Type") or ""
                target = rel.get("Target") or ""
                target_mode = rel.get("TargetMode")
                target_name = "" if target_mode == "External" else self._normalize_target(base, target)

                remove_review = rel_type in REVIEW_REL_TYPES or target_name in REVIEW_PARTS
                remove_unused_image = (
                    rel_type == IMAGE_REL_TYPE
                    and owner is not None
                    and rel.get("Id") not in used_ids
                )
                if remove_review or remove_unused_image:
                    root.remove(rel)
                    changed = True
                    if remove_review:
                        summary["review_relationships_removed"] += 1
                    if remove_unused_image:
                        summary["unused_image_relationships_removed"] += 1

            if changed:
                files[rels_name] = etree.tostring(root, encoding="utf-8", xml_declaration=True)

        self._remove_unreferenced_media(files, summary)

    def _sanitize_content_types(self, files: dict[str, bytes]) -> None:
        if "[Content_Types].xml" not in files:
            return
        root = etree.fromstring(files["[Content_Types].xml"])
        changed = False
        for override in list(root.findall(f"{{{CT_NS}}}Override")):
            part_name = (override.get("PartName") or "").lstrip("/")
            content_type = override.get("ContentType") or ""
            if part_name in REVIEW_PARTS or content_type in REVIEW_CONTENT_TYPES:
                root.remove(override)
                changed = True
            elif part_name.startswith("word/media/") and part_name not in files:
                root.remove(override)
                changed = True
        if changed:
            files["[Content_Types].xml"] = etree.tostring(root, encoding="utf-8", xml_declaration=True)

    def _sanitize_document_xml(self, files: dict[str, bytes], summary: dict[str, int]) -> None:
        if "word/document.xml" not in files:
            return
        root = etree.fromstring(files["word/document.xml"])
        ns = {"w": WORD_NS}

        for tag, key in [
            ("bookmarkStart", "bookmark_elements_removed"),
            ("bookmarkEnd", "bookmark_elements_removed"),
            ("lastRenderedPageBreak", "rendered_page_breaks_removed"),
            ("proofErr", "proofing_markers_removed"),
            ("commentRangeStart", "comment_markers_removed"),
            ("commentRangeEnd", "comment_markers_removed"),
            ("commentReference", "comment_markers_removed"),
        ]:
            summary[key] += self._remove_elements(root, f".//w:{tag}", ns)

        for pbdr in list(root.xpath(".//w:pBdr", namespaces=ns)):
            if self._is_no_border_block(pbdr):
                parent = pbdr.getparent()
                if parent is not None:
                    parent.remove(pbdr)
                    summary["paragraph_border_blocks_removed"] += 1

        summary["simple_fields_unwrapped"] += self._unwrap_elements(root, ".//w:fldSimple", ns)
        summary["hyperlinks_unwrapped"] += self._unwrap_elements(root, ".//w:hyperlink", ns)
        files["word/document.xml"] = etree.tostring(root, encoding="utf-8", xml_declaration=True)

    def _remove_unreferenced_media(self, files: dict[str, bytes], summary: dict[str, int]) -> None:
        referenced = set()
        for name, data in files.items():
            if not name.endswith(".rels"):
                continue
            root = etree.fromstring(data)
            base = self._relationship_base(name)
            for rel in root.findall(f"{{{PKG_REL_NS}}}Relationship"):
                if rel.get("TargetMode") == "External":
                    continue
                referenced.add(self._normalize_target(base, rel.get("Target") or ""))

        for name in list(files):
            if name.startswith("word/media/") and name not in referenced:
                files.pop(name)
                summary["unused_media_parts_removed"] += 1

    def _used_relationship_ids(self, files: dict[str, bytes], owner: str | None) -> set[str]:
        if owner is None or owner not in files or not owner.endswith(".xml"):
            return set()
        try:
            root = etree.fromstring(files[owner])
        except etree.XMLSyntaxError:
            return set()
        used = set()
        for element in root.iter():
            for attr, value in element.attrib.items():
                if attr in REL_ATTRS and value:
                    used.add(value)
        return used

    def _remove_elements(self, root, expression: str, namespaces: dict[str, str]) -> int:
        removed = 0
        for element in list(root.xpath(expression, namespaces=namespaces)):
            parent = element.getparent()
            if parent is not None:
                parent.remove(element)
                removed += 1
        return removed

    def _unwrap_elements(self, root, expression: str, namespaces: dict[str, str]) -> int:
        unwrapped = 0
        for element in list(root.xpath(expression, namespaces=namespaces)):
            parent = element.getparent()
            if parent is None:
                continue
            index = parent.index(element)
            children = list(element)
            parent.remove(element)
            for child in reversed(children):
                parent.insert(index, child)
            unwrapped += 1
        return unwrapped

    def _is_no_border_block(self, pbdr) -> bool:
        children = list(pbdr)
        if not children:
            return True
        return all(child.get(f"{{{WORD_NS}}}val") in {None, "none", "nil"} for child in children)

    def _relationship_base(self, rels_name: str) -> PurePosixPath:
        if rels_name == "_rels/.rels":
            return PurePosixPath("")
        return PurePosixPath(rels_name).parent.parent

    def _owner_part_for_rels(self, rels_name: str) -> str | None:
        if rels_name == "_rels/.rels":
            return None
        path = PurePosixPath(rels_name)
        return str(path.parent.parent / path.name[: -len(".rels")])

    def _normalize_target(self, base: PurePosixPath, target: str) -> str:
        target_name = target.lstrip("/") if target.startswith("/") else str(base / target)
        parts: list[str] = []
        for part in target_name.split("/"):
            if part == "..":
                if parts:
                    parts.pop()
            elif part and part != ".":
                parts.append(part)
        return "/".join(parts)
