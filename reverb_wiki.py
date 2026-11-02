#!/usr/bin/env python3
"""Reverb Wiki - a flat-file personal wiki in a single Python file.

Your pages are plain .md/.txt files in a folder you own. Reverb Wiki
serves them as a small local web app: read, edit, link, and search your
notes from any browser on your own machine. No database, no build step,
no external assets, no JavaScript frameworks - standard library only.

Usage:
    python3 reverb_wiki.py [--port 8471] [--pages ./pages] [--host 127.0.0.1]

By Dimon Global Group. MIT License.
"""

import argparse
import html
import os
import re
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DEFAULT_PORT = 8471
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PAGES_DIR = "./pages"

PAGE_EXTENSIONS = (".md", ".txt")

# ---------------------------------------------------------------------------
# Page naming
# ---------------------------------------------------------------------------

_SLUG_BAD_CHARS = re.compile(r"[^A-Za-z0-9_\-. ]+")


def slugify(title):
    """Turn a page title into a safe file slug.

    'My Note!' -> 'My_Note'. Strips anything that could escape the pages
    directory (slashes, dots-only names, control characters).
    """
    title = (title or "").strip()
    title = _SLUG_BAD_CHARS.sub("", title)
    title = title.replace(" ", "_")
    title = title.strip("._")
    return title or "Untitled"


def unslug(slug):
    """Turn a slug back into a display title."""
    return slug.replace("_", " ")


# ---------------------------------------------------------------------------
# Page store: plain files on disk
# ---------------------------------------------------------------------------


class PageStore:
    """CRUD over a directory of .md/.txt page files."""

    def __init__(self, pages_dir):
        self.pages_dir = pages_dir
        os.makedirs(self.pages_dir, exist_ok=True)

    def _path_for(self, slug):
        """Existing file path for a slug, or the default .md path."""
        for ext in PAGE_EXTENSIONS:
            candidate = os.path.join(self.pages_dir, slug + ext)
            if os.path.isfile(candidate):
                return candidate
        return os.path.join(self.pages_dir, slug + PAGE_EXTENSIONS[0])

    def exists(self, slug):
        slug = slugify(slug)
        return any(
            os.path.isfile(os.path.join(self.pages_dir, slug + ext))
            for ext in PAGE_EXTENSIONS
        )

    def read(self, slug):
        """Return page text, or None if the page does not exist."""
        slug = slugify(slug)
        path = self._path_for(slug)
        if not os.path.isfile(path):
            return None
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()

    def write(self, slug, text):
        """Create or overwrite a page. Returns the slug used."""
        slug = slugify(slug)
        path = self._path_for(slug)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return slug

    def delete(self, slug):
        slug = slugify(slug)
        path = self._path_for(slug)
        if os.path.isfile(path):
            os.remove(path)
            return True
        return False

    def list_slugs(self):
        """All page slugs, sorted case-insensitively."""
        slugs = []
        for name in os.listdir(self.pages_dir):
            base, ext = os.path.splitext(name)
            if ext in PAGE_EXTENSIONS and base:
                slugs.append(base)
        return sorted(set(slugs), key=str.lower)

    def search(self, query):
        """Case-insensitive substring search over titles and page text.

        Returns a list of dicts: slug, title, snippet.
        """
        query = (query or "").strip().lower()
        if not query:
            return []
        results = []
        for slug in self.list_slugs():
            text = self.read(slug) or ""
            title = unslug(slug)
            haystack = (title + "\n" + text).lower()
            if query not in haystack:
                continue
            flat = text.replace("\n", " ")
            fpos = flat.lower().find(query)
            if fpos == -1:
                snippet = flat[:100]
            else:
                s = max(0, fpos - 40)
                snippet = ("..." if s > 0 else "") + flat[s:fpos + len(query) + 60]
            results.append({"slug": slug, "title": title, "snippet": snippet})
        return results


# ---------------------------------------------------------------------------
# Minimal Markdown renderer (hand-written, escapes HTML)
# ---------------------------------------------------------------------------

_WIKILINK_RE = re.compile(r"\[\[([^\[\]]+)\]\]")
_FENCE_RE = re.compile(r"^```")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_UL_ITEM_RE = re.compile(r"^\s*[-*]\s+(.*)$")
_OL_ITEM_RE = re.compile(r"^\s*\d+[.)]\s+(.*)$")


def extract_wikilinks(text):
    """Return the raw titles inside [[...]] links, in order of appearance."""
    return [m.group(1).strip() for m in _WIKILINK_RE.finditer(text or "")]


def _inline(text, page_exists):
    """Render inline Markdown for one already-block-level chunk of text."""
    escaped = html.escape(text, quote=True)

    stash = []

    def keep(fragment):
        stash.append(fragment)
        return "\x00%d\x00" % (len(stash) - 1)

    # Inline code first so its contents are never re-interpreted.
    def code_sub(match):
        return keep("<code>%s</code>" % match.group(1))

    escaped = re.sub(r"`([^`]+)`", code_sub, escaped)

    # WikiLinks: [[Page Title]] or [[Page Title|label]]
    def wiki_sub(match):
        inner = match.group(1)
        if "|" in inner:
            target, label = inner.split("|", 1)
        else:
            target, label = inner, inner
        target = html.unescape(target).strip()
        label = label.strip()
        slug = slugify(target)
        if page_exists(slug):
            return keep('<a href="/page/%s">%s</a>' % (slug, label))
        return keep(
            '<a class="missing" href="/edit/%s" title="Create this page">%s</a>'
            % (slug, label)
        )

    escaped = _WIKILINK_RE.sub(wiki_sub, escaped)

    # Ordinary links [label](url) - http(s), mailto, and local paths only.
    def link_sub(match):
        label, url = match.group(1), match.group(2)
        if re.match(r"^(https?://|mailto:|/|#)", url):
            return keep('<a href="%s">%s</a>' % (url, label))
        return keep(label)

    escaped = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", link_sub, escaped)

    # Bold, then italic.
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"__([^_]+)__", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", escaped)
    escaped = re.sub(r"(?<![\w])_([^_]+)_(?![\w])", r"<em>\1</em>", escaped)

    for index, fragment in enumerate(stash):
        escaped = escaped.replace("\x00%d\x00" % index, fragment)
    return escaped


def render_markdown(text, page_exists=None):
    """Render a small, safe subset of Markdown to HTML.

    Supports headings, paragraphs, bold/italic, inline code, fenced code
    blocks, unordered/ordered lists, links, and [[WikiLinks]].
    All raw HTML in the source is escaped.
    """
    if page_exists is None:
        page_exists = lambda slug: False  # noqa: E731

    lines = (text or "").split("\n")
    out = []
    paragraph = []
    list_items = []
    list_tag = None
    in_code = False
    code_lines = []

    def flush_paragraph():
        if paragraph:
            out.append("<p>%s</p>" % _inline(" ".join(paragraph), page_exists))
            paragraph.clear()

    def flush_list():
        nonlocal list_tag
        if list_items:
            out.append("<%s>" % list_tag)
            for item in list_items:
                out.append("<li>%s</li>" % _inline(item, page_exists))
            out.append("</%s>" % list_tag)
            list_items.clear()
            list_tag = None

    for line in lines:
        if _FENCE_RE.match(line):
            if in_code:
                out.append(
                    "<pre><code>%s</code></pre>"
                    % html.escape("\n".join(code_lines))
                )
                code_lines = []
                in_code = False
            else:
                flush_paragraph()
                flush_list()
                in_code = True
            continue
        if in_code:
            code_lines.append(line)
            continue

        heading = _HEADING_RE.match(line)
        if heading:
            flush_paragraph()
            flush_list()
            level = len(heading.group(1))
            out.append(
                "<h%d>%s</h%d>"
                % (level, _inline(heading.group(2).strip(), page_exists), level)
            )
            continue

        ul = _UL_ITEM_RE.match(line)
        ol = _OL_ITEM_RE.match(line)
        if ul or ol:
            flush_paragraph()
            tag = "ul" if ul else "ol"
            if list_tag != tag:
                flush_list()
                list_tag = tag
            list_items.append((ul or ol).group(1).strip())
            continue

        if not line.strip():
            flush_paragraph()
            flush_list()
            continue

        flush_list()
        paragraph.append(line.strip())

    if in_code:  # unterminated fence: still emit what we collected
        out.append("<pre><code>%s</code></pre>" % html.escape("\n".join(code_lines)))
    flush_paragraph()
    flush_list()
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Web UI
# ---------------------------------------------------------------------------

STYLE = """
body { font-family: Georgia, 'Times New Roman', serif; margin: 0; background: #faf8f3; color: #222; }
header { background: #2f3b2f; color: #f2efe6; padding: 0.7rem 1rem; }
header a { color: #f2efe6; text-decoration: none; font-weight: bold; }
header form { display: inline-block; margin-left: 1rem; }
main { max-width: 46rem; margin: 0 auto; padding: 1.2rem 1rem 3rem; }
a { color: #205c40; }
a.missing { color: #a33; border-bottom: 1px dashed #a33; }
pre { background: #eee9dc; padding: 0.8rem; overflow-x: auto; }
code { background: #eee9dc; padding: 0.1rem 0.3rem; }
pre code { padding: 0; }
textarea { width: 100%; min-height: 22rem; font-family: monospace; font-size: 0.95rem; }
input[type=text] { padding: 0.3rem; }
button, input[type=submit] { padding: 0.4rem 0.9rem; cursor: pointer; }
.meta { color: #666; font-size: 0.9rem; }
ul.pages { line-height: 1.7; }
""".strip()


def page_shell(title, body, query=""):
    return (
        "<!DOCTYPE html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        "<title>%s - Reverb Wiki</title><style>%s</style></head><body>"
        "<header><a href=\"/\">Reverb Wiki</a>"
        "<form method=\"get\" action=\"/search\">"
        "<input type=\"text\" name=\"q\" value=\"%s\" placeholder=\"Search pages\">"
        "<input type=\"submit\" value=\"Search\"></form></header>"
        "<main>%s</main></body></html>"
        % (html.escape(title), STYLE, html.escape(query, quote=True), body)
    )


def index_body(store):
    slugs = store.list_slugs()
    if slugs:
        items = "".join(
            '<li><a href="/page/%s">%s</a></li>'
            % (slug, html.escape(unslug(slug)))
            for slug in slugs
        )
        listing = '<ul class="pages">%s</ul>' % items
    else:
        listing = "<p>No pages yet. Create the first one below.</p>"
    return (
        "<h1>All pages</h1>%s"
        "<h2>New page</h2>"
        "<form method=\"get\" action=\"/new\">"
        "<input type=\"text\" name=\"title\" placeholder=\"Page title\">"
        "<input type=\"submit\" value=\"Create\"></form>" % listing
    )


def view_body(store, slug):
    text = store.read(slug)
    title = unslug(slug)
    rendered = render_markdown(text, page_exists=store.exists)
    return (
        "<h1>%s</h1>%s"
        "<p class=\"meta\"><a href=\"/edit/%s\">Edit this page</a> &middot; "
        "<a href=\"/\">All pages</a></p>" % (html.escape(title), rendered, slug)
    )


def edit_body(store, slug):
    text = store.read(slug)
    title = unslug(slug)
    if text is None:
        text = "# %s\n\n" % title
        note = "<p class=\"meta\">This page does not exist yet. Write it and save.</p>"
    else:
        note = ""
    return (
        "<h1>Edit: %s</h1>%s"
        "<form method=\"post\" action=\"/save/%s\">"
        "<textarea name=\"content\">%s</textarea><br>"
        "<input type=\"submit\" value=\"Save page\"></form>"
        "<p class=\"meta\"><a href=\"/\">All pages</a></p>"
        % (html.escape(title), note, slug, html.escape(text))
    )


def search_body(store, query):
    results = store.search(query)
    if not query:
        inner = "<p>Enter a search term above.</p>"
    elif not results:
        inner = "<p>No pages match <strong>%s</strong>.</p>" % html.escape(query)
    else:
        items = "".join(
            '<li><a href="/page/%s">%s</a><br><span class="meta">%s</span></li>'
            % (r["slug"], html.escape(r["title"]), html.escape(r["snippet"]))
            for r in results
        )
        inner = "<ul>%s</ul>" % items
    return "<h1>Search</h1>%s" % inner


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------


class WikiHandler(BaseHTTPRequestHandler):
    store = None  # set by serve()
    server_version = "ReverbWiki/1.0"

    def log_message(self, fmt, *args):  # keep the console quiet-ish
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _send_html(self, body_html, status=200):
        data = body_html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _redirect(self, location):
        self.send_response(303)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _route_parts(self):
        parsed = urllib.parse.urlparse(self.path)
        parts = [p for p in parsed.path.split("/") if p != ""]
        query = urllib.parse.parse_qs(parsed.query)
        return parts, query

    def do_GET(self):
        parts, query = self._route_parts()
        store = self.store
        if not parts:
            self._send_html(page_shell("All pages", index_body(store)))
            return
        if parts[0] == "page" and len(parts) == 2:
            slug = slugify(urllib.parse.unquote(parts[1]))
            if store.exists(slug):
                self._send_html(page_shell(unslug(slug), view_body(store, slug)))
            else:
                self._redirect("/edit/%s" % slug)
            return
        if parts[0] == "edit" and len(parts) == 2:
            slug = slugify(urllib.parse.unquote(parts[1]))
            self._send_html(page_shell("Edit", edit_body(store, slug)))
            return
        if parts[0] == "new":
            title = query.get("title", [""])[0]
            self._redirect("/edit/%s" % slugify(title))
            return
        if parts[0] == "search":
            q = query.get("q", [""])[0]
            self._send_html(page_shell("Search", search_body(store, q), query=q))
            return
        self._send_html(page_shell("Not found", "<h1>404</h1><p>Not found.</p>"), 404)

    def do_POST(self):
        parts, _query = self._route_parts()
        if parts and parts[0] == "save" and len(parts) == 2:
            slug = slugify(urllib.parse.unquote(parts[1]))
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length).decode("utf-8") if length else ""
            fields = urllib.parse.parse_qs(raw)
            content = fields.get("content", [""])[0]
            self.store.write(slug, content)
            self._redirect("/page/%s" % slug)
            return
        self._send_html(page_shell("Not found", "<h1>404</h1><p>Not found.</p>"), 404)


WELCOME_PAGE = """# Welcome

This is your new wiki. Pages are plain text files in the pages folder,
so your notes are always yours - readable with any text editor, forever.

## Getting started

- Click **Edit this page** above and write something.
- Link to another page with double brackets, like [[Ideas]] or
  [[Shopping List]]. Links to pages that do not exist yet show in red;
  click one to create that page.
- Use the search box at the top to find anything.

## Formatting

Headings, **bold**, *italic*, `code`, lists, and links all work:

- plain [Markdown links](https://example.com) work too
- fenced code blocks keep your snippets readable

```
print("hello, wiki")
```
"""


def serve(pages_dir, host, port):
    store = PageStore(pages_dir)
    if not store.list_slugs():
        store.write("Welcome", WELCOME_PAGE)
    WikiHandler.store = store
    server = ThreadingHTTPServer((host, port), WikiHandler)
    print("Reverb Wiki serving %s at http://%s:%d/ (Ctrl+C to stop)"
          % (os.path.abspath(pages_dir), host, port))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Reverb Wiki - a flat-file personal wiki (single file, stdlib only)."
    )
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help="port to serve on (default %d)" % DEFAULT_PORT)
    parser.add_argument("--host", default=DEFAULT_HOST,
                        help="interface to bind (default %s)" % DEFAULT_HOST)
    parser.add_argument("--pages", default=DEFAULT_PAGES_DIR,
                        help="pages directory (default %s)" % DEFAULT_PAGES_DIR)
    args = parser.parse_args(argv)
    serve(args.pages, args.host, args.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
