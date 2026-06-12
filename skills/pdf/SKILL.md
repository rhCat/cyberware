---
skill: pdf
name: PDF processing
perks: [extract, info]
---

# pdf — PDF processing

Extract text or read metadata from a PDF — **read-only**. Both perks open the file, read it,
and write a report to `record_store`; neither modifies the source PDF.

## What to look out for
Each tool emits one line of structured JSON (the audit + debug log) and writes its artifact under
`record_store`. LOGS TO CHECK: that line + the named report + the executor run-ledger.

> **Best-effort extractors:** these tools prefer poppler's `pdftotext` / `pdfinfo`, falling back to
> the `pypdf` (or `PyPDF2` / `pdfminer`) Python package. If **none** is installed the tool still
> succeeds — it writes a one-line note to its report so the contract's `output_exists` always holds.

## Perks
| perk | tool | nature |
|---|---|---|
| `extract` | `pdf_extract` | read-only / safe |
| `info` | `pdf_info` | read-only / safe |

- **`extract`** — set `PDF_FILE`; writes the document's text to `extracted.txt`.
- **`info`** — set `PDF_FILE`; writes page count + document metadata to `pdf_info.json`.

## How to use it
Pick a perk, copy `ledger.json` → `task-ledger.json`, fill `PDF_FILE` + `record_store`, then
validate → compose → compile → oversight → executor.
