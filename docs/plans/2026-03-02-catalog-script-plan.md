# Flipper Zero Catalog Script — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Python script that fetches Flipper Zero apps from the Official Catalog API + awesome-flipperzero, generates a categorized README.md with 123fzero's apps featured first.

**Architecture:** Single Python script with functions for each data source. Fetches categories and apps from the official API (list endpoint only — avoids 322 detail calls). Parses awesome-flipperzero markdown for extra sections. Uses GitHub API for 123fzero repos. Generates README.md and `site/catalog.json`. GitHub Action runs it daily, then GitHub Pages deploys the updated site.

**Tech Stack:** Python 3.10+, `requests`, GitHub Actions

---

### Task 1: Create script skeleton and requirements

**Files:**
- Create: `scripts/update_catalog.py`
- Create: `scripts/requirements.txt`

**Step 1: Create requirements.txt**

```
requests>=2.28.0
```

**Step 2: Create script skeleton with constants and main()**

```python
#!/usr/bin/env python3
"""Generates README.md catalog of Flipper Zero apps."""

import re
import sys
import json
import time
from pathlib import Path
from urllib.parse import quote

import requests

CATALOG_API = "https://catalog.flipperzero.one/api/v0"
AWESOME_RAW_URL = "https://raw.githubusercontent.com/djsime1/awesome-flipperzero/main/README.md"
GITHUB_API = "https://api.github.com"
FEATURED_OWNER = "123fzero"
LAB_URL = "https://lab.flipper.net/apps"
REPO_ROOT = Path(__file__).resolve().parent.parent
README_PATH = REPO_ROOT / "README.md"
REQUEST_TIMEOUT = 30
PAGE_LIMIT = 100


def main():
    print("Fetching 123fzero repos...")
    featured_repos = fetch_123fzero_repos()

    print("Fetching official catalog...")
    categories, catalog_apps = fetch_official_catalog()

    print("Fetching awesome-flipperzero...")
    awesome_sections = fetch_awesome_list()

    print("Generating README.md...")
    readme = generate_readme(categories, catalog_apps, awesome_sections, featured_repos)

    README_PATH.write_text(readme, encoding="utf-8")
    print(f"Done! Written to {README_PATH}")


if __name__ == "__main__":
    main()
```

**Step 3: Install deps and verify script runs (with stubs)**

Run: `cd /Users/colinfrl/work/123fzero/123Games && pip install -r scripts/requirements.txt`

**Step 4: Commit**

```bash
git add scripts/update_catalog.py scripts/requirements.txt
git commit -m "feat: add catalog script skeleton and requirements"
```

---

### Task 2: Implement fetch_123fzero_repos()

**Files:**
- Modify: `scripts/update_catalog.py`

**Step 1: Add function that fetches 123fzero's public repos via GitHub API**

```python
def fetch_123fzero_repos():
    """Fetch public repos for 123fzero. Returns dict of lowercase repo name -> repo info."""
    url = f"{GITHUB_API}/users/{FEATURED_OWNER}/repos"
    params = {"per_page": 100, "type": "public"}
    headers = {"Accept": "application/vnd.github.v3+json"}
    resp = requests.get(url, params=params, headers=headers, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    repos = {}
    for repo in resp.json():
        repos[repo["name"].lower()] = {
            "name": repo["name"],
            "description": repo.get("description") or "",
            "url": repo["html_url"],
            "topics": repo.get("topics", []),
        }
    return repos
```

**Step 2: Verify by running**

Run: `cd /Users/colinfrl/work/123fzero/123Games && python3 -c "from scripts.update_catalog import fetch_123fzero_repos; import json; print(json.dumps(fetch_123fzero_repos(), indent=2))"`

Expected: JSON with 123DiceDnD, 123PuffPacer, etc.

**Step 3: Commit**

```bash
git add scripts/update_catalog.py
git commit -m "feat: add fetch_123fzero_repos function"
```

---

### Task 3: Implement fetch_official_catalog()

**Files:**
- Modify: `scripts/update_catalog.py`

**Step 1: Add function to fetch categories and all apps per category from official API**

```python
def fetch_official_catalog():
    """Fetch all categories and apps from the official Flipper catalog API.

    Returns:
        categories: list of {id, name, priority, applications}
        apps_by_category: dict of category_id -> list of app dicts
    """
    # Fetch categories
    resp = requests.get(f"{CATALOG_API}/category", timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    categories = sorted(resp.json(), key=lambda c: c.get("priority", 0))

    apps_by_category = {}
    for cat in categories:
        cat_id = cat["_id"]
        apps = []
        offset = 0
        while True:
            params = {
                "category_id": cat_id,
                "limit": PAGE_LIMIT,
                "offset": offset,
                "sort_by": "updated_at",
                "order": "desc",
            }
            resp = requests.get(
                f"{CATALOG_API}/application",
                params=params,
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            batch = resp.json()
            if not batch:
                break
            for app in batch:
                cv = app.get("current_version", {})
                apps.append({
                    "name": cv.get("name", app.get("alias", "Unknown")),
                    "description": cv.get("short_description", ""),
                    "author": app.get("author", ""),
                    "alias": app.get("alias", ""),
                    "app_url": f"{LAB_URL}/{app.get('alias', '')}",
                })
            offset += PAGE_LIMIT
            if len(batch) < PAGE_LIMIT:
                break
            time.sleep(0.2)  # Be polite to the API

        apps.sort(key=lambda a: a["name"].lower())
        apps_by_category[cat_id] = apps

    return categories, apps_by_category
```

**Step 2: Verify by running**

Run: `cd /Users/colinfrl/work/123fzero/123Games && python3 -c "
from scripts.update_catalog import fetch_official_catalog
cats, apps = fetch_official_catalog()
for c in cats:
    print(f'{c[\"name\"]}: {len(apps.get(c[\"_id\"], []))} apps')
"`

Expected: List of 11 categories with app counts.

**Step 3: Commit**

```bash
git add scripts/update_catalog.py
git commit -m "feat: add fetch_official_catalog function"
```

---

### Task 4: Implement fetch_awesome_list()

**Files:**
- Modify: `scripts/update_catalog.py`

**Step 1: Add markdown parser for awesome-flipperzero README**

This parses the awesome-flipperzero markdown into sections. We only extract sections that DON'T overlap with the official catalog (i.e., skip "Applications & Plugins" since that's covered by the API).

```python
# Sections from awesome-flipperzero to include (these don't overlap with official catalog)
AWESOME_SECTIONS_TO_INCLUDE = [
    "Databases & Dumps",
    "Firmwares & Tweaks",
    "Graphics & Animations",
    "Modules & Cases",
    "Off-device & Debugging",
    "Notes & References",
]


def fetch_awesome_list():
    """Fetch and parse awesome-flipperzero README into sections.

    Returns: list of {title, entries: [{name, url, description}]}
    """
    resp = requests.get(AWESOME_RAW_URL, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    text = resp.text

    sections = []
    current_section = None
    current_subsection = None
    entries = []

    for line in text.split("\n"):
        # Match ## headers (main sections)
        h2_match = re.match(r"^## (.+?)(?:\s*<small>.*)?$", line.strip())
        if h2_match:
            # Save previous section
            if current_section and entries:
                sections.append({"title": current_section, "entries": entries})
            title = h2_match.group(1).strip()
            if title in AWESOME_SECTIONS_TO_INCLUDE:
                current_section = title
                entries = []
            else:
                current_section = None
                entries = []
            continue

        # Match ### headers (subsections) — just track for context
        h3_match = re.match(r"^### (.+)$", line.strip())
        if h3_match and current_section:
            current_subsection = h3_match.group(1).strip()
            continue

        # Match list entries: - [Name](URL) - Description
        if current_section:
            entry_match = re.match(
                r"^-\s+\[([^\]]+)\]\(([^)]+)\)\s*[-–—]\s*(.+)$", line.strip()
            )
            if entry_match:
                entries.append({
                    "name": entry_match.group(1),
                    "url": entry_match.group(2),
                    "description": entry_match.group(3).rstrip("."),
                    "subsection": current_subsection or "",
                })

    # Don't forget the last section
    if current_section and entries:
        sections.append({"title": current_section, "entries": entries})

    return sections
```

**Step 2: Verify by running**

Run: `cd /Users/colinfrl/work/123fzero/123Games && python3 -c "
from scripts.update_catalog import fetch_awesome_list
sections = fetch_awesome_list()
for s in sections:
    print(f'{s[\"title\"]}: {len(s[\"entries\"])} entries')
"`

Expected: Several sections with entry counts.

**Step 3: Commit**

```bash
git add scripts/update_catalog.py
git commit -m "feat: add fetch_awesome_list parser"
```

---

### Task 5: Implement generate_readme()

**Files:**
- Modify: `scripts/update_catalog.py`

**Step 1: Add helper to check if an app is from 123fzero**

```python
def is_featured(app, featured_repos):
    """Check if an app belongs to 123fzero."""
    author = app.get("author", "").lower()
    if FEATURED_OWNER.lower() in author:
        return True
    url = app.get("url", app.get("app_url", "")).lower()
    if f"github.com/{FEATURED_OWNER.lower()}" in url:
        return True
    # Check by alias/name match against 123fzero repo names
    alias = app.get("alias", "").lower()
    name = app.get("name", "").lower().replace(" ", "")
    for repo_name in featured_repos:
        clean_repo = repo_name.replace("123", "").lower()
        if clean_repo and (clean_repo in alias or clean_repo in name):
            return True
    return False
```

**Step 2: Add the main README generator**

```python
def generate_readme(categories, catalog_apps, awesome_sections, featured_repos):
    """Generate the full README.md content."""
    lines = []

    # Header
    lines.append("# 123 Games")
    lines.append("")
    lines.append(
        "A catalog of Flipper Zero apps and games. "
        "Maintained by [123fzero](https://github.com/123fzero). "
        "Auto-generated from the [Official Flipper App Catalog](https://lab.flipper.net/apps) "
        "and [awesome-flipperzero](https://github.com/djsime1/awesome-flipperzero)."
    )
    lines.append("")

    # Table of Contents
    lines.append("## Table of Contents")
    lines.append("")
    lines.append("**Official Catalog**")
    lines.append("")
    for cat in categories:
        anchor = cat["name"].lower().replace(" ", "-").replace("/", "")
        lines.append(f"- [{cat['name']}](#{anchor})")
    lines.append("")
    if awesome_sections:
        lines.append("**Community Resources**")
        lines.append("")
        for section in awesome_sections:
            anchor = section["title"].lower().replace(" ", "-").replace("&", "").replace("  ", "-")
            lines.append(f"- [{section['title']}](#{anchor})")
        lines.append("")

    lines.append("---")
    lines.append("")

    # Official Catalog sections
    lines.append("# Official Catalog")
    lines.append("")
    lines.append(f"> Apps from [lab.flipper.net]({LAB_URL})")
    lines.append("")

    for cat in categories:
        cat_id = cat["_id"]
        apps = catalog_apps.get(cat_id, [])
        lines.append(f"## {cat['name']}")
        lines.append("")

        if not apps:
            lines.append("*No apps in this category.*")
            lines.append("")
            continue

        # Split into featured and regular
        featured = [a for a in apps if is_featured(a, featured_repos)]
        regular = [a for a in apps if not is_featured(a, featured_repos)]

        if featured:
            for app in featured:
                # Try to find the original repo URL for featured apps
                repo_url = None
                for repo_info in featured_repos.values():
                    clean_repo = repo_info["name"].replace("123", "").lower()
                    if clean_repo and (
                        clean_repo in app.get("alias", "").lower()
                        or clean_repo in app.get("name", "").lower().replace(" ", "")
                    ):
                        repo_url = repo_info["url"]
                        break
                source_link = f"[GitHub]({repo_url})" if repo_url else f"[Catalog]({app['app_url']})"
                lines.append(
                    f"| ⭐ | **[{app['name']}]({app['app_url']})** | "
                    f"{app['description']} | {app['author']} | {source_link} |"
                )

        # Table header
        lines.append("")
        lines.append("| | App | Description | Author | Link |")
        lines.append("|---|-----|-------------|--------|------|")

        if featured:
            for app in featured:
                repo_url = None
                for repo_info in featured_repos.values():
                    clean_repo = repo_info["name"].replace("123", "").lower()
                    if clean_repo and (
                        clean_repo in app.get("alias", "").lower()
                        or clean_repo in app.get("name", "").lower().replace(" ", "")
                    ):
                        repo_url = repo_info["url"]
                        break
                source_link = f"[GitHub]({repo_url})" if repo_url else f"[Catalog]({app['app_url']})"
                lines.append(
                    f"| ⭐ | **[{app['name']}]({app['app_url']})** | "
                    f"{app['description']} | {app['author']} | {source_link} |"
                )

        for app in regular:
            lines.append(
                f"| | [{app['name']}]({app['app_url']}) | "
                f"{app['description']} | {app['author']} | [Catalog]({app['app_url']}) |"
            )

        lines.append("")

    # Awesome-flipperzero sections
    if awesome_sections:
        lines.append("---")
        lines.append("")
        lines.append("# Community Resources")
        lines.append("")
        lines.append(
            "> From [awesome-flipperzero](https://github.com/djsime1/awesome-flipperzero)"
        )
        lines.append("")

        for section in awesome_sections:
            lines.append(f"## {section['title']}")
            lines.append("")

            # Group by subsection
            subsections = {}
            for entry in section["entries"]:
                sub = entry.get("subsection", "")
                subsections.setdefault(sub, []).append(entry)

            for sub_name, entries in subsections.items():
                if sub_name:
                    lines.append(f"### {sub_name}")
                    lines.append("")

                # Check for featured entries
                featured_entries = [e for e in entries if is_featured(e, featured_repos)]
                regular_entries = [e for e in entries if not is_featured(e, featured_repos)]

                for entry in featured_entries:
                    lines.append(
                        f"- ⭐ **[{entry['name']}]({entry['url']})** — {entry['description']}"
                    )
                for entry in regular_entries:
                    lines.append(
                        f"- [{entry['name']}]({entry['url']}) — {entry['description']}"
                    )
                lines.append("")

    # Footer
    lines.append("---")
    lines.append("")
    lines.append(
        "*This catalog is auto-generated. "
        "Run `python scripts/update_catalog.py` to update.*"
    )
    lines.append("")

    return "\n".join(lines)
```

**Step 3: Run the full script and verify output**

Run: `cd /Users/colinfrl/work/123fzero/123Games && python3 scripts/update_catalog.py`

Then check README.md looks correct.

**Step 4: Commit**

```bash
git add scripts/update_catalog.py
git commit -m "feat: add generate_readme with featured app prioritization"
```

---

### Task 6: Create GitHub Action for automated updates

**Files:**
- Create: `.github/workflows/update-catalog.yml`

**Step 1: Create the workflow file**

```yaml
name: Update Catalog

on:
  schedule:
    - cron: '0 6 * * *'  # Every day at 06:00 UTC
  workflow_dispatch:  # Manual trigger

permissions:
  contents: write

jobs:
  update:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: pip install -r scripts/requirements.txt

      - name: Run catalog update
        run: python scripts/update_catalog.py

      - name: Commit and push if changed
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git diff --quiet README.md || {
            git add README.md
            git commit -m "chore: update app catalog $(date +%Y-%m-%d)"
            git push
          }
```

**Step 2: Commit**

```bash
git add .github/workflows/update-catalog.yml
git commit -m "ci: add GitHub Action for daily catalog updates"
```

---

### Task 7: Final run, review, and commit everything

**Step 1: Run the full script**

Run: `python scripts/update_catalog.py`

**Step 2: Review the generated README.md**

Check:
- 123fzero apps appear first in their categories with ⭐
- All 11 official categories are present
- Awesome-flipperzero community sections are present
- Links work correctly
- Table formatting is correct

**Step 3: Fix any issues found during review**

**Step 4: Final commit**

```bash
git add -A
git commit -m "feat: complete Flipper Zero app catalog with auto-update script"
```
