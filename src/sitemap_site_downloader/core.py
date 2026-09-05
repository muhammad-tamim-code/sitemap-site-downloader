from __future__ import annotations

import csv
import gzip
import hashlib
import html as html_module
import mimetypes
import os
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse, urlunparse
from urllib.request import Request, urlopen


USER_AGENT = "SitemapSiteDownloader/0.1 (+local website archive)"
HTML_ATTRS = {"href", "src", "srcset", "poster", "data-src", "data-lazy-src"}
SKIP_SCHEMES = ("data:", "mailto:", "tel:", "javascript:", "#")
DOWNLOADABLE_LINK_SUFFIXES = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".csv", ".zip", ".xml", ".json"
}


@dataclass
class FetchResult:
    requested_url: str
    final_url: str
    status: int
    content_type: str
    body: bytes
    error: str = ""


@dataclass
class PageRecord:
    url: str
    final_url: str = ""
    status: int = 0
    content_type: str = ""
    saved_path: str = ""
    title: str = ""
    meta_description: str = ""
    canonical: str = ""
    robots: str = ""
    h1: str = ""
    word_count: int = 0
    internal_link_count: int = 0
    asset_count: int = 0
    bytes: int = 0
    error: str = ""


class PageParser(HTMLParser):
    def __init__(self, page_url: str):
        super().__init__(convert_charrefs=True)
        self.page_url = page_url
        self.title_parts: list[str] = []
        self.h1_parts: list[str] = []
        self.text_parts: list[str] = []
        self.references: set[str] = set()
        self.links: set[str] = set()
        self.meta_description = ""
        self.canonical = ""
        self.robots = ""
        self._in_title = False
        self._in_h1 = False
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {key.lower(): value or "" for key, value in attrs}
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "template"}:
            self._ignored_depth += 1
        if tag == "title":
            self._in_title = True
        if tag == "h1":
            self._in_h1 = True
        if tag == "meta":
            name = attrs_dict.get("name", "").lower()
            if name == "description" and not self.meta_description:
                self.meta_description = attrs_dict.get("content", "").strip()
            if name in {"robots", "googlebot"}:
                self.robots = attrs_dict.get("content", "").strip()
        if tag == "link" and "canonical" in attrs_dict.get("rel", "").lower().split():
            self.canonical = urljoin(self.page_url, attrs_dict.get("href", ""))
        for name, value in attrs:
            if not value or name.lower() not in HTML_ATTRS:
                continue
            candidates = [part.strip().split()[0] for part in value.split(",")] if name.lower() == "srcset" else [value]
            for candidate in candidates:
                normalized = normalize_reference(candidate, self.page_url)
                if not normalized:
                    continue
                self.references.add(normalized)
                if tag == "a" and name.lower() == "href":
                    self.links.add(normalized)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "title":
            self._in_title = False
        if tag == "h1":
            self._in_h1 = False
        if tag in {"script", "style", "noscript", "template"} and self._ignored_depth:
            self._ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        cleaned = " ".join(data.split())
        if not cleaned:
            return
        if self._in_title:
            self.title_parts.append(cleaned)
        if self._in_h1:
            self.h1_parts.append(cleaned)
        if not self._ignored_depth:
            self.text_parts.append(cleaned)


def normalize_reference(value: str, base_url: str) -> str:
    value = html_module.unescape(value.strip())
    if not value or value.lower().startswith(SKIP_SCHEMES):
        return ""
    parsed = urlparse(urljoin(base_url, value))
    if parsed.scheme not in {"http", "https"}:
        return ""
    return urlunparse(parsed._replace(fragment=""))


def same_site(url: str, origin_url: str) -> bool:
    left = urlparse(url).hostname or ""
    right = urlparse(origin_url).hostname or ""
    return left.lower().removeprefix("www.") == right.lower().removeprefix("www.")


def local_path_for_url(url: str, is_page: bool = False) -> Path:
    parsed = urlparse(url)
    raw_path = parsed.path or "/"
    path = PurePosixPath(raw_path)
    safe_parts = [re.sub(r"[^A-Za-z0-9._-]+", "_", part) for part in path.parts if part not in {"/", "", ".", ".."}]
    if is_page:
        if raw_path.endswith("/") or not safe_parts:
            safe_parts.append("index.html")
        elif "." not in safe_parts[-1]:
            safe_parts[-1] += ".html"
    elif not safe_parts:
        safe_parts = ["asset"]
    if parsed.query:
        digest = hashlib.sha1(parsed.query.encode("utf-8")).hexdigest()[:10]
        stem = Path(safe_parts[-1]).stem
        suffix = Path(safe_parts[-1]).suffix
        safe_parts[-1] = f"{stem}__{digest}{suffix}"
    return Path(*safe_parts)


def fetch(url: str, timeout: float, user_agent: str = USER_AGENT) -> FetchResult:
    request = Request(url, headers={"User-Agent": user_agent, "Accept": "*/*"})
    try:
        with urlopen(request, timeout=timeout) as response:
            return FetchResult(
                requested_url=url,
                final_url=response.geturl(),
                status=getattr(response, "status", 200),
                content_type=response.headers.get_content_type(),
                body=response.read(),
            )
    except HTTPError as exc:
        body = exc.read() if exc.fp else b""
        return FetchResult(url, exc.geturl(), exc.code, exc.headers.get_content_type() if exc.headers else "", body, str(exc))
    except (URLError, TimeoutError, OSError) as exc:
        return FetchResult(url, url, 0, "", b"", str(exc))


def decode_text(body: bytes, content_type: str = "") -> str:
    if content_type.endswith("gzip") or body[:2] == b"\x1f\x8b":
        body = gzip.decompress(body)
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return body.decode(encoding)
        except UnicodeDecodeError:
            pass
    return body.decode("utf-8", errors="replace")


def sitemap_locations(xml_text: str) -> tuple[str, list[str]]:
    root = ET.fromstring(xml_text)
    root_name = root.tag.rsplit("}", 1)[-1].lower()
    locations = [node.text.strip() for node in root.iter() if node.tag.rsplit("}", 1)[-1].lower() == "loc" and node.text]
    return root_name, locations


def collect_sitemap_urls(sitemap_url: str, timeout: float, limit: int, delay: float) -> list[str]:
    pending = [sitemap_url]
    seen_sitemaps: set[str] = set()
    pages: list[str] = []
    page_seen: set[str] = set()
    while pending:
        current = pending.pop(0)
        if current in seen_sitemaps:
            continue
        seen_sitemaps.add(current)
        result = fetch(current, timeout)
        if not result.body or result.status >= 400 or result.status == 0:
            raise RuntimeError(f"Could not read sitemap {current}: HTTP {result.status} {result.error}".strip())
        root_name, locations = sitemap_locations(decode_text(result.body, result.content_type))
        if root_name == "sitemapindex":
            pending.extend(urljoin(current, location) for location in locations if urljoin(current, location) not in seen_sitemaps)
        else:
            for location in locations:
                absolute = normalize_reference(location, current)
                if absolute and absolute not in page_seen:
                    page_seen.add(absolute)
                    pages.append(absolute)
                    if len(pages) >= limit:
                        return pages
        if delay:
            time.sleep(delay)
    return pages


def css_references(css: str, base_url: str) -> set[str]:
    output: set[str] = set()
    for match in re.finditer(r"url\(\s*(['\"]?)(.*?)\1\s*\)", css, flags=re.I):
        normalized = normalize_reference(match.group(2), base_url)
        if normalized:
            output.add(normalized)
    for match in re.finditer(r"@import\s+(?:url\()?\s*['\"]([^'\"]+)", css, flags=re.I):
        normalized = normalize_reference(match.group(1), base_url)
        if normalized:
            output.add(normalized)
    return output


def replace_references(text: str, source_url: str, source_path: Path, mapping: dict[str, Path]) -> str:
    for remote, target in sorted(mapping.items(), key=lambda item: len(item[0]), reverse=True):
        relative = Path(".") if source_path.parent == Path("") else source_path.parent
        local = Path(target)
        try:
            rel = Path(os.path.relpath(local, relative)).as_posix()
        except ValueError:
            continue
        candidates = {remote}
        parsed = urlparse(remote)
        if same_site(remote, source_url):
            candidates.add(urlunparse(parsed._replace(scheme="", netloc="")))
        for candidate in sorted(candidates, key=len, reverse=True):
            if not candidate:
                continue
            if candidate == "/":
                for wrapped in (f"'{candidate}'", f'"{candidate}"', f"({candidate})"):
                    text = text.replace(wrapped, wrapped[0] + rel + wrapped[-1])
                continue
            text = text.replace(candidate, rel)
    return text


class SiteDownloader:
    def __init__(self, sitemap_url: str, output_dir: Path, timeout: float = 30, delay: float = 0.15, limit: int = 5000, assets: bool = True):
        self.sitemap_url = sitemap_url
        self.output_dir = output_dir
        self.timeout = timeout
        self.delay = delay
        self.limit = limit
        self.download_assets = assets
        self.site_dir = output_dir / "site"
        self.page_records: list[PageRecord] = []
        self.mapping: dict[str, Path] = {}
        self.text_files: dict[str, tuple[Path, str]] = {}
        self.asset_queue: list[str] = []
        self.asset_seen: set[str] = set()

    def run(self) -> dict[str, int | str]:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.site_dir.mkdir(parents=True, exist_ok=True)
        urls = collect_sitemap_urls(self.sitemap_url, self.timeout, self.limit, self.delay)
        if not urls:
            raise RuntimeError("The sitemap did not contain any page URLs.")
        origin = urls[0]
        print(f"Found {len(urls)} page URLs.")
        for index, url in enumerate(urls, 1):
            self._download_page(url, origin, index, len(urls))
            if self.delay:
                time.sleep(self.delay)
        if self.download_assets:
            self._download_queued_assets(origin)
        self._rewrite_text_files()
        self._write_inventory()
        summary = {
            "sitemap": self.sitemap_url,
            "pages_found": len(urls),
            "pages_saved": sum(bool(row.saved_path) for row in self.page_records),
            "page_errors": sum(bool(row.error) for row in self.page_records),
            "assets_saved": len({path for path in self.mapping.values()}) - sum(bool(row.saved_path) for row in self.page_records),
            "output": str(self.output_dir.resolve()),
        }
        (self.output_dir / "summary.txt").write_text("\n".join(f"{key}: {value}" for key, value in summary.items()) + "\n", encoding="utf-8")
        return summary

    def _download_page(self, url: str, origin: str, index: int, total: int) -> None:
        result = fetch(url, self.timeout)
        record = PageRecord(url=url, final_url=result.final_url, status=result.status, content_type=result.content_type, bytes=len(result.body), error=result.error)
        if result.body and result.status < 400:
            local = local_path_for_url(result.final_url, is_page=True)
            target = self.site_dir / local
            target.parent.mkdir(parents=True, exist_ok=True)
            text = decode_text(result.body, result.content_type)
            parser = PageParser(result.final_url)
            try:
                parser.feed(text)
            except Exception as exc:
                record.error = f"HTML parse warning: {exc}"
            record.saved_path = str(Path("site") / local)
            record.title = " ".join(parser.title_parts)
            record.meta_description = parser.meta_description
            record.canonical = parser.canonical
            record.robots = parser.robots
            record.h1 = " | ".join(parser.h1_parts)
            record.word_count = len(re.findall(r"\b\w+\b", " ".join(parser.text_parts), flags=re.UNICODE))
            record.internal_link_count = sum(same_site(link, origin) for link in parser.links)
            downloadable_links = {
                link for link in parser.links
                if Path(urlparse(link).path).suffix.lower() in DOWNLOADABLE_LINK_SUFFIXES
            }
            assets = {
                ref for ref in parser.references
                if same_site(ref, origin) and (ref not in parser.links or ref in downloadable_links)
            }
            record.asset_count = len(assets)
            self.asset_queue.extend(sorted(assets))
            self.mapping[url] = local
            self.mapping[result.final_url] = local
            self.text_files[result.final_url] = (local, text)
        self.page_records.append(record)
        print(f"[{index}/{total}] HTTP {record.status}: {url}")

    def _download_queued_assets(self, origin: str) -> None:
        while self.asset_queue:
            url = self.asset_queue.pop(0)
            if url in self.asset_seen or not same_site(url, origin):
                continue
            self.asset_seen.add(url)
            result = fetch(url, self.timeout)
            if not result.body or result.status >= 400 or result.status == 0:
                continue
            local = local_path_for_url(result.final_url)
            if not local.suffix:
                guessed = mimetypes.guess_extension(result.content_type or "") or ""
                local = local.with_suffix(guessed)
            target = self.site_dir / local
            target.parent.mkdir(parents=True, exist_ok=True)
            self.mapping[url] = local
            self.mapping[result.final_url] = local
            if result.content_type in {"text/css", "application/javascript", "text/javascript"}:
                text = decode_text(result.body, result.content_type)
                self.text_files[result.final_url] = (local, text)
                if result.content_type == "text/css":
                    self.asset_queue.extend(sorted(css_references(text, result.final_url)))
            else:
                target.write_bytes(result.body)
            if self.delay:
                time.sleep(self.delay)

    def _rewrite_text_files(self) -> None:
        for url, (local, text) in self.text_files.items():
            rewritten = replace_references(text, url, local, self.mapping)
            target = self.site_dir / local
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(rewritten, encoding="utf-8", errors="replace")

    def _write_inventory(self) -> None:
        fields = list(asdict(PageRecord(url="")).keys())
        with (self.output_dir / "pages.csv").open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(asdict(record) for record in self.page_records)
        with (self.output_dir / "files.csv").open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["url", "local_path"])
            writer.writeheader()
            writer.writerows({"url": url, "local_path": str(Path("site") / path)} for url, path in sorted(self.mapping.items()))
