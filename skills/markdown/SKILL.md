---
skill: markdown
name: Markdown docs hygiene
perks: [toc, links]
---

# markdown — Markdown docs hygiene

Generate a table of contents or find dead relative links in a Markdown file — read-only.
Both perks read a single `.md` file and never modify it; they only write a report under
`record_store`.

## What to look out for
Each tool emits one line of structured JSON (the audit + debug log) and writes its
artifacts under `record_store`. LOGS TO CHECK: that line + the named report + the executor run-ledger.

## Perks
| perk | tool | nature |
|---|---|---|
| `toc` | `md_toc` | read-only / safe |
| `links` | `md_links` | read-only / safe |

The `toc` perk scans ATX headings (`#`…`######`), skips headings inside fenced code blocks, and
writes a nested bullet list of `- [text](#slug)` links (GitHub-style slugs) to `toc.md` — always,
even when the file has no headings.

The `links` perk extracts inline `[text](target)` links, keeps only RELATIVE targets (skipping
`http://`, `https://`, `mailto:`, and pure `#anchor` links), strips any `#fragment`, resolves each
against the Markdown file's directory, and reports the ones that do not exist to `link_report.json`.

## How to use it
Pick a perk, copy `ledger.json` → `task-ledger.json`, fill its vars + `record_store`, then
validate → compose → compile → oversight → executor.
