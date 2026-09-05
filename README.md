# Sitemap Site Downloader

Download every page listed in an XML sitemap, save a local website copy, and export page and file inventories as CSV. Sitemap indexes and gzip-compressed sitemaps are supported.

## What the tool produces

- `site/`: downloaded HTML and same-site assets
- `pages.csv`: one row per sitemap page, including status, title, description, canonical, robots, H1, word count, links, assets and errors
- `files.csv`: remote URL to local-file mapping
- `summary.txt`: totals and output location

The result is a static archive. Forms, logins, APIs, search, carts and other server-side behaviour do not become functional offline. JavaScript-rendered content may be absent because version 0.1 downloads HTTP responses rather than running a browser.

## Run from Python

```powershell
py -3 run.py
```

Paste the sitemap URL when prompted. You can also run it without prompts:

```powershell
py -3 run.py https://example.com/sitemap_index.xml --output output/example
```

When launched without arguments (including by double-clicking the Windows executable), the output folder opens automatically and the terminal remains open until you press Enter.

Useful options:

```text
--pages-only       Skip images, stylesheets, scripts and other assets
--limit 500        Stop after 500 page URLs
--delay 0.5        Wait half a second between requests
--timeout 45       Allow 45 seconds per request
```

Run only on websites you own or are authorized to archive. Review the site's terms and use a sensible delay.

## Install as a terminal command

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
sitemap-site-downloader https://example.com/sitemap.xml
```

## Build a Windows executable

```powershell
.\build_exe.ps1
```

The executable will be created in `dist/`. Building locally keeps the published Git repository small and allows users to verify the source.

After publishing to GitHub, the `build-windows` Actions workflow can also build a downloadable Windows executable artifact on demand.

## Test

```powershell
py -3 -m unittest discover -s tests -v
```

## Current limitations

- The sitemap defines page coverage. Unlisted pages are not discovered automatically.
- Assets are limited to the same hostname and references found in HTML or CSS.
- Version 0.1 does not execute JavaScript.
- URL rewriting is designed for ordinary static assets and links; complex JavaScript applications may still depend on the live server.
