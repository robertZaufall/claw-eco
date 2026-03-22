#!/usr/bin/env python3
"""
Fetch live GitHub stats (stars, forks, commits, language, last update) and update HTML files.
Tables 1 (frameworks) and 2 (harnesses) are updated in-place, and the China tables
can inherit missing language tags from linked GitHub repos.

Requirements: gh CLI (authenticated)
Usage:       python3 update_stats.py [--file index.html] [--file other.html]
"""

import argparse
from html import escape
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from datetime import datetime


FOOTER_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M"
LANGUAGE_KEYWORDS_RE = re.compile(
    r"\b(TypeScript|JavaScript|Node\.js|Python|Rust|Go|Golang|Zig|C\+\+|C#|C|"
    r"Java|Kotlin|Swift|Shell|Bash|PHP|Ruby|Elixir|Scala)\b",
    re.IGNORECASE,
)
CHINA_TABLE_IDS = ("china-product-table", "china-claw-extended-table")


def gh_api(path: str) -> dict | list:
    """Call the GitHub API via the gh CLI (handles auth + SSL)."""
    try:
        result = subprocess.run(
            ["gh", "api", path],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            if "404" in result.stderr:
                print("NOT FOUND", end=" ")
                return {}
            print(f"ERROR: {result.stderr.strip()[:80]}", end=" ")
            return {}
        return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError) as e:
        print(f"ERROR: {e}", end=" ")
        return {}


def get_commit_count(owner: str, repo: str) -> int | None:
    """Get total commit count via the contributors endpoint (summed)."""
    page = 1
    total = 0
    while True:
        data = gh_api(f"repos/{owner}/{repo}/contributors?per_page=100&anon=true&page={page}")
        if not data or not isinstance(data, list):
            break
        for c in data:
            total += c.get("contributions", 0)
        if len(data) < 100:
            break
        page += 1
    return total if total else None


def fetch_repo_stats(owner: str, repo: str) -> dict:
    """Return {stars, forks, commits, emoji, language, pushed_at} for one repo."""
    info = gh_api(f"repos/{owner}/{repo}")
    if not info or not isinstance(info, dict):
        return {}

    stars = info.get("stargazers_count", 0)
    forks = info.get("forks_count", 0)
    pushed_at = info.get("pushed_at", "")  # ISO 8601: "2026-03-15T..."
    primary_language = info.get("language") or ""

    commits = get_commit_count(owner, repo)

    topics = [t.lower() for t in (info.get("topics") or [])]
    lang = primary_language.lower()
    emoji = pick_emoji(topics, lang, info.get("description", ""))

    # Format pushed_at to "Mar 2026" style
    updated = ""
    if pushed_at:
        dt = datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
        updated = dt.strftime("%b %d, %Y")

    return {
        "stars": stars,
        "forks": forks,
        "commits": commits,
        "emoji": emoji,
        "language": primary_language,
        "updated": updated,
    }


def pick_emoji(topics: list[str], lang: str, desc: str) -> str:
    """Pick an emoji based on repo metadata."""
    keyword_map = {
        "security": "🛡️",
        "privacy": "🔒",
        "rust": "🦀",
        "zig": "⚡",
        "go": "🐹",
        "golang": "🐹",
        "embedded": "🔌",
        "esp32": "🔌",
        "iot": "🔌",
        "microcontroller": "🔌",
        "nvidia": "💚",
        "lightweight": "🪶",
        "tiny": "🪶",
        "nano": "🪶",
        "pico": "🪶",
        "autonomous": "🤖",
        "agent": "🤖",
        "self-improving": "🧠",
        "memory": "🧠",
        "bytedance": "🔬",
        "research": "🔬",
        "desktop": "🖥️",
        "companion": "🐾",
    }

    for keyword, em in keyword_map.items():
        if keyword in topics:
            return em
    desc_lower = (desc or "").lower()
    for keyword, em in keyword_map.items():
        if keyword in desc_lower:
            return em
    lang_map = {"rust": "🦀", "zig": "⚡", "go": "🐹", "c": "🔌"}
    if lang in lang_map:
        return lang_map[lang]
    return "🦞"


def fmt_number(n: int) -> str:
    """Format a number like GitHub does: 1.2k, 34k, 319k, etc."""
    if n >= 1_000_000:
        v = f"{n / 1_000_000:.1f}M"
        return v.replace(".0M", "M")
    if n >= 100_000:
        return f"{n / 1000:.0f}k"
    if n >= 1_000:
        v = f"{n / 1000:.1f}k"
        return v.replace(".0k", "k")
    return str(n)


def update_html(html: str, repos: dict[str, dict]) -> str:
    """Refresh GitHub stats and enrich language tags where repo-backed rows need them."""

    def replace_row(m: re.Match) -> str:
        full = m.group(0)
        link_m = re.search(r'github\.com/([^"]+)', full)
        if not link_m:
            return full
        slug = link_m.group(1).rstrip("/").lower()
        stats = repos.get(slug)
        if not stats:
            return full

        stars_str = fmt_number(stats["stars"])
        forks_str = fmt_number(stats["forks"])

        # Replace star count
        full = re.sub(
            r'(<span class="star-count">)★\s*[^<]+(</span>)',
            rf'\g<1>★ {stars_str}\2',
            full,
        )
        # Replace fork count
        full = re.sub(
            r'(<span class="fork-count">)⑂\s*[^<]+(</span>)',
            rf'\g<1>⑂ {forks_str}\2',
            full,
        )

        # Add or update commit count
        commit_span_re = r'<span class="commit-count">[^<]*</span>'
        if stats.get("commits"):
            commits_str = fmt_number(stats["commits"])
            new_commit = f'<span class="commit-count">⟳ {commits_str}</span>'
            if re.search(commit_span_re, full):
                full = re.sub(commit_span_re, new_commit, full)
            else:
                full = re.sub(
                    r'(<span class="fork-count">[^<]*</span>)',
                    rf'\1\n        {new_commit}',
                    full,
                )

        # Add or update last-updated date
        updated_span_re = r'<span class="last-updated">[^<]*</span>'
        if stats.get("updated"):
            new_updated = f'<span class="last-updated">⏱ {stats["updated"]}</span>'
            if re.search(updated_span_re, full):
                full = re.sub(updated_span_re, new_updated, full)
            else:
                # Insert after gh-stats div closing
                full = re.sub(
                    r'(</div>\s*)(<span class="metric-sm">)',
                    rf'\1{new_updated}\n      \2',
                    full,
                )

        return full

    html = re.sub(r'<tr>.*?</tr>', replace_row, html, flags=re.DOTALL)
    html = update_missing_language_tags(html, repos)

    # Re-order rows in tables 1 and 2 by star count (descending)
    html = sort_table_rows(html, repos)

    return html


def get_star_count(row: str, repos: dict[str, dict]) -> int:
    """Extract the star count for a table row from the repos dict."""
    link_m = re.search(r'github\.com/([^"]+)', row)
    if not link_m:
        return 0
    slug = link_m.group(1).rstrip("/").lower()
    stats = repos.get(slug)
    return stats.get("stars", 0) if stats else 0


def sort_table_rows(html: str, repos: dict[str, dict]) -> str:
    """Sort <tr> rows by star count within the first two <tbody> sections."""

    def sort_tbody(m: re.Match) -> str:
        tbody_content = m.group(1)
        # Extract all comment + <tr>...</tr> blocks
        row_pattern = r'((?:\s*<!--[^>]*-->\s*)?<tr>.*?</tr>)'
        rows = re.findall(row_pattern, tbody_content, flags=re.DOTALL)
        if not rows:
            return m.group(0)

        # Strip each row and sort by star count descending
        rows = [r.strip() for r in rows]
        rows.sort(key=lambda r: get_star_count(r, repos), reverse=True)

        return "<tbody>\n\n  " + "\n\n  ".join(rows) + "\n\n</tbody>"

    # Apply to first two <tbody>...</tbody> blocks only (tables 1 and 2)
    tbody_re = r'<tbody>(.*?)</tbody>'
    matches = list(re.finditer(tbody_re, html, flags=re.DOTALL))
    for match in reversed(matches[:2]):  # reversed to preserve offsets
        html = html[:match.start()] + sort_tbody(match) + html[match.end():]

    return html


def normalize_language_tag(language: str) -> tuple[str, str] | None:
    """Map a GitHub primary language to the existing badge palette."""
    if not language:
        return None

    mapping = {
        "typescript": ("TypeScript", "tag-ts"),
        "javascript": ("JavaScript", "tag-js"),
        "node.js": ("Node.js", "tag-js"),
        "python": ("Python", "tag-py"),
        "rust": ("Rust", "tag-rust"),
        "go": ("Go", "tag-go"),
        "golang": ("Go", "tag-go"),
        "zig": ("Zig", "tag-zig"),
        "c": ("C", "tag-c"),
        "shell": ("Shell", "tag-shell"),
        "bash": ("Shell", "tag-shell"),
    }
    normalized = mapping.get(language.strip().lower())
    if normalized:
        return normalized
    return language.strip(), "tag-generic"


def row_has_language_info(row: str) -> bool:
    """Return True when the row already exposes a programming language."""
    return bool(LANGUAGE_KEYWORDS_RE.search(row))


def build_language_tag(language: str) -> str | None:
    """Render a Table 1-style language tag for a repo primary language."""
    normalized = normalize_language_tag(language)
    if not normalized:
        return None
    label, class_name = normalized
    return f'<div class="tag {class_name}">{escape(label)}</div>'


def insert_language_tag_into_first_cell(row: str, tag_html: str) -> str:
    """Insert a language tag into the first <td>, preserving any secondary label."""
    first_cell_match = re.search(r'(<td\b[^>]*>)(.*?)(</td>)', row, flags=re.DOTALL)
    if not first_cell_match:
        return row

    cell_open, cell_inner, cell_close = first_cell_match.groups()
    if 'class="tag ' in cell_inner:
        return row

    secondary_match = re.search(r'(<span class="metric-sm">.*?</span>)\s*$', cell_inner, flags=re.DOTALL)
    if secondary_match:
        secondary = secondary_match.group(1)
        secondary = re.sub(r'^<span([^>]*)>', r'<div\1>', secondary)
        secondary = secondary.replace("</span>", "</div>")
        cell_inner = (
            cell_inner[:secondary_match.start()].rstrip()
            + f"\n      {tag_html}\n      {secondary}\n    "
        )
    else:
        cell_inner = cell_inner.rstrip() + f"\n      {tag_html}\n    "

    start, end = first_cell_match.span()
    return row[:start] + cell_open + cell_inner + cell_close + row[end:]


def update_missing_language_tags(html: str, repos: dict[str, dict]) -> str:
    """Fill Table 1-style language tags in the two China tables when a repo exposes one."""

    def replace_row(m: re.Match) -> str:
        row = m.group(0)
        if 'class="tag ' in row or row_has_language_info(row):
            return row

        link_m = re.search(r'href="https://github\.com/([^"]+)"', row)
        if not link_m:
            return row

        slug = link_m.group(1).rstrip("/").lower()
        stats = repos.get(slug)
        if not stats or not stats.get("language"):
            return row

        tag_html = build_language_tag(stats["language"])
        if not tag_html:
            return row
        return insert_language_tag_into_first_cell(row, tag_html)

    for table_id in CHINA_TABLE_IDS:
        table_re = rf'(<table id="{re.escape(table_id)}"[^>]*>.*?<tbody>)(.*?)(</tbody>\s*</table>)'

        def replace_table(m: re.Match) -> str:
            tbody = re.sub(r'<tr\b[^>]*>.*?</tr>', replace_row, m.group(2), flags=re.DOTALL)
            return m.group(1) + tbody + m.group(3)

        html = re.sub(table_re, replace_table, html, flags=re.DOTALL)

    return html


def ensure_css(html: str) -> str:
    """Add missing stat and language-tag CSS helpers if not already present."""
    style_block = ""
    if "<style>" in html:
        style_block = html.split("<style>")[1].split("</style>")[0]

    additions = ""
    tag_additions = ""

    if "tag-shell" not in style_block:
        tag_additions += """
  .tag-shell { background: rgba(244, 114, 182, 0.12); color: var(--accent-pink); }
"""

    if "tag-generic" not in style_block:
        tag_additions += """
  .tag-generic { background: rgba(139, 144, 160, 0.14); color: var(--text-muted); }
"""

    if tag_additions:
        html = re.sub(
            r'(\.tag-js\s*\{[^}]+\})',
            rf'\1\n{tag_additions}',
            html,
        )

    if "commit-count" not in style_block:
        additions += """
  .commit-count {
    font-family: 'JetBrains Mono', monospace;
    font-weight: 500;
    font-size: 12px;
    color: var(--text-muted);
  }
"""

    if "last-updated" not in style_block:
        additions += """
  .last-updated {
    display: block;
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px;
    color: var(--text-muted);
    margin-top: 4px;
    opacity: 0.7;
  }
"""

    if additions:
        html = re.sub(
            r'(\.fork-count\s*\{[^}]+\})',
            rf'\1\n{additions}',
            html,
        )

    return html


def format_footer_timestamp(now: datetime | None = None) -> str:
    """Format the footer timestamp as YYYY-MM-DD HH:MM."""
    if now is None:
        now = datetime.now()
    return now.strftime(FOOTER_TIMESTAMP_FORMAT)


def update_footer_date(html: str, timestamp: str) -> str:
    """Update the 'Last updated' date and time in the footer."""
    html = re.sub(
        r'(<span id="last-updated-date">)[^<]*(</span>)',
        rf'\g<1>{timestamp}\2',
        html,
    )
    return html


def extract_repo_slugs(html: str) -> list[str]:
    """Pull all owner/repo slugs from name-cell or gh-link hrefs."""
    slugs = re.findall(r'href="https://github\.com/([^"]+)"', html)
    # Deduplicate while preserving order
    seen = set()
    unique = []
    for s in slugs:
        s_clean = s.rstrip("/").lower()
        if s_clean not in seen:
            seen.add(s_clean)
            unique.append(s.rstrip("/"))
    return unique


def collect_html_paths(files: list[str] | None) -> list[Path]:
    """Resolve HTML files from CLI args or default to all top-level HTML files."""
    if files:
        return [Path(file) for file in files]
    return sorted(Path(".").glob("*.html"))


def update_html_file(
    html_path: Path,
    html: str,
    repos: dict[str, dict],
    timestamp: str,
    has_repo_links: bool,
) -> bool:
    """Update one HTML file and refresh its footer on every run."""
    updated_html = html
    if has_repo_links:
        updated_html = ensure_css(updated_html)
        updated_html = update_html(updated_html, repos)
    updated_html = update_footer_date(updated_html, timestamp)

    if updated_html == html:
        return False

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(updated_html)
    return True


def main():
    parser = argparse.ArgumentParser(description="Update GitHub stats in HTML files")
    parser.add_argument(
        "--file",
        action="append",
        dest="files",
        help="Path to an HTML file. Pass multiple times to update more than one file. Defaults to all *.html files.",
    )
    args = parser.parse_args()

    html_paths = collect_html_paths(args.files)
    if not html_paths:
        print("❌ No HTML files found.")
        sys.exit(1)

    missing_paths = [str(path) for path in html_paths if not os.path.exists(path)]
    if missing_paths:
        print(f"❌ File not found: {missing_paths[0]}")
        sys.exit(1)

    html_inputs: list[tuple[Path, str, bool]] = []
    all_slugs: list[str] = []

    for html_path in html_paths:
        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()

        slugs = extract_repo_slugs(html)
        if not slugs:
            print(f"→ {html_path} … footer only (no GitHub repo links found)")
            html_inputs.append((html_path, html, False))
            continue

        html_inputs.append((html_path, html, True))
        all_slugs.extend(slugs)

    if not all_slugs:
        print("No GitHub repo links found. Refreshing footer timestamps only.\n")

    unique_slugs: list[str] = []
    if all_slugs:
        seen_slugs: set[str] = set()
        for slug in all_slugs:
            slug_clean = slug.rstrip("/").lower()
            if slug_clean not in seen_slugs:
                seen_slugs.add(slug_clean)
                unique_slugs.append(slug.rstrip("/"))

        print(f"Found {len(unique_slugs)} repos across {len(html_inputs)} HTML file(s).\n")

    repos: dict[str, dict] = {}
    for slug in unique_slugs:
        slug_clean = slug.rstrip("/")
        parts = slug_clean.split("/", 1)
        if len(parts) != 2:
            continue
        owner, repo = parts
        print(f"→ {owner}/{repo} …", end=" ", flush=True)
        stats = fetch_repo_stats(owner, repo)
        if stats:
            repos[slug_clean.lower()] = stats
            c = fmt_number(stats["commits"]) if stats.get("commits") else "?"
            upd = stats.get("updated", "?")
            print(f"★ {fmt_number(stats['stars'])}  ⑂ {fmt_number(stats['forks'])}  "
                  f"⟳ {c}  ⏱ {upd}")
        else:
            print("SKIPPED (not found)")

    timestamp = format_footer_timestamp()
    changed_files = 0
    for html_path, html, has_repo_links in html_inputs:
        if update_html_file(html_path, html, repos, timestamp, has_repo_links):
            changed_files += 1
            print(f"✅ Updated {html_path}")
        else:
            print(f"✓ No changes in {html_path}")

    print(f"\n✅ Updated {len(repos)} repos across {changed_files} HTML file(s)")


if __name__ == "__main__":
    main()
