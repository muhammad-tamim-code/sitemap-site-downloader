# Sitemap Site Downloader

This tool downloads pages from a website sitemap.

Paste a sitemap URL. The tool will save the pages and website files on your computer. It will also make CSV files with page details.

## What you get

- `site/` has the saved website pages and files.
- `pages.csv` has the page URL, status code, title, description, canonical URL, robots tag, H1, word count, link count, file count and errors.
- `files.csv` shows each online URL and its saved file path.
- `summary.txt` shows the final totals.

## Run with Python

You need Python 3.11 or newer.

```powershell
py -3 run.py
```

The tool will ask for the sitemap URL.

You can also give the URL in the command:

```powershell
py -3 run.py https://example.com/sitemap.xml
```

Choose your own output folder:

```powershell
py -3 run.py https://example.com/sitemap.xml --output output/example
```

## Useful options

```text
--pages-only       Save pages but skip images, CSS and other files
--limit 500        Download up to 500 pages
--delay 0.5        Wait 0.5 seconds between requests
--timeout 45       Wait up to 45 seconds for each request
```

## Install as a terminal command

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
sitemap-site-downloader https://example.com/sitemap.xml
```

## Make a Windows EXE

```powershell
.\build_exe.ps1
```

The EXE will be inside the `dist` folder. You can also run the `build-windows` workflow on GitHub and download the EXE from the workflow result.

## Test the code

```powershell
py -3 -m unittest discover -s tests -v
```

## Limits

- It downloads pages found in the sitemap.
- It downloads files from the same website.
- It does not run JavaScript.
- It makes a static copy. Forms, login, search, cart and other server features will not work offline.
- Some complex websites may still need the live server.
- A website can block automated downloads. The tool will show a clear message when the sitemap is blocked.

Only download a website when you own it or have permission.
