# Changelog

All notable changes to Reverb Wiki are documented here.

## [1.0.0] - 2026-11-01

Initial public release.

- Single-file flat-file personal wiki (`reverb_wiki.py`), Python standard
  library only — no dependencies, no build step.
- Pages stored as plain `.md` / `.txt` files in a user-owned directory.
- Local web UI on 127.0.0.1 (default port 8471): page view, edit view
  with save, page index, and full-text search with snippets.
- Hand-written minimal Markdown renderer: headings, paragraphs,
  bold/italic, inline code, fenced code blocks, lists, and links, with
  all raw HTML escaped.
- `[[WikiLinks]]` with automatic page creation — links to missing pages
  render distinctly and open the editor for that page.
- Filename slugification that keeps pages inside the pages directory.
- Starter Welcome page created on first run.
- Test suite (25 tests) covering the renderer, WikiLink extraction,
  page-store CRUD, search, and filename safety.
