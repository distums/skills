# Using Obscura CLI Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create and verify a reusable `using-obscura-cli` skill that guides agents through Obscura's `fetch` and `scrape` commands without introducing MCP, CDP, Puppeteer, Playwright, or `serve` workflows.

**Architecture:** Keep the frequently loaded decision workflow in `SKILL.md`, move exact command and tuning details into one directly linked CLI reference, and store three realistic evaluations in `evals/evals.json`. Use baseline and skill-guided agent runs to verify that the skill improves command selection, flag placement, dynamic-page handling, binary output, and troubleshooting.

**Tech Stack:** Markdown Agent Skills, YAML frontmatter, Obscura CLI, JSON evaluation fixtures, PowerShell validation, Git.

---

## File Structure

- Create `using-obscura-cli/SKILL.md`: triggering metadata, command-selection workflow, safety boundaries, quick reference, one representative example, and common mistakes.
- Create `using-obscura-cli/references/cli-reference.md`: exact CLI syntax derived from `D:/repository/obscura/readme.md` for installation checks, `fetch`, `scrape`, proxy use, V8 tuning, and SPA script budgets.
- Create `using-obscura-cli/evals/evals.json`: three realistic prompts with objectively verifiable expectations.
- Create `using-obscura-cli-workspace/iteration-1/...`: temporary baseline and skill-guided outputs, metadata, timings, and grades used during development.
- Modify `.gitignore`: exclude `using-obscura-cli-workspace/` because benchmark artifacts are development outputs rather than shipped skill content.

### Task 1: Establish the RED Baseline

**Files:**

- Modify: `.gitignore`
- Create: `using-obscura-cli-workspace/iteration-1/dynamic-single-page/eval_metadata.json`
- Create: `using-obscura-cli-workspace/iteration-1/batch-proxy-scrape/eval_metadata.json`
- Create: `using-obscura-cli-workspace/iteration-1/binary-and-tuning/eval_metadata.json`
- Create: `using-obscura-cli-workspace/iteration-1/baseline-findings.md`

- [ ] **Step 1: Ignore the evaluation workspace**

Append this exact entry to `.gitignore` using `apply_patch`:

```gitignore

# Skill evaluation workspaces
using-obscura-cli-workspace/
```

- [ ] **Step 2: Create baseline metadata**

Create one `eval_metadata.json` per scenario with these prompts and an empty `assertions` array:

```json
{
  "eval_id": 1,
  "eval_name": "dynamic-single-page",
  "prompt": "Use only the Obscura CLI to extract the text and href of every .result-card a element from https://example.test/search. The page renders results asynchronously, so wait for .result-card, bound navigation to 20 seconds, and save the JavaScript evaluation result to results.json. Provide the exact command and a short explanation; do not run it.",
  "assertions": []
}
```

```json
{
  "eval_id": 2,
  "eval_name": "batch-proxy-scrape",
  "prompt": "Use only the Obscura CLI to scrape https://example.test/a, https://example.test/b, and https://example.test/c through socks5://127.0.0.1:1080. Extract each h1, use five workers, emit JSON, and suppress progress noise. Provide the exact command and a short explanation; do not run it.",
  "assertions": []
}
```

```json
{
  "eval_id": 3,
  "eval_name": "binary-and-tuning",
  "prompt": "Using only Obscura CLI commands, show how to save https://example.test/photo.png without corrupting its bytes. Then show how to retry a JavaScript-heavy page after a 'JavaScript heap out of memory' failure and allow a 60-second SPA script budget. Provide exact commands and explain the resource trade-off; do not run them.",
  "assertions": []
}
```

- [ ] **Step 3: Run three independent baseline agents without the skill**

Spawn the three prompts concurrently. Tell each agent that it has no Obscura skill, must not read `D:/repository/obscura/readme.md`, must not execute commands, and must save its final response as:

```text
using-obscura-cli-workspace/iteration-1/<eval-name>/without_skill/outputs/response.md
```

Capture each completion's token and duration values immediately in `without_skill/timing.json` using the `timing.json` schema.

- [ ] **Step 4: Verify RED and record gaps**

Read all three baseline responses. Record exact incorrect commands, omitted flags, unsupported interfaces, or unsafe assumptions in `baseline-findings.md`. A valid RED result has at least one objectively relevant gap across the campaign; if all expectations already pass, strengthen the scenarios before writing the skill.

- [ ] **Step 5: Define objective assertions**

Update each `eval_metadata.json` with the following assertions:

Dynamic single page:

```json
[
  "Uses obscura fetch for the single URL",
  "Includes --selector .result-card and --timeout 20",
  "Uses --eval to return text and href values and --output results.json",
  "Does not use serve, MCP, CDP, Puppeteer, or Playwright"
]
```

Batch proxy scrape:

```json
[
  "Uses obscura scrape with all three URLs",
  "Places --proxy socks5://127.0.0.1:1080 before the scrape subcommand",
  "Includes --concurrency 5, --eval for h1, --format json, and --quiet",
  "Does not use serve, MCP, CDP, Puppeteer, or Playwright"
]
```

Binary and tuning:

```json
[
  "Uses obscura fetch with --dump original for the image",
  "Preserves binary output through an output file or binary-safe redirection",
  "Uses --v8-flags with --max-old-space-size=4096 before fetch",
  "Sets OBSCURA_SCRIPT_DEADLINE_MS=60000 and explains higher memory/time costs",
  "Does not use serve, MCP, CDP, Puppeteer, or Playwright"
]
```

### Task 2: Write the Minimal GREEN Skill

**Files:**

- Create: `using-obscura-cli/SKILL.md`
- Create: `using-obscura-cli/references/cli-reference.md`
- Create: `using-obscura-cli/evals/evals.json`

- [ ] **Step 1: Create `SKILL.md` from baseline evidence**

Use this exact frontmatter:

```yaml
---
name: using-obscura-cli
description: Use when a task requires the Obscura command-line headless browser for fetching or scraping pages, JavaScript-rendered extraction, batch URLs, proxies, dynamic waits, binary responses, heavy SPAs, or Obscura CLI troubleshooting.
---
```

Keep the body under 500 lines and include these sections in this order:

1. `# Using Obscura CLI`
2. `## Scope` with an explicit CLI-only boundary and exclusions for `serve`, MCP, CDP, Puppeteer, and Playwright.
3. `## Workflow` covering authorization, local `obscura --help`, one URL versus multiple URLs, extraction mode, waits, bounded execution, and output reporting.
4. `## Command Selection` mapping one URL to `fetch` and multiple independent URLs to `scrape`.
5. `## Quick Reference` with the core supported flags.
6. `## Example` using the dynamic single-page scenario.
7. `## Troubleshooting` routing command-not-found, unsupported syntax, missing dynamic content, heavy SPA budgets, V8 heap exhaustion, binary output, and batch instability.
8. `## Safety` covering authorization, access controls, rate limits, secrets, bounded concurrency, and confirmation before installation or persistent changes.
9. `## Common Mistakes` covering global proxy placement, raw binary handling, `--eval` versus `--dump`, and excluded interfaces.
10. A direct instruction to read `references/cli-reference.md` before composing a non-trivial command or troubleshooting flags.

Address every concrete gap recorded in `baseline-findings.md`; do not add unrelated features.

- [ ] **Step 2: Create the CLI reference from the source README**

Write `references/cli-reference.md` with a contents list and these exact sections:

- Availability and local help checks.
- `obscura fetch <URL>` syntax and the README-supported flags: `--dump`, `--eval`, `--wait-until`, `--timeout`, `--selector`, `--stealth`, `--output`, `--quiet`, and inherited `--proxy`.
- `obscura scrape <URL...>` syntax and flags: `--concurrency`, `--eval`, `--format`, `--quiet`, and inherited `--proxy`.
- Global proxy placement examples.
- Raw binary response example using `--dump original`.
- Asset listing behavior for `--dump assets` as NDJSON.
- V8 heap tuning with `obscura --v8-flags "--max-old-space-size=4096" fetch <url>`.
- Heavy SPA tuning with `OBSCURA_SCRIPT_DEADLINE_MS=60000` and a matching navigation budget.
- A supported-values table for `--dump`, `--wait-until`, and `--format`.

Do not copy `serve`, MCP, CDP, Puppeteer, Playwright, marketing, sponsor, benchmark, or cloud material.

- [ ] **Step 3: Create the shipped eval fixture**

Create `evals/evals.json` using the three prompts from Task 1. Each item must contain `id`, `prompt`, `expected_output`, `files: []`, and the same objective assertions under the schema field `expectations`.

- [ ] **Step 4: Validate the draft structure**

Run:

```powershell
$skill = Get-Content -Raw './using-obscura-cli/SKILL.md'
$evals = Get-Content -Raw './using-obscura-cli/evals/evals.json' | ConvertFrom-Json
if ($skill -notmatch '^---\r?\nname: using-obscura-cli\r?\ndescription: Use when') { throw 'Invalid frontmatter' }
if ($evals.skill_name -ne 'using-obscura-cli' -or $evals.evals.Count -ne 3) { throw 'Invalid evals' }
```

Expected: exit code 0 with no error.

### Task 3: Verify GREEN and Refactor

**Files:**

- Create: `using-obscura-cli-workspace/iteration-1/<eval-name>/with_skill/outputs/response.md`
- Create: `using-obscura-cli-workspace/iteration-1/<eval-name>/with_skill/timing.json`
- Create: `using-obscura-cli-workspace/iteration-1/<eval-name>/{with_skill,without_skill}/grading.json`
- Create: `using-obscura-cli-workspace/iteration-1/benchmark.json`
- Create: `using-obscura-cli-workspace/iteration-1/benchmark.md`
- Create: `using-obscura-cli-workspace/iteration-1/review.html`
- Modify: `using-obscura-cli/SKILL.md` or `using-obscura-cli/references/cli-reference.md` only if testing exposes a real gap.

- [ ] **Step 1: Run three independent agents with the skill**

Spawn the three Task 1 prompts concurrently. Require each agent to read `using-obscura-cli/SKILL.md` completely and follow its direct reference link when needed. Save responses under each scenario's `with_skill/outputs/response.md` and capture timing immediately.

- [ ] **Step 2: Grade both configurations**

Read `C:/Users/distums/.agents/skills/skill-creator/agents/grader.md`, then grade each response against its `eval_metadata.json` assertions. Save `grading.json` with exact `text`, `passed`, and `evidence` fields plus a summary.

- [ ] **Step 3: Aggregate the benchmark**

Run from `C:/Users/distums/.agents/skills/skill-creator`:

```powershell
python -m scripts.aggregate_benchmark 'D:/repository/skills/using-obscura-cli-workspace/iteration-1' --skill-name using-obscura-cli
```

Expected: `benchmark.json` and `benchmark.md` are created with `with_skill` and `without_skill` results.

- [ ] **Step 4: Generate the static review viewer**

Run:

```powershell
python 'C:/Users/distums/.agents/skills/skill-creator/eval-viewer/generate_review.py' 'D:/repository/skills/using-obscura-cli-workspace/iteration-1' --skill-name using-obscura-cli --benchmark 'D:/repository/skills/using-obscura-cli-workspace/iteration-1/benchmark.json' --static 'D:/repository/skills/using-obscura-cli-workspace/iteration-1/review.html'
```

Expected: `review.html` exists and contains both output and benchmark views.

- [ ] **Step 5: Refactor only from observed failures**

If a skill-guided assertion fails, revise the smallest relevant section, rerun that scenario, regrade it, and regenerate the benchmark. Stop when all skill-guided assertions pass or report the unresolved evidence; do not broaden scope.

### Task 4: Final Validation and Commit

**Files:**

- Verify: `using-obscura-cli/SKILL.md`
- Verify: `using-obscura-cli/references/cli-reference.md`
- Verify: `using-obscura-cli/evals/evals.json`
- Verify: `.gitignore`

- [ ] **Step 1: Verify required files and JSON**

Run:

```powershell
$required = @('./using-obscura-cli/SKILL.md','./using-obscura-cli/references/cli-reference.md','./using-obscura-cli/evals/evals.json')
foreach ($path in $required) { if (-not (Test-Path -LiteralPath $path)) { throw "Missing $path" } }
Get-Content -Raw './using-obscura-cli/evals/evals.json' | ConvertFrom-Json | Out-Null
```

Expected: exit code 0 with no errors.

- [ ] **Step 2: Verify scope and source accuracy**

Compare every documented flag and supported value against `D:/repository/obscura/readme.md`. Confirm that excluded interface names appear only in scope warnings, not executable examples, and that `serve` never appears as a recommended command.

- [ ] **Step 3: Verify formatting and repository state**

Run:

```powershell
git -c safe.directory='D:/repository/skills' diff --check
git -c safe.directory='D:/repository/skills' status --short
```

Expected: no whitespace errors; only `.gitignore` and `using-obscura-cli/` are implementation changes before commit.

- [ ] **Step 4: Commit the verified skill**

Run:

```powershell
git -c safe.directory='D:/repository/skills' add -- .gitignore using-obscura-cli
git -c safe.directory='D:/repository/skills' commit -m "feat: add Obscura CLI skill"
```

- [ ] **Step 5: Confirm the committed result**

Run:

```powershell
git -c safe.directory='D:/repository/skills' status --short
git -c safe.directory='D:/repository/skills' show --stat --oneline --summary HEAD
```

Expected: clean status and a commit containing `.gitignore` plus the three `using-obscura-cli` files.
