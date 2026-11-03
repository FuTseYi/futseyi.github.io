"""Tests for deterministic blog content indexing."""
import tempfile
import unittest
from pathlib import Path

from blog_index import (
    build_index,
    check_index,
    extract_excerpt,
    extract_headings,
    extract_internal_links,
    render_index,
    write_index,
)


class BlogIndexTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / "index.html").write_text(
            '<link rel="canonical" href="https://example.org/">', encoding="utf-8"
        )
        self.posts = self.root / "posts"
        self.posts.mkdir()

    def tearDown(self):
        self.temporary.cleanup()

    def add_post(self, slug, title, day, tags, body):
        folder = self.posts / slug
        folder.mkdir()
        (folder / "index.md").write_text(
            f"---\ntitle: {title}\ndate: {day}\ntags: {tags}\n---\n\n{body}\n",
            encoding="utf-8",
        )

    def test_index_extracts_metadata_excerpt_headings_and_internal_links(self):
        self.add_post(
            "first-post",
            "First post",
            "2026-11-02",
            "Python, Tools, Python",
            "A useful introduction with **important context**.\n\n"
            "## Why it matters\n\n"
            "\x60\x60\x60python\n## Not a heading\n\x60\x60\x60\n\n"
            "Read [the next article](https://example.org/blog/second-post/). "
            "Ignore [an external page](https://other.example/blog/second-post/).",
        )
        self.add_post("second-post", "Second post", "2026-11-01", "Python", "A second article.")
        index = build_index(self.root)
        first = index["articles"][0]
        self.assertEqual(first["slug"], "first-post")
        self.assertEqual(first["tags"], ["Python", "Tools"])
        self.assertEqual(first["internal_links"], ["second-post"])
        self.assertEqual(first["excerpt"], "A useful introduction with important context.")
        self.assertEqual(first["headings"], [{"level": 2, "title": "Why it matters"}])
        self.assertEqual(index["schema_version"], 2)
        self.assertEqual(index["tags"][0], {
            "name": "Python", "count": 2, "articles": ["first-post", "second-post"]
        })

    def test_excerpt_skips_images_code_and_structural_blocks(self):
        excerpt = extract_excerpt(
            "# Heading\n\n"
            "![Decorative image](image.png)\n\n"
            "\x60\x60\x60python\nignored = True\n\x60\x60\x60\n\n"
            "- A list item is not an introduction.\n\n"
            "A **useful** paragraph with \x60inline code\x60 and a [reference](https://example.org).\n\n"
            "A later paragraph."
        )
        self.assertEqual(excerpt, "A useful paragraph with inline code and a reference.")

    def test_excerpt_supports_blockquotes_and_empty_articles(self):
        self.assertEqual(extract_excerpt("> A considered quotation.\n> A second line."), "A considered quotation. A second line.")
        self.assertEqual(extract_excerpt("\x60\x60\x60text\nOnly code.\n\x60\x60\x60\n"), "")

    def test_excerpt_truncates_at_a_word_boundary(self):
        excerpt = extract_excerpt("A useful paragraph with enough words to exceed the configured limit. " * 8)
        self.assertLessEqual(len(excerpt), 241)
        self.assertTrue(excerpt.endswith("…"))

    def test_headings_preserve_actual_levels_and_ignore_fenced_examples(self):
        headings = extract_headings(
            "## Overview\n\n### Details\n\n"
            "\x60\x60\x60markdown\n# Not a heading\n\x60\x60\x60\n\n"
            "Setext heading\n--------------\n\n"
            "## Heading with **emphasis** {#custom-id}\n"
        )
        self.assertEqual(
            headings,
            [
                {"level": 2, "title": "Overview"},
                {"level": 3, "title": "Details"},
                {"level": 2, "title": "Setext heading"},
                {"level": 2, "title": "Heading with emphasis"},
            ],
        )

    def test_internal_links_support_reference_links_and_ignore_code(self):
        source = (
            "Read [the article][target].\n\n"
            "[target]: https://example.org/blog/target-article/\n\n"
            "\x60\x60\x60html\n<a href='/blog/not-an-article/'>Example</a>\n\x60\x60\x60"
        )
        self.assertEqual(
            extract_internal_links(
                source,
                "source-article",
                {"source-article", "target-article"},
                "https://example.org",
            ),
            ["target-article"],
        )

    def test_index_is_deterministic_and_check_detects_stale_output(self):
        self.add_post("sample", "Sample", "2026-11-03", "Notes", "A sample paragraph.")
        expected = render_index(self.root)
        self.assertEqual(expected, render_index(self.root))
        write_index(self.root)
        check_index(self.root)
        (self.root / "BLOG_INDEX.json").write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "out of date"):
            check_index(self.root)

    def test_missing_index_and_invalid_json_are_reported(self):
        self.add_post("sample", "Sample", "2026-11-03", "Notes", "A sample paragraph.")
        with self.assertRaisesRegex(ValueError, "Missing BLOG_INDEX.json"):
            check_index(self.root)
        (self.root / "BLOG_INDEX.json").write_text("{", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "invalid JSON"):
            check_index(self.root)

    def test_articles_and_tags_have_stable_order(self):
        self.add_post("zeta", "Zeta", "2026-11-01", "Beta, Alpha", "Zeta body.")
        self.add_post("alpha", "Alpha", "2026-11-01", "Alpha", "Alpha body.")
        index = build_index(self.root)
        self.assertEqual([item["slug"] for item in index["articles"]], ["zeta", "alpha"])
        self.assertEqual([item["name"] for item in index["tags"]], ["Alpha", "Beta"])


if __name__ == "__main__":
    unittest.main()
