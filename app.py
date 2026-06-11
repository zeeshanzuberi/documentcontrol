from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Annotated

try:
    from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
    from fastapi.responses import FileResponse, HTMLResponse
    from fastapi.templating import Jinja2Templates
except ImportError as exc:  # pragma: no cover - exercised when dependencies are missing
    raise SystemExit(
        "FastAPI dependencies are not installed. Run: python -m pip install -r requirements.txt"
    ) from exc

from src.converter import DocumentConverter, normalize_metadata


BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"
TEMPLATE_DIR = BASE_DIR / "templates"
CONFIG_DIR = BASE_DIR / "config"

for folder in (UPLOAD_DIR, OUTPUT_DIR, TEMPLATE_DIR):
    folder.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Airblue Technical Publications Document Automation")
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))


def metadata_from_form(
    manual_name: str,
    manual_abbreviation: str,
    edition_number: str,
    revision_number: str,
    effective_date: str,
    issue_date: str,
    document_owner: str,
    prepared_by: str,
    checked_by: str,
    approved_by: str,
) -> dict[str, str]:
    return normalize_metadata(
        {
            "manual_name": manual_name,
            "manual_abbreviation": manual_abbreviation,
            "edition_number": edition_number,
            "revision_number": revision_number,
            "effective_date": effective_date,
            "issue_date": issue_date,
            "document_owner": document_owner,
            "prepared_by": prepared_by,
            "checked_by": checked_by,
            "approved_by": approved_by,
        }
    )


def options_from_form(
    body_insertion_bookmark: str = "",
    generate_lep: str | None = None,
    generate_ror: str | None = None,
    generate_roa: str | None = None,
    extract_definitions: str | None = None,
    extract_abbreviations: str | None = None,
    extract_conformance: str | None = None,
    preserve_blank_pages: str | None = None,
    extract_images: str | None = None,
    extract_tables: str | None = None,
    revision_bars: str | None = None,
    numbering_mode: str = "word_fields",
) -> dict:
    return {
        "body_insertion_bookmark": body_insertion_bookmark.strip(),
        "generate_lep": generate_lep is not None,
        "generate_ror": generate_ror is not None,
        "generate_roa": generate_roa is not None,
        "extract_definitions": extract_definitions is not None,
        "extract_abbreviations": extract_abbreviations is not None,
        "extract_conformance": extract_conformance is not None,
        "preserve_blank_pages": preserve_blank_pages is not None,
        "extract_images": extract_images is not None,
        "extract_tables": extract_tables is not None,
        "revision_bars": revision_bars is not None,
        "numbering_mode": numbering_mode if numbering_mode in {"word_fields", "static"} else "word_fields",
    }


def build_converter() -> DocumentConverter:
    return DocumentConverter(
        style_map_path=CONFIG_DIR / "style_map.json",
        placeholder_path=CONFIG_DIR / "placeholders.json",
        numbering_rules_path=CONFIG_DIR / "numbering_rules.json",
        manual_sections_path=CONFIG_DIR / "manual_sections.json",
        page_numbering_rules_path=CONFIG_DIR / "page_numbering_rules.json",
        front_matter_rules_path=CONFIG_DIR / "front_matter_rules.json",
        generated_tables_path=CONFIG_DIR / "generated_tables.json",
    )


async def save_upload(upload: UploadFile, target_dir: Path) -> Path:
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix not in {".docx", ".pdf"}:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {suffix or 'missing extension'}")
    safe_name = f"{Path(upload.filename or 'upload').stem[:80]}{suffix}"
    path = target_dir / safe_name
    path.write_bytes(await upload.read())
    return path


def load_job(job_id: str) -> dict:
    job_path = UPLOAD_DIR / job_id / "job.json"
    if not job_path.exists():
        raise HTTPException(status_code=404, detail="Conversion job was not found.")
    return json.loads(job_path.read_text(encoding="utf-8"))


def ensure_output_path(job_id: str, filename: str) -> Path:
    base = (OUTPUT_DIR / job_id).resolve()
    path = (base / filename).resolve()
    if not str(path).startswith(str(base)) or not path.exists():
        raise HTTPException(status_code=404, detail="Output file was not found.")
    return path


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {"request": request})


@app.post("/preview", response_class=HTMLResponse)
async def preview(
    request: Request,
    template_file: Annotated[UploadFile, File()],
    source_file: Annotated[UploadFile, File()],
    manual_name: Annotated[str, Form()] = "",
    manual_abbreviation: Annotated[str, Form()] = "",
    edition_number: Annotated[str, Form()] = "",
    revision_number: Annotated[str, Form()] = "",
    effective_date: Annotated[str, Form()] = "",
    issue_date: Annotated[str, Form()] = "",
    document_owner: Annotated[str, Form()] = "",
    prepared_by: Annotated[str, Form()] = "",
    checked_by: Annotated[str, Form()] = "",
    approved_by: Annotated[str, Form()] = "",
    body_insertion_bookmark: Annotated[str, Form()] = "",
    generate_lep: Annotated[str | None, Form()] = None,
    generate_ror: Annotated[str | None, Form()] = None,
    generate_roa: Annotated[str | None, Form()] = None,
    extract_definitions: Annotated[str | None, Form()] = None,
    extract_abbreviations: Annotated[str | None, Form()] = None,
    extract_conformance: Annotated[str | None, Form()] = None,
    preserve_blank_pages: Annotated[str | None, Form()] = None,
    extract_images: Annotated[str | None, Form()] = None,
    extract_tables: Annotated[str | None, Form()] = None,
    revision_bars: Annotated[str | None, Form()] = None,
    numbering_mode: Annotated[str, Form()] = "word_fields",
):
    if Path(template_file.filename or "").suffix.lower() != ".docx":
        raise HTTPException(status_code=400, detail="The Airblue template must be a .docx file.")

    job_id = uuid.uuid4().hex
    job_upload_dir = UPLOAD_DIR / job_id
    job_upload_dir.mkdir(parents=True, exist_ok=True)
    metadata = metadata_from_form(
        manual_name,
        manual_abbreviation,
        edition_number,
        revision_number,
        effective_date,
        issue_date,
        document_owner,
        prepared_by,
        checked_by,
        approved_by,
    )

    template_path = await save_upload(template_file, job_upload_dir)
    source_path = await save_upload(source_file, job_upload_dir)
    options = options_from_form(
        body_insertion_bookmark=body_insertion_bookmark,
        generate_lep=generate_lep,
        generate_ror=generate_ror,
        generate_roa=generate_roa,
        extract_definitions=extract_definitions,
        extract_abbreviations=extract_abbreviations,
        extract_conformance=extract_conformance,
        preserve_blank_pages=preserve_blank_pages,
        extract_images=extract_images,
        extract_tables=extract_tables,
        revision_bars=revision_bars,
        numbering_mode=numbering_mode,
    )

    converter = build_converter()
    try:
        preview_data = converter.preview(template_path, source_path, metadata, options)
    except Exception as exc:
        return templates.TemplateResponse(
            request,
            "error.html",
            {"request": request, "message": str(exc)},
            status_code=400,
        )

    job = {
        "job_id": job_id,
        "template_path": str(template_path),
        "source_path": str(source_path),
        "metadata": metadata,
        "options": options,
    }
    (job_upload_dir / "job.json").write_text(json.dumps(job, indent=2), encoding="utf-8")
    (job_upload_dir / "preview.json").write_text(json.dumps(preview_data, indent=2), encoding="utf-8")

    return templates.TemplateResponse(
        request,
        "preview.html",
        {
            "request": request,
            "job_id": job_id,
            "metadata": metadata,
            "preview": preview_data,
            "options": options,
        },
    )


@app.post("/convert/{job_id}", response_class=HTMLResponse)
async def convert(request: Request, job_id: str):
    job = load_job(job_id)
    output_dir = OUTPUT_DIR / job_id
    converter = build_converter()
    try:
        report = converter.convert(
            template_path=job["template_path"],
            source_path=job["source_path"],
            metadata=job["metadata"],
            output_dir=output_dir,
            revision_bars=job.get("options", {}).get("revision_bars", False),
            options=job.get("options", {}),
        )
    except Exception as exc:
        return templates.TemplateResponse(
            request,
            "error.html",
            {"request": request, "message": str(exc)},
            status_code=400,
        )

    downloads = []
    for path_value in report.get("outputs", {}).values():
        path = Path(path_value)
        downloads.append({"name": path.name, "url": f"/download/{job_id}/{path.name}"})

    return templates.TemplateResponse(
        request,
        "result.html",
        {"request": request, "job_id": job_id, "report": report, "downloads": downloads},
    )


@app.get("/download/{job_id}/{filename}")
async def download(job_id: str, filename: str):
    path = ensure_output_path(job_id, filename)
    media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if path.suffix == ".txt":
        media_type = "text/plain"
    elif path.suffix == ".json":
        media_type = "application/json"
    return FileResponse(path, media_type=media_type, filename=path.name)


@app.get("/health")
async def health():
    return {"status": "ok"}
