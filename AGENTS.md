# AGENTS.md

This file is the working guide for agents editing `claw-eco`.

## First rule: sync with remote before changing anything

This repo is actively updated from GitHub Actions and may also receive direct remote edits.
Before starting work, always pull the latest remote changes when it is safe to do so.

Recommended sequence:

```bash
git status --short --branch
git fetch origin
git pull --ff-only origin main
```

If the worktree is dirty:

- Do not discard local changes you did not make.
- Inspect what is modified first.
- Either merge around those changes or coordinate before pulling if the same files are involved.

## What this repo is

`claw-eco` is a single-page static comparison site about "claw-like" AI agent tools, centered on OpenClaw and nearby ecosystems.

The page is not a generic AI directory. The business lens is:

- Open-source AI agent frameworks with similar style or end-user job to OpenClaw.
- Wrappers and harnesses that operationalize, secure, deploy, or manage OpenClaw-like agents.
- Commercial products that overlap with OpenClaw's user job, even if they are hosted SaaS instead of open source frameworks.
- China-market agent products and adjacent frameworks that matter for the same landscape scan.

## Business context

"OpenClaw proximity" matters more than raw popularity.

The strongest fits usually share several of these traits:

- Personal or team AI assistant behavior
- Long-running or always-on agents
- Multi-channel messaging or multi-surface presence
- Tool use, memory, scheduling, workflow execution, or companion UX
- Self-hosted or operator-controlled runtime
- Direct overlap with "replace or extend OpenClaw" decision making

Weak fits:

- Generic model SDKs with no agent runtime angle
- Pure prompt libraries
- Narrow LLM utilities with no meaningful OpenClaw-style use case overlap

### Landscape chart

| Section | OpenClaw proximity | What belongs here | Typical examples |
| --- | --- | --- | --- |
| AI Agent Frameworks | High | Open-source runtimes or frameworks that are close in style, use case, or deployment model to OpenClaw | OpenClaw, nanobot, TinyAGI, Archon |
| Wrapper Harnesses and Ops Layers | Medium to high | Tools that wrap, govern, secure, deploy, or orchestrate OpenClaw-like agents | Paperclip, NemoClaw, OpenSandbox |
| Commercial AI Agent Platforms | Medium | Hosted products that solve similar user jobs as OpenClaw, even if they are not OSS frameworks | PetClaw, Devin, OpenAI Operator |
| China's AI Agent Product Wave | Mixed | Market-facing products in the China ecosystem relevant to the same competitive scan | consumer and business agent products |
| China's AI Agent Product Wave - Extended | Mixed | Extra frameworks, products, and adjacent implementations worth tracking in the same market map | OSS and hosted China-adjacent entries |

## Repo layout

Important files:

- `index.html`: the entire site, including content, styles, markup, and client-side behavior
- `favicon.svg`: icon deployed with the page
- `update_stats.py`: updates GitHub-derived stats and footer timestamps in HTML files
- `.github/workflows/static.yml`: deploys the static site to GitHub Pages
- `.github/workflows/update-stats.yml`: scheduled daily stats refresh and follow-up deploy
- `README.md`: lightweight local preview notes

There is no build system, bundler, framework runtime, or package manifest.

## index.html

### Tech stack

`index.html` is a self-contained static page:

- Plain HTML
- Embedded CSS in a single `<style>` block
- Embedded vanilla JavaScript in a single bottom-of-file `<script>`
- Google Fonts for `JetBrains Mono` and `DM Sans`
- No npm, no transpilation, no template system

There is also a small `<base href>` helper in the `<head>` so the page can work correctly when served from a subpath.

### Content structure

The page is made of section headers followed by `.table-wrap` containers.

Current major sections:

1. AI Agent Frameworks
2. Wrapper Harnesses and Ops Layers
3. Commercial AI Agent Platforms
4. China's AI Agent Product Wave
5. China's AI Agent Product Wave - Extended

Most edits are content edits inside table rows.

### Table behavior

Important runtime behavior:

- The China product table is client-side sorted by `data-launch-sort`.
- Global search is implemented in the bottom `<script>`.
- Search applies across all `.table-wrap table` elements.
- Queries shorter than 3 characters reset visibility and show all rows.
- If a query has no matches, the page also resets to showing all rows.
- If there are matches, rows and whole sections are hidden or shown by toggling `hidden`.

Relevant DOM ids and behavior:

- `#global-table-search`
- `#global-search-clear`
- `#china-product-table`

### Editing guidance for index.html

- Preserve the single-file structure unless the user explicitly asks for a refactor.
- Keep row markup consistent with neighboring rows.
- Reuse existing badge, tag, and metric styles instead of inventing new markup patterns.
- If you add a GitHub-backed row, include the repo URL so `update_stats.py` can discover it.
- Expect the first two tables to be re-sorted by star count after running the update script.
- Expect the footer timestamp to change when `update_stats.py` runs.

## GitHub Actions

### 1. Pages deploy

File: `.github/workflows/static.yml`

Behavior:

- Runs on pushes to `main`
- Trigger path filter is limited to:
  - `index.html`
  - `favicon.svg`
- Also supports `workflow_dispatch` and `workflow_call`
- Copies `index.html` and `favicon.svg` into `_site/`
- Deploys `_site/` to GitHub Pages

### 2. Daily stats refresh

File: `.github/workflows/update-stats.yml`

Behavior:

- Runs on schedule: `0 6 * * *`
- That is 06:00 UTC every day
- Also supports manual `workflow_dispatch`
- Runs `python3 update_stats.py`
- Commits `index.html` if the generated output changed
- Pushes the stats update commit back to `main`
- Deploys the pushed commit to GitHub Pages if anything changed

Operational implication:

- Remote `main` can move even when no human edited the repo, because the stats workflow writes directly to the branch.

## update_stats.py

Purpose:

- Fetch stars, forks, commit counts, primary language, and last-updated dates from GitHub
- Update GitHub-backed rows in HTML
- Fill missing language tags in the two China tables when possible
- Re-sort the first two tables by GitHub star count
- Refresh the footer "Last updated" timestamp

How repo discovery works:

- The script scans HTML for `https://github.com/owner/repo` links
- Any row without a GitHub URL is ignored for stats refresh

What it mutates:

- `star-count`
- `fork-count`
- `commit-count`
- `last-updated`
- Missing language tags in China tables
- Footer timestamp via `#last-updated-date`

What it does not do:

- It does not update commercial rows without GitHub links
- It does not understand external hosting or Cloudflare config
- It does not sort all tables; only the first two `<tbody>` blocks are star-sorted

Local usage:

```bash
python3 update_stats.py --file index.html
```

Requirements:

- Python 3
- `gh` CLI
- authenticated GitHub access for API calls

## Hosting and delivery

Hosting model:

- Source of truth content lives in this repo
- GitHub Pages serves the deployed static site
- A Cloudflare hidden redirect or proxy layer sits in front operationally

Important note:

- Cloudflare configuration is not defined in this repo
- Treat GitHub Pages as the deploy target and Cloudflare as external infrastructure
- If the user asks for DNS, redirect, cache, or edge behavior changes, expect that to be outside the checked-in files unless they add infra config later

## Practical editing rules for future agents

- Pull remote changes first before starting work
- Check whether `index.html` is already dirty before editing
- Do not revert user changes just to make a pull work
- When adding entries, keep the OpenClaw-comparison lens front and center
- Prefer high-signal additions over exhaustive catalogs
- Keep the page self-contained unless explicitly asked to split files
- After changing GitHub-backed rows, run `python3 update_stats.py --file index.html` if you want the stats and order refreshed
- Be aware that running the update script changes the footer timestamp and may reorder the first two tables

## Suggested quick-start workflow for agents

```bash
git status --short --branch
git fetch origin
git pull --ff-only origin main
python3 -m http.server 8000
```

Then open `http://localhost:8000` for a local check if needed.
