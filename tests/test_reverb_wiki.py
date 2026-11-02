#!/usr/bin/env python3
"""Tests for Reverb Wiki (stdlib unittest only).

Run:  python3 -m unittest discover -s tests -v
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import reverb_wiki as rw


class TestSlugify(unittest.TestCase):
    def test_spaces_become_underscores(self):
        self.assertEqual(rw.slugify("Shopping List"), "Shopping_List")

    def test_strips_unsafe_characters(self):
        self.assertEqual(rw.slugify("../etc/passwd"), "etcpasswd")
        self.assertEqual(rw.slugify("a/b\\c"), "abc")

    def test_empty_becomes_untitled(self):
        self.assertEqual(rw.slugify("   "), "Untitled")
        self.assertEqual(rw.slugify(""), "Untitled")

    def test_unslug_round_trip(self):
        self.assertEqual(rw.unslug(rw.slugify("My Big Note")), "My Big Note")


class TestRenderer(unittest.TestCase):
    def render(self, text, exists=()):
        return rw.render_markdown(text, page_exists=lambda s: s in exists)

    def test_heading(self):
        self.assertIn("<h1>Hello</h1>", self.render("# Hello"))
        self.assertIn("<h3>Deep</h3>", self.render("### Deep"))

    def test_paragraph_and_bold_italic(self):
        out = self.render("Some **bold** and *italic* text.")
        self.assertIn("<strong>bold</strong>", out)
        self.assertIn("<em>italic</em>", out)
        self.assertIn("<p>", out)

    def test_html_is_escaped(self):
        out = self.render("<script>alert(1)</script>")
        self.assertNotIn("<script>", out)
        self.assertIn("&lt;script&gt;", out)

    def test_inline_code_protects_contents(self):
        out = self.render("Use `**not bold**` here.")
        self.assertIn("<code>**not bold**</code>", out)

    def test_fenced_code_block_escaped(self):
        out = self.render("```\nif a < b:\n    pass\n```")
        self.assertIn("<pre><code>", out)
        self.assertIn("a &lt; b", out)

    def test_unordered_list(self):
        out = self.render("- one\n- two")
        self.assertIn("<ul>", out)
        self.assertEqual(out.count("<li>"), 2)

    def test_ordered_list(self):
        out = self.render("1. first\n2. second")
        self.assertIn("<ol>", out)
        self.assertEqual(out.count("<li>"), 2)

    def test_markdown_link(self):
        out = self.render("See [Example](https://example.com) now.")
        self.assertIn('<a href="https://example.com">Example</a>', out)

    def test_wikilink_to_existing_page(self):
        out = self.render("Go to [[Ideas]]", exists={"Ideas"})
        self.assertIn('<a href="/page/Ideas">Ideas</a>', out)

    def test_wikilink_to_missing_page_points_at_edit(self):
        out = self.render("Go to [[New Page]]")
        self.assertIn('class="missing"', out)
        self.assertIn('href="/edit/New_Page"', out)

    def test_wikilink_with_label(self):
        out = self.render("See [[Ideas|my ideas]]", exists={"Ideas"})
        self.assertIn('<a href="/page/Ideas">my ideas</a>', out)


class TestExtractWikilinks(unittest.TestCase):
    def test_extracts_in_order(self):
        text = "Links: [[Alpha]], [[Beta Page]] and [[Alpha]] again."
        self.assertEqual(rw.extract_wikilinks(text),
                         ["Alpha", "Beta Page", "Alpha"])

    def test_no_links(self):
        self.assertEqual(rw.extract_wikilinks("plain text"), [])


class TestPageStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = rw.PageStore(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_create_and_read(self):
        self.store.write("First Page", "# First\n\nHello world.")
        self.assertTrue(self.store.exists("First Page"))
        self.assertEqual(self.store.read("First_Page"), "# First\n\nHello world.")

    def test_read_missing_returns_none(self):
        self.assertIsNone(self.store.read("Nope"))

    def test_update_overwrites(self):
        self.store.write("Note", "v1")
        self.store.write("Note", "v2")
        self.assertEqual(self.store.read("Note"), "v2")

    def test_delete(self):
        self.store.write("Temp", "x")
        self.assertTrue(self.store.delete("Temp"))
        self.assertFalse(self.store.exists("Temp"))
        self.assertFalse(self.store.delete("Temp"))

    def test_list_slugs_sorted(self):
        self.store.write("banana", "b")
        self.store.write("Apple", "a")
        self.store.write("cherry", "c")
        self.assertEqual(self.store.list_slugs(), ["Apple", "banana", "cherry"])

    def test_txt_files_are_pages_too(self):
        with open(os.path.join(self.tmp.name, "legacy.txt"), "w") as fh:
            fh.write("old note")
        self.assertTrue(self.store.exists("legacy"))
        self.assertEqual(self.store.read("legacy"), "old note")

    def test_search_finds_text_and_title(self):
        self.store.write("Recipes", "Best pancakes ever.")
        self.store.write("Chores", "Mow the lawn.")
        hits = self.store.search("pancakes")
        self.assertEqual([h["slug"] for h in hits], ["Recipes"])
        hits = self.store.search("RECIPES")
        self.assertEqual([h["slug"] for h in hits], ["Recipes"])
        self.assertEqual(self.store.search("zzzzz"), [])
        self.assertEqual(self.store.search(""), [])

    def test_traversal_cannot_escape_pages_dir(self):
        slug = self.store.write("../../evil", "nope")
        self.assertNotIn("/", slug)
        self.assertTrue(
            os.path.isfile(os.path.join(self.tmp.name, slug + ".md")))


if __name__ == "__main__":
    unittest.main()
