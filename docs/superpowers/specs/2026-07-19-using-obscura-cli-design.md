# Using Obscura CLI Skill Design

## Goal

Create a reusable agent skill that guides reliable use of the Obscura headless browser exclusively through its command-line interface. The skill must help an agent choose the correct command, construct safe and precise invocations, and troubleshoot common execution failures without drifting into MCP, CDP, Puppeteer, or Playwright workflows.

## Scope

The skill covers:

- Verifying that the `obscura` executable is available and inspecting local help before use.
- Fetching and rendering one URL with `obscura fetch`.
- Scraping multiple URLs concurrently with `obscura scrape`.
- Selecting HTML, text, links, Markdown, assets, original response bodies, or JavaScript evaluation output.
- Waiting for page lifecycle events or CSS selectors on dynamic pages.
- Applying navigation timeouts, output files, quiet output, HTTP/SOCKS5 proxies, concurrency, and result formats.
- Handling JavaScript heap exhaustion, heavy SPA script budgets, slow pages, and binary resources.

The skill explicitly excludes:

- `obscura serve`, because it exists to expose a CDP server.
- Obscura MCP configuration and MCP browser tools.
- Chrome DevTools Protocol calls.
- Puppeteer and Playwright examples or generated code.
- Automatic installation, downloading, or starting persistent services without user authorization.

## Skill Layout

Use a flat skill directory named `using-obscura-cli`:

```text
using-obscura-cli/
|-- SKILL.md
|-- references/
|   `-- cli-reference.md
`-- evals/
    `-- evals.json
```

`SKILL.md` contains the decision workflow, safety rules, quick reference, one representative example, troubleshooting routing, and common mistakes. It stays concise so an agent can load it for every relevant task without consuming the full API reference.

`references/cli-reference.md` contains the exact supported command syntax and flags derived from `D:\repository\obscura\readme.md`. It includes only CLI material relevant to `fetch`, `scrape`, global proxy/V8 options, output behavior, and environment tuning. It does not reproduce marketing, benchmarks, MCP, CDP, or library integration sections.

`evals/evals.json` contains realistic retrieval and application prompts for skill testing.

## Triggering and Naming

The skill name is `using-obscura-cli`.

Its description begins with `Use when...` and targets these situations:

- A user explicitly requests Obscura CLI.
- A user wants to fetch or scrape pages with Obscura.
- A user needs JavaScript-rendered extraction, batch URL processing, proxy use, dynamic-page waits, or Obscura CLI troubleshooting.

The description does not summarize the internal workflow. Keywords such as `obscura`, `headless browser`, `fetch`, `scrape`, `JavaScript rendering`, `proxy`, and `SPA` make the skill discoverable while keeping adjacent CDP/MCP tasks outside its trigger boundary.

## Command Selection and Data Flow

The agent follows this decision sequence:

1. Confirm that the requested work is authorized and suitable for browser automation.
2. Run `obscura --help` or the relevant subcommand help when the installed CLI is available, because local help is the authoritative source for version-specific behavior.
3. Choose `fetch` for one URL and `scrape` for multiple independent URLs.
4. Choose exactly one primary extraction mode:
   - `--dump html`, `text`, `links`, `markdown`, or `assets` for document-oriented output.
   - `--dump original` for the raw response body, including binary resources.
   - `--eval` for targeted JavaScript extraction.
5. Add waiting behavior only when the page requires it: `--selector` for a known element or `--wait-until` for lifecycle/network completion.
6. Add bounded timeouts and resource tuning appropriate to the page.
7. Choose stdout for pipelines or `--output` for an explicit file.
8. Report the command, output location, and any assumptions or failures without exposing credentials.

Global options such as `--proxy` and `--v8-flags` appear before the subcommand, following the README examples. Scrape workers inherit the global proxy.

## Error Handling

The skill maps symptoms to focused responses:

- Command not found: report that Obscura is unavailable and ask whether installation is desired; do not install automatically.
- Unsupported flag or syntax: inspect `obscura <subcommand> --help` and adapt to the installed version.
- Slow or broken navigation: use a finite `--timeout`; select a more suitable wait condition when justified.
- Missing dynamic content: wait for a stable CSS selector or use `networkidle0` when background traffic eventually settles.
- Heavy React/Vue/Angular application: raise `OBSCURA_SCRIPT_DEADLINE_MS` and keep the navigation timeout consistent with that budget.
- `JavaScript heap out of memory`: raise the V8 heap using `--v8-flags "--max-old-space-size=4096"` as a deliberate resource trade-off.
- Corrupted binary output: use `--dump original` and preserve the raw byte stream instead of passing it through DOM/text extraction.
- Batch failures: reduce concurrency, retain machine-readable JSON output, and keep progress noise separate with `--quiet` when appropriate.

## Safety and Operational Boundaries

The skill instructs the agent to:

- Use browser automation only on targets and accounts the user is authorized to access.
- Avoid bypassing access controls, CAPTCHAs, rate limits, or site protections.
- Respect applicable site policies and robots directives through task-level policy; do not document `--obey-robots` because the README exposes it only for the excluded `serve` command.
- Never place passwords, tokens, cookies, or proxy credentials in logs or final responses.
- Avoid unbounded concurrency and indefinite waits.
- Confirm before downloads, installations, persistent processes, or other material environment changes.
- Preserve raw output faithfully when the requested content is binary.

## Test Strategy

Treat this as a reference skill and test both retrieval and correct application.

1. Dynamic single-page extraction: request a command that waits for a selector, evaluates a targeted DOM expression, uses a finite timeout, and writes a result file.
2. Batch proxy scraping: request multiple URLs through a proxy with bounded concurrency, JSON output, and quiet progress; verify global proxy placement and `scrape` selection.
3. Binary and troubleshooting: request an image download plus guidance for a JS-heavy page that exhausts V8 memory; verify `--dump original`, binary-safe output, and correct tuning syntax.

For each scenario, first record baseline behavior without the skill, then run the same scenario with the skill. Assertions check command selection, flag placement, exclusion of MCP/CDP/library APIs, bounded execution, and handling of sensitive data. Revise the skill if tests expose ambiguity or unsupported syntax.

## Success Criteria

The skill is ready when:

- It contains no MCP, CDP, Puppeteer, Playwright, or `serve` workflow guidance beyond an explicit exclusion.
- Its documented commands and flags match the source README.
- An agent consistently chooses `fetch` for one URL and `scrape` for multiple URLs.
- The agent uses correct extraction, waiting, proxy, output, and tuning options for the tested scenarios.
- The skill passes structural validation and its test cases distinguish skill-guided behavior from the baseline.
