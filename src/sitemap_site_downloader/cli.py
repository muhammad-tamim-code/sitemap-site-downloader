from __future__ import annotations

import argparse
import os
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from .core import SiteDownloader


def pause_before_close(interactive: bool) -> None:
    if interactive:
        try:
            input("Press Enter to close...")
        except EOFError:
            pass


def valid_url(value: str) -> str:
    value = value.strip()
    markdown_link = re.fullmatch(r"\[[^\]]+\]\((https?://[^)]+)\)", value, flags=re.I)
    if markdown_link:
        value = markdown_link.group(1)
    value = value.strip("<>")
    if not value:
        raise argparse.ArgumentTypeError("A sitemap URL is required.")
    if not urlparse(value).scheme:
        value = "https://" + value
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise argparse.ArgumentTypeError("Enter a valid http or https sitemap URL.")
    return value


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Download every page in an XML sitemap and create CSV inventories.")
    result.add_argument("sitemap", nargs="?", type=valid_url, help="XML sitemap or sitemap-index URL")
    result.add_argument("--output", type=Path, help="Output directory")
    result.add_argument("--limit", type=int, default=5000, help="Maximum page URLs (default: 5000)")
    result.add_argument("--timeout", type=float, default=30, help="Per-request timeout in seconds")
    result.add_argument("--delay", type=float, default=0.15, help="Delay between requests in seconds")
    result.add_argument("--pages-only", action="store_true", help="Save HTML pages without downloading assets")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    sitemap = args.sitemap
    interactive = not sitemap
    if not sitemap:
        print("Sitemap Site Downloader")
        try:
            sitemap = valid_url(input("Paste the XML sitemap URL: "))
        except (argparse.ArgumentTypeError, EOFError) as exc:
            print(f"Error: {exc}")
            pause_before_close(interactive)
            return 1
    host = re.sub(r"[^A-Za-z0-9.-]+", "_", urlparse(sitemap).hostname or "website")
    output = args.output or Path("output") / f"{host}_{datetime.now():%Y%m%d_%H%M%S}"
    try:
        summary = SiteDownloader(sitemap, output, args.timeout, max(args.delay, 0), max(args.limit, 1), not args.pages_only).run()
    except (RuntimeError, ValueError) as exc:
        print(f"Error: {exc}")
        pause_before_close(interactive)
        return 1
    print("\nDownload complete")
    for key, value in summary.items():
        print(f"  {key}: {value}")
    if interactive:
        if os.name == "nt":
            os.startfile(output.resolve())
    pause_before_close(interactive)
    return 0
