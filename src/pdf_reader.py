from __future__ import annotations

from pathlib import Path

from .models import ContentItem


class MissingPDFDependency(RuntimeError):
    pass


class PDFReader:
    """Extracts text from PDFs; OCR is optional and reported when unavailable."""

    def __init__(self, enable_ocr: bool = False):
        self.enable_ocr = enable_ocr

    def read(self, path: str | Path) -> tuple[list[ContentItem], dict[str, object]]:
        path = Path(path)
        warnings: list[str] = []
        try:
            import pdfplumber  # type: ignore
        except ImportError:
            pdfplumber = None

        if pdfplumber is not None:
            return self._read_with_pdfplumber(path, warnings)

        try:
            import fitz  # type: ignore
        except ImportError as exc:
            raise MissingPDFDependency(
                "PDF support requires pdfplumber or PyMuPDF. Install requirements.txt before converting PDFs."
            ) from exc

        return self._read_with_pymupdf(path, warnings, fitz)

    def _read_with_pdfplumber(self, path: Path, warnings: list[str]) -> tuple[list[ContentItem], dict[str, object]]:
        import pdfplumber  # type: ignore

        items: list[ContentItem] = []
        tables = 0
        with pdfplumber.open(str(path)) as pdf:
            for page_index, page in enumerate(pdf.pages, start=1):
                text = page.extract_text(x_tolerance=2, y_tolerance=3) or ""
                if not text.strip():
                    warnings.append(f"Page {page_index} has no extractable text and may be scanned.")
                for line in text.splitlines():
                    if line.strip():
                        items.append(ContentItem(type="paragraph", text=line.rstrip(), page_number=page_index))
                try:
                    page_tables = page.extract_tables() or []
                except Exception:
                    page_tables = []
                for table in page_tables:
                    rows = [["" if cell is None else str(cell) for cell in row] for row in table if row]
                    if rows:
                        tables += 1
                        items.append(ContentItem(type="table", rows=rows, page_number=page_index))
            page_count = len(pdf.pages)

        if not items:
            warnings.append("No extractable PDF text was found. OCR may be required.")
            if self.enable_ocr:
                warnings.append("OCR was requested, but OCR requires a local Tesseract installation.")
        for index, item in enumerate(items):
            item.metadata["source_index"] = index

        warnings.append("PDF conversion cannot preserve Word fields, bookmarks, or original table geometry with full fidelity.")
        return items, {"tables": tables, "images": 0, "warnings": warnings, "pages": page_count}

    def _read_with_pymupdf(self, path: Path, warnings: list[str], fitz_module) -> tuple[list[ContentItem], dict[str, object]]:
        items: list[ContentItem] = []
        image_count = 0
        with fitz_module.open(str(path)) as pdf:
            for page_index, page in enumerate(pdf, start=1):
                text = page.get_text("text") or ""
                if not text.strip():
                    warnings.append(f"Page {page_index} has no extractable text and may be scanned.")
                for line in text.splitlines():
                    if line.strip():
                        items.append(ContentItem(type="paragraph", text=line.rstrip(), page_number=page_index))
                image_count += len(page.get_images(full=True))
            page_count = pdf.page_count
        if not items:
            warnings.append("No extractable PDF text was found. OCR may be required.")
        for index, item in enumerate(items):
            item.metadata["source_index"] = index
        warnings.append("PDF conversion is text-first; tables and images may need manual review after export.")
        return items, {"tables": 0, "images": image_count, "warnings": warnings, "pages": page_count}
