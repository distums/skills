---
name: using-obscura-cli
description: Use when a task requires the Obscura command-line headless browser for fetching or scraping pages, JavaScript-rendered extraction, batch URLs, proxies, dynamic waits, binary responses, heavy SPAs, or Obscura CLI troubleshooting.
---

# Using Obscura CLI

## Scope

Use Obscura through its CLI only. This skill covers `fetch` for one URL and `scrape` for multiple independent URLs.

Do not switch to `serve`, MCP, CDP, Puppeteer, or Playwright. If the request requires one of those interfaces, explain that it is outside this skill rather than generating commands or code for it.

Read [references/cli-reference.md](references/cli-reference.md) completely before composing a non-trivial command or troubleshooting flags. Obscura's surface differs from Chrome-like CLIs; do not guess subcommands, flag names, units, or option placement.

## Workflow

1. Confirm that the user is authorized to automate the target and that the request does not bypass access controls or site protections.
2. Respect the requested action boundary. If the user asks only for a command, do not execute it.
3. When execution is authorized and Obscura is available, inspect `obscura --help` and the relevant subcommand help. Installed help is authoritative for version-specific behavior.
4. Choose the subcommand by URL count: one URL uses `fetch`; multiple independent URLs use `scrape`.
5. Choose one primary extraction mode: a `--dump` value, `--eval`, or the default HTML output.
6. For `fetch`, add a selector or lifecycle wait only when dynamic content requires it. Bound navigation with `--timeout` in **seconds**.
7. Put global options such as `--proxy` and `--v8-flags` before the subcommand.
8. Use stdout for pipelines or `--output` for an explicit file. Preserve raw bytes for binary resources.
9. Report the exact command, output location, assumptions, and any failure without exposing secrets.

## Command Selection

| Need | Command | Notes |
|---|---|---|
| Render or extract one URL | `obscura fetch <URL>` | Supports dumps, JavaScript evaluation, waits, timeout, and output files |
| Process multiple URLs | `obscura scrape <URL...>` | Supports concurrent workers, per-page evaluation, JSON/text format, and quiet progress |
| Save an image or other raw resource | `obscura fetch <URL> --dump original --output <FILE>` | Bypasses the JavaScript/DOM layer and preserves bytes |

Never invent adjacent-looking forms such as `navigate`, `--wait-for`, `--workers`, `--json`, `--no-progress`, `--binary`, `--javascript`, or `--spa-timeout`.

## Quick Reference

| Concern | Supported form |
|---|---|
| Targeted extraction | `--eval "<JavaScript expression>"` |
| Document output | `--dump html|text|links|markdown|assets|original` |
| Known dynamic element | `--selector <CSS_SELECTOR>` |
| Lifecycle wait | `--wait-until load|domcontentloaded|networkidle0` |
| Navigation bound | `--timeout <SECONDS>` |
| Explicit output file | `--output <PATH>` |
| Global HTTP/SOCKS5 proxy | `obscura --proxy <URL> <SUBCOMMAND> ...` |
| Batch concurrency | `scrape ... --concurrency <N>` |
| Batch output | `scrape ... --format json|text` |
| Quiet batch progress | `scrape ... --quiet` |

## Example

Extract links after asynchronous results appear and save the evaluation output:

```sh
obscura fetch "https://example.test/search" --selector ".result-card" --timeout 20 --eval "Array.from(document.querySelectorAll('.result-card a'), a => ({ text: a.textContent.trim(), href: a.href }))" --output "results.json"
```

The timeout is 20 seconds, not milliseconds. `--selector` waits for the known result element before the evaluation runs.

## Troubleshooting

- **`obscura` not found:** Report that the executable is unavailable and ask whether installation is desired. Do not download or install it automatically.
- **Unknown subcommand or flag:** Run the relevant local `--help` when authorized. Replace guessed Chrome-like syntax with documented Obscura syntax.
- **Dynamic content missing:** Prefer `--selector` when a stable element is known. Use `--wait-until networkidle0` only when network activity eventually settles.
- **Slow or broken page:** Use a finite `--timeout`; do not create an indefinite wait.
- **Heavy SPA needs longer to boot:** Set `OBSCURA_SCRIPT_DEADLINE_MS` in milliseconds and pair it with a matching `fetch --timeout` value in seconds. See the reference for shell-specific examples.
- **`JavaScript heap out of memory`:** Raise the V8 heap deliberately with global `--v8-flags`; a larger heap increases possible peak memory.
- **Binary output is corrupted:** Use `--dump original` with `--output` or binary-safe redirection. Do not pass raw bytes through a text transformation.
- **Batch runs are unstable:** Reduce `--concurrency`, retain `--format json` for machine-readable results, and use `--quiet` when progress noise would interfere with consumers.

## Safety

- Automate only targets and accounts the user is authorized to access.
- Do not bypass authentication, CAPTCHAs, rate limits, robots directives, or other site protections.
- Never print passwords, tokens, cookies, or credential-bearing proxy URLs in logs or final responses.
- Keep timeouts and concurrency bounded; start conservatively when target capacity is unknown.
- Confirm before installations, downloads, persistent processes, or other material environment changes.
- Treat `--stealth` as an execution mode, not authorization to evade safeguards.

## Common Mistakes

- Putting `--proxy` after `fetch` or `scrape`; use it as a global option before the subcommand.
- Treating `fetch --timeout` as milliseconds; it is expressed in seconds.
- Using `--dump text` or `--eval` for an image; use `--dump original` for raw bytes.
- Guessing familiar browser flags instead of consulting the bundled reference or installed help.
- Using `scrape --selector`; batch extraction uses `--eval` according to the documented CLI surface.
- Combining multiple primary extraction modes without a clear need; choose the output that matches the requested artifact.
