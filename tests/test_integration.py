import csv
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sitemap_site_downloader.core import SiteDownloader


class SiteHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        origin = f"http://127.0.0.1:{self.server.server_port}"
        routes = {
            "/sitemap.xml": ("application/xml", f"<urlset><url><loc>{origin}/</loc></url><url><loc>{origin}/about/</loc></url></urlset>".encode()),
            "/": ("text/html", b"<html><head><title>Home</title><link rel='stylesheet' href='/assets/site.css'></head><body><h1>Home</h1><a href='/about/'>About</a><img src='/assets/logo.png'></body></html>"),
            "/about/": ("text/html", b"<html><head><title>About</title><meta name='description' content='About this test'></head><body><h1>About us</h1><a href='/'>Home</a></body></html>"),
            "/assets/site.css": ("text/css", b"body{background-image:url('/assets/bg.png')}") ,
            "/assets/logo.png": ("image/png", b"fake-logo"),
            "/assets/bg.png": ("image/png", b"fake-background"),
        }
        content_type, body = routes.get(self.path, ("text/plain", b"not found"))
        status = 200 if self.path in routes else 404
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass


class DownloaderIntegrationTests(unittest.TestCase):
    def test_downloads_pages_assets_and_csv_inventory(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), SiteHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as temp:
                output = Path(temp) / "archive"
                summary = SiteDownloader(
                    f"http://127.0.0.1:{server.server_port}/sitemap.xml",
                    output,
                    delay=0,
                ).run()
                self.assertEqual(summary["pages_saved"], 2)
                self.assertEqual(summary["assets_saved"], 3)
                self.assertTrue((output / "site" / "index.html").exists())
                self.assertTrue((output / "site" / "about" / "index.html").exists())
                self.assertTrue((output / "site" / "assets" / "bg.png").exists())
                with (output / "pages.csv").open(encoding="utf-8-sig") as handle:
                    rows = list(csv.DictReader(handle))
                self.assertEqual([row["title"] for row in rows], ["Home", "About"])
                home = (output / "site" / "index.html").read_text(encoding="utf-8")
                self.assertIn("assets/site.css", home)
                self.assertNotIn(f"127.0.0.1:{server.server_port}/about", home)
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
