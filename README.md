# Airblue Technical Publications Document Automation Tool

A local web app for converting old Airblue manuals into the official new-edition Airblue Word template.

The uploaded `.docx` template is always the master design source. The old manual is only the content source. The converter does not rewrite, summarize, paraphrase, correct, translate, or improve manual text.

## What The Tool Does

- Uses the uploaded Airblue `.docx` template as the base document.
- Keeps the template front matter, styles, headers, footers, page setup, bookmarks, fields, section breaks, numbering definitions, and controlled document layout.
- Extracts body content from an old `.docx` or `.pdf`.
- Removes only old cover/control material where it can do so conservatively.
- Inserts the extracted body content at the configured content bookmark or placeholder.
- Applies existing template styles by exact style name.
- Starts detected chapters and appendices on new Word sections.
- Restarts page numbering at detected chapters and appendices.
- Applies a best-effort chapter-page header field format such as `1-1`, `2-1`, or `A-1`.
- Preserves `Intentionally Left Blank` markers as standalone pages.
- Generates or updates LEP, ROR, ROA, Definitions, Abbreviations, Approval, and Conformance sections where enabled.
- Preserves DOCX table XML where possible so rows, columns, and merged cells survive.
- Preserves body images where possible and warns when images cannot be safely transferred.
- Generates a final `.docx` plus `.txt` and `.json` conversion reports.
- Marks uncertain heading/list decisions in the report for manual review.

## Install

From this project folder:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If PowerShell blocks activation, run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

## Run

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn app:app --reload --host 127.0.0.1 --port 8000
```

Open:

```text
http://127.0.0.1:8000
```

## Upload The Airblue Template

On the first screen, select the official new-edition Airblue template `.docx`.

The converter copies that file into a temporary job folder and edits only the copy. It does not overwrite the original template.

## Upload The Old Manual

Select the old manual as either:

- `.docx`
- `.pdf`

DOCX conversion preserves paragraphs, table text, and body images where possible. PDF conversion is text-first and needs closer review.

## Enter Metadata

Fill in the available metadata fields:

- Manual Name
- Manual Abbreviation
- Edition Number
- Revision Number
- Effective Date
- Issue Date
- Department / Owner
- Prepared By
- Checked By
- Approved By

The tool replaces configured placeholders such as `{{MANUAL_NAME}}`, updates configured bookmarks, applies configured front-matter text patterns, and updates Word core document properties where supported.

## Preview

Click **Preview Mapping** before exporting.

The preview shows detected content roles, target styles, confidence, skipped front-matter items, warnings, and unresolved mapping issues.

The preview also shows generated-section status for:

- LEP
- ROR
- ROA
- Definitions
- Abbreviations
- Conformance tables
- Page numbering

## Download The Converted DOCX

After preview, click **Export DOCX**.

The result page provides:

- Final converted `.docx`
- Conversion report `.txt`
- Conversion report `.json`

Open the `.docx` in Microsoft Word for final controlled-document checks.

## Update TOC And Fields In Microsoft Word

After opening the exported `.docx` in Word:

1. Press `Ctrl+A`.
2. Press `F9`.
3. Update the Table of Contents when prompted.
4. Right-click the Table of Contents and select `Update Field`.
5. Select `Update entire table`.
6. Check page numbers in the header/footer.
7. Check LEP after pagination is updated.
8. Review all generated front matter before controlled release.
9. Save the document.

The converter sets Word's update-fields-on-open setting where possible, but final field refresh should still be done in Word.

## Edit Style Mapping

Edit:

```text
config/style_map.json
```

Important keys:

- `target_styles`: Maps detected roles to exact template style names.
- `table_style`: Template table style for transferred tables.
- `content_bookmarks`: Bookmark names used as the body insertion point.
- `content_placeholders`: Placeholder text used as a body insertion point if no bookmark exists.
- `replace_existing_body_after_bookmark`: Removes the template sample body from the insertion point onward before inserting converted content.
- `strip_numbering_when_style_has_auto_numbering`: Removes visible source numbering only when the target Word style already has automatic numbering.

For the provided Airblue template, the default insertion bookmark is:

```text
Chapter_0
```

## Edit Placeholder Mapping

Edit:

```text
config/placeholders.json
```

Use `placeholders` for text tokens such as:

```json
"{{MANUAL_NAME}}": "manual_name"
```

Use `bookmarks` for Word bookmarks such as:

```json
"MANUAL_NAME": "manual_name"
```

Use `front_matter_patterns` only for template front matter. These rules are useful when a template has fixed text instead of placeholders.

## Edit Manual Section Rules

Edit:

```text
config/manual_sections.json
```

This file controls required manual sections, section-break behavior, page-break behavior, and the heading names used to locate front-matter regions.

## Edit Page Numbering Rules

Edit:

```text
config/page_numbering_rules.json
```

This file controls front-matter, chapter, and appendix page-number formats. The default mode uses Word `PAGE` fields and section page-number restarts. If the web UI is set to static fallback, the report warns that the Technical Writer must verify every page number manually.

## Edit Generated Table Rules

Edit:

```text
config/generated_tables.json
```

This file controls generated LEP, ROR, ROA, and conformance table behavior, including columns and safe default revision descriptions.

## Edit Front Matter Rules

Edit:

```text
config/front_matter_rules.json
```

This file controls approval-page metadata fields and sample value patterns used for quality-control checks.

## Edit Numbering Rules

Edit:

```text
config/numbering_rules.json
```

This file controls heading/list detection:

- `Chapter 1` -> `chapter_heading`
- `1` -> `heading_1` when heading context is strong
- `1.1` -> `heading_2`
- `1.1.1` -> `heading_3`
- `A.` -> paragraph numbering level 1
- `1.` -> paragraph numbering level 2
- `a.` -> paragraph numbering level 3
- `i.` -> paragraph numbering level 4
- `a)` -> paragraph numbering level 5

The detector uses numbering pattern, source Word style, bold formatting, capitalization, line length, and sentence-like context to avoid treating normal list paragraphs as headings.

## PDF Conversion Limits

PDF files do not contain Word styles, Word numbering definitions, bookmarks, fields, or section structure in a form that can be reliably reconstructed.

For PDFs, the tool extracts visible text and applies best-effort style detection. Tables may be detected by `pdfplumber`, but complex table geometry may need manual cleanup in Word.

PDF images and exact pagination are not as reliable as DOCX input. The report warns when image/table extraction is incomplete.

## Scanned PDF OCR Limits

Scanned PDFs may contain no extractable text. The report warns when pages appear scanned.

OCR support requires a local Tesseract installation in addition to the Python package `pytesseract`. OCR output should always be manually checked against the original manual because OCR can introduce character errors.

## Error Handling

The report flags:

- Missing bookmarks
- Missing placeholders
- Missing styles
- Ambiguous heading/list detection
- Numbering conflicts
- Corrupted or unsupported Word/PDF files
- Scanned PDF or OCR issues
- Unsupported formatting that needs manual review
- Generated LEP/ROR/ROA status
- Definitions, abbreviations, and conformance extraction status
- Intentionally Left Blank page count
- Chapter and appendix section count
- Section/page break count
- Tables/images extracted and inserted
- Final review checklist

## Project Structure

```text
app.py
requirements.txt
README.md
config/
  numbering_rules.json
  manual_sections.json
  page_numbering_rules.json
  front_matter_rules.json
  generated_tables.json
  placeholders.json
  style_map.json
outputs/
src/
  abbreviations_extractor.py
  blank_page_handler.py
  conformance_table_extractor.py
  content_cleaner.py
  converter.py
  definitions_extractor.py
  docx_reader.py
  front_matter_updater.py
  image_handler.py
  lep_generator.py
  numbering_detector.py
  page_numbering_manager.py
  pdf_reader.py
  report_generator.py
  roa_generator.py
  ror_generator.py
  section_break_manager.py
  style_mapper.py
  table_handler.py
  template_engine.py
templates/
uploads/
tests/
```

## Run Tests

```powershell
python -m unittest discover -s tests
```

## Current Automation Boundaries

The tool prepares section breaks, page-number restarts, Word fields, generated front matter, body tables, and body images. Microsoft Word remains the final pagination authority. Always update fields and review the LEP, TOC, headers/footers, section breaks, and generated front matter before controlled release.
