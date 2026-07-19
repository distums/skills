# Obscura CLI Reference

This reference is derived from `D:/repository/obscura/readme.md` and intentionally covers only direct CLI fetching and scraping.

## Contents

- Availability and help
- Global options
- Fetch one URL
- Scrape multiple URLs
- Extraction and output patterns
- Dynamic pages and limits
- Supported values
- Command construction checklist

## Availability and Help

Check the installed command before relying on bundled documentation:

```sh
obscura --help
obscura fetch --help
obscura scrape --help
```

If the executable is missing, report that fact. Do not install it without user approval.

## Global Options

Place global options before the subcommand.

### Proxy

Obscura accepts HTTP and SOCKS proxy URLs:

```sh
obscura --proxy socks5://127.0.0.1:1080 fetch "https://example.com" --dump text
obscura --proxy http://127.0.0.1:8080 scrape "https://example.com" "https://news.ycombinator.com"
```

All `scrape` workers inherit the global proxy. Keep credentials out of displayed commands and logs; use an environment or secret mechanism appropriate to the user's shell.

### V8 flags

Pass raw V8 flags through `--v8-flags`. Raise the heap cap only after a real memory failure:

```sh
obscura --v8-flags "--max-old-space-size=4096" fetch "https://example.com"
```

The value is in MiB. A larger heap may allow a JavaScript-heavy page to complete but increases possible peak memory.

## Fetch One URL

Syntax:

```text
obscura fetch <URL> [OPTIONS]
```

| Flag | Default | Meaning |
|---|---|---|
| `--dump` | `html` | Output `html`, `text`, `links`, `markdown`, `assets`, or `original` |
| `--eval` | none | Evaluate a JavaScript expression |
| `--wait-until` | `load` | Wait for `load`, `domcontentloaded`, or `networkidle0` |
| `--timeout` | `30` | Maximum navigation time in seconds |
| `--selector` | none | Wait for a CSS selector |
| `--stealth` | off | Enable anti-detection mode |
| `--output` | none | Write dump or evaluation output to a file |
| `--quiet` | off | Suppress the banner |
| `--proxy` | none | Inherited global HTTP/SOCKS5 proxy URL |

Examples:

```sh
obscura fetch "https://example.com" --eval "document.title"
obscura fetch "https://example.com" --dump links
obscura fetch "https://news.ycombinator.com" --dump html
obscura fetch "https://example.com" --wait-until networkidle0
obscura fetch "https://example.com" --selector "main article" --timeout 20 --dump markdown --output "article.md"
```

## Scrape Multiple URLs

Release archives include both `obscura` and `obscura-worker`; keep them in the same directory for parallel `scrape`.

Syntax:

```text
obscura scrape <URL...> [OPTIONS]
```

| Flag | Default | Meaning |
|---|---|---|
| `--concurrency` | `10` | Number of parallel workers |
| `--eval` | none | JavaScript expression evaluated per page |
| `--format` | `json` | Output `json` or `text` |
| `--quiet` | off | Suppress progress on stderr |
| `--proxy` | none | Inherited global proxy for all workers |

Example:

```sh
obscura --proxy socks5://127.0.0.1:1080 scrape "https://example.test/a" "https://example.test/b" "https://example.test/c" --concurrency 5 --eval "document.querySelector('h1')?.textContent" --format json --quiet
```

`scrape` does not document `--selector`, `--timeout`, or `--output`. Do not borrow `fetch` flags for batch commands.

## Extraction and Output Patterns

### Raw or binary response

`original` streams the response body verbatim and bypasses the JavaScript/DOM layer. Prefer `--output` when shell redirection might transcode bytes:

```sh
obscura fetch "https://example.test/photo.png" --dump original --output "photo.png"
```

Binary-safe redirection is also valid when the shell guarantees raw bytes:

```sh
obscura fetch "https://picsum.photos/200/300" --dump original > photo.jpg
```

### Page assets

`assets` lists every sub-resource URL the page would fetch. Output is NDJSON with one record per asset:

```sh
obscura fetch "https://example.com" --dump assets
```

### Targeted JavaScript extraction

Use an expression that returns serializable data:

```sh
obscura fetch "https://example.com" --eval "Array.from(document.querySelectorAll('a'), a => ({ text: a.textContent.trim(), href: a.href }))" --output "links.json"
```

## Dynamic Pages and Limits

### Known element

Use `--selector` when a stable element identifies readiness:

```sh
obscura fetch "https://example.com/app" --selector "main[data-ready='true']" --timeout 30 --dump text
```

### Lifecycle or network completion

Use `--wait-until domcontentloaded` for DOM readiness or `networkidle0` for pages whose relevant network activity eventually stops. Avoid `networkidle0` on pages with permanent polling or streaming.

### Heavy SPA script budget

The default script-execution budget is 30 seconds. Increase it for a genuinely heavy React, Vue, or Angular application and keep the navigation timeout aligned.

POSIX shell:

```sh
OBSCURA_SCRIPT_DEADLINE_MS=60000 obscura fetch "https://example.com/app" --timeout 60 --wait-until networkidle0 --output "page.html"
```

PowerShell:

```powershell
$env:OBSCURA_SCRIPT_DEADLINE_MS = '60000'
obscura fetch "https://example.com/app" --timeout 60 --wait-until networkidle0 --output "page.html"
```

Pages that finish sooner still return immediately. A larger budget allows slow or hung scripts to consume CPU for longer.

## Supported Values

| Option | Supported values |
|---|---|
| `fetch --dump` | `html`, `text`, `links`, `markdown`, `assets`, `original` |
| `fetch --wait-until` | `load`, `domcontentloaded`, `networkidle0` |
| `scrape --format` | `json`, `text` |

## Command Construction Checklist

- Use `fetch` for one URL and `scrape` for multiple independent URLs.
- Put `--proxy` and `--v8-flags` before the subcommand.
- Treat `fetch --timeout` as seconds and `OBSCURA_SCRIPT_DEADLINE_MS` as milliseconds.
- Use `--eval` for targeted DOM data and `--dump original` for raw bytes.
- Use only flags documented for the selected subcommand.
- Check installed `--help` before adapting to version-specific behavior.
