# Reverb Wiki

**A personal wiki that lives in plain text files you own.**

Reverb Wiki is a complete wiki in a single Python file. Your pages are
ordinary `.md` / `.txt` files in a folder on your own machine — readable
with any text editor, searchable with any tool, yours forever. Reverb Wiki
just gives them a friendly local web interface: read, edit, link, and
search your notes from a browser, with nothing leaving your computer.

No database. No build step. No accounts. No JavaScript frameworks.
Python's standard library is the only dependency.

## Why

The personal wiki tools a generation kept their notes in — small, local,
link-everything notebooks — were built on a good idea: *your notes should
be files, and files outlive apps.* Reverb Wiki revives that idea
local-first, with plain-text storage and zero dependencies. It is a
clean-room reimplementation in the Reverb line: written from scratch for
this release, no original code used.

## Quick start

Requires Python 3.8+.

```sh
python3 reverb_wiki.py
```

Then open <http://127.0.0.1:8471/> in your browser. A starter **Welcome**
page is created for you on first run.

## Usage

```sh
python3 reverb_wiki.py [--port PORT] [--pages DIR] [--host HOST]
```

| Flag      | Default     | Meaning                          |
|-----------|-------------|----------------------------------|
| `--port`  | `8471`      | Port to serve on                 |
| `--pages` | `./pages`   | Folder holding your page files   |
| `--host`  | `127.0.0.1` | Interface to bind (local only by default) |

Point `--pages` at an existing folder of `.md`/`.txt` files and they
become wiki pages immediately — the file name is the page title, with
underscores shown as spaces (`Shopping_List.md` → "Shopping List").

## Features

- **Plain-file storage** — every page is a `.md` or `.txt` file you can
  read, copy, back up, or version with any tool you like.
- **WikiLinks** — link pages together with `[[Page Title]]`. Links to
  pages that don't exist yet render in red; click one and you're writing
  that page.
- **Minimal Markdown** — headings, **bold**, *italic*, `code`, fenced
  code blocks, lists, and `[links](https://example.com)`. Raw HTML in a
  page is escaped, never executed.
- **Full-text search** — search box on every page, matching titles and
  page text with context snippets.
- **Page index and in-browser editing** — one click to the edit view,
  save, and you're back at the rendered page.
- **Single file, zero dependencies** — one `reverb_wiki.py`, Python
  standard library only. No external assets are loaded, ever.
- **Local by default** — binds to `127.0.0.1`; your wiki stays on your
  machine unless you deliberately choose otherwise.

## Tests

```sh
python3 -m unittest discover -s tests -v
```

The suite covers the Markdown renderer, WikiLink extraction, page-store
CRUD, search, and filename safety.

## License

MIT — see [LICENSE](LICENSE).

---

By **Dimon Global Group**. Part of the Reverb line: retired software
ideas, rebuilt from scratch for the tools of today.
