import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sitemap_site_downloader.core import PageParser, css_references, local_path_for_url, sitemap_locations
from sitemap_site_downloader.cli import valid_url


class CoreTests(unittest.TestCase):
    def test_markdown_link_input_is_cleaned(self):
        copied = "[https://x.test/sitemap.xml](https://x.test/sitemap.xml)"
        self.assertEqual(valid_url(copied), "https://x.test/sitemap.xml")

    def test_sitemap_index(self):
        kind, urls = sitemap_locations("<sitemapindex><sitemap><loc>https://x.test/a.xml</loc></sitemap></sitemapindex>")
        self.assertEqual(kind, "sitemapindex")
        self.assertEqual(urls, ["https://x.test/a.xml"])

    def test_urlset_with_namespace(self):
        kind, urls = sitemap_locations("<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'><url><loc>https://x.test/a/</loc></url></urlset>")
        self.assertEqual(kind, "urlset")
        self.assertEqual(urls, ["https://x.test/a/"])

    def test_page_parser_extracts_inventory_fields(self):
        parser = PageParser("https://x.test/page/")
        parser.feed("<html><head><title>Example</title><meta name='description' content='Desc'><link rel='canonical' href='/page/'></head><body><h1>Hello</h1><a href='/next/'>Next</a><img src='/a.jpg'></body></html>")
        self.assertEqual(" ".join(parser.title_parts), "Example")
        self.assertEqual(parser.meta_description, "Desc")
        self.assertEqual(parser.canonical, "https://x.test/page/")
        self.assertIn("https://x.test/a.jpg", parser.references)

    def test_local_paths_are_stable(self):
        self.assertEqual(local_path_for_url("https://x.test/about/", True).as_posix(), "about/index.html")
        self.assertEqual(local_path_for_url("https://x.test/about", True).as_posix(), "about.html")
        self.assertIn("__", local_path_for_url("https://x.test/app.js?v=2").name)

    def test_css_references(self):
        refs = css_references("body{background:url('../img/a.png')} @import 'theme.css';", "https://x.test/css/main.css")
        self.assertEqual(refs, {"https://x.test/img/a.png", "https://x.test/css/theme.css"})


if __name__ == "__main__":
    unittest.main()
