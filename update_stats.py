#!/usr/bin/env python3
"""
Fetch live GitHub stats (stars, forks, commits, last update) and update index.html.
Tables 1 (frameworks) and 2 (harnesses) are updated in-place.

Requirements: gh CLI (authenticated)
Usage:       python3 update_stats.py [--file index.html]
"""

import argparse
import json
import os
import re
import subprocess
import sys


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
    """Return {stars, forks, commits, emoji, pushed_at} for one repo."""
    info = gh_api(f"repos/{owner}/{repo}")
    if not info or not isinstance(info, dict):
        return {}

    stars = info.get("stargazers_count", 0)
    forks = info.get("forks_count", 0)
    pushed_at = info.get("pushed_at", "")  # ISO 8601: "2026-03-15T..."

    commits = get_commit_count(owner, repo)

    topics = [t.lower() for t in (info.get("topics") or [])]
    lang = (info.get("language") or "").lower()
    emoji = pick_emoji(topics, lang, info.get("description", ""))

    # Format pushed_at to "Mar 2026" style
    updated = ""
    if pushed_at:
        from datetime import datetime
        dt = datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
        updated = dt.strftime("%b %d, %Y")

    return {
        "stars": stars,
        "forks": forks,
        "commits": commits,
        "emoji": emoji,
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
    """Find each gh-stats block and update stars, forks, commits, and last updated."""

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


def ensure_css(html: str) -> str:
    """Add .commit-count and .last-updated CSS if not already present."""
    style_block = ""
    if "<style>" in html:
        style_block = html.split("<style>")[1].split("</style>")[0]

    additions = ""

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


def update_footer_date(html: str) -> str:
    """Update the 'Last updated' date in the footer to today."""
    from datetime import datetime
    today = datetime.now().strftime("%B %d, %Y")
    html = re.sub(
        r'(<span id="last-updated-date">)[^<]*(</span>)',
        rf'\g<1>{today}\2',
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


def main():
    parser = argparse.ArgumentParser(description="Update GitHub stats in index.html")
    parser.add_argument("--file", default="index.html",
                        help="Path to HTML file (default: index.html)")
    args = parser.parse_args()

    html_path = args.file
    if not os.path.exists(html_path):
        print(f"❌ File not found: {html_path}")
        sys.exit(1)

    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    slugs = extract_repo_slugs(html)
    if not slugs:
        print("❌ No GitHub repo links found in the HTML.")
        sys.exit(1)

    print(f"Found {len(slugs)} repos to update.\n")

    repos: dict[str, dict] = {}
    for slug in slugs:
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

    # Update HTML
    html = ensure_css(html)
    html = update_html(html, repos)
    html = update_footer_date(html)

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n✅ Updated {len(repos)} repos in {html_path}")


if __name__ == "__main__":
    main()
