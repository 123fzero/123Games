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

# Map 123fzero repo names to catalog category names.
# Repos not listed here (or listed as None) are skipped.
FEATURED_REPO_CATEGORIES = {
    "123dicednd": "Games",
    "123puffpacer": "Tools",
    "123periodictimer": "Tools",
    "123pomadoro": "Tools",
    # Skip non-app repos
    "123games": None,
    "flipper-zero-awesome": None,
}

# Sections from awesome-flipperzero to include (these don't overlap with official catalog)
AWESOME_SECTIONS_TO_INCLUDE = [
    "Databases & Dumps",
    "Firmwares & Tweaks",
    "Graphics & Animations",
    "Modules & Cases",
    "Off-device & Debugging",
    "Notes & References",
]


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

def fetch_official_catalog():
    """Fetch all categories and apps from the official Flipper catalog API.

    Returns:
        categories: list of {id, name, priority, applications} sorted by priority
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

def fetch_awesome_list():
    """Fetch and parse awesome-flipperzero README into sections.

    Returns: list of {title, entries: [{name, url, description, subsection}]}
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

        # Match ### headers (subsections) — track for context
        h3_match = re.match(r"^### (.+)$", line.strip())
        if h3_match and current_section:
            current_subsection = h3_match.group(1).strip().strip("*")
            continue

        # Match list entries in two formats:
        # Format 1: - [Name](URL) - Description
        # Format 2: - [`Name` Description.](URL) (actual awesome-flipperzero format)
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
            else:
                bt_match = re.match(
                    r"^-\s+\[`([^`]+)`\s+(.+?)\]\(([^)]+)\)$", line.strip()
                )
                if bt_match:
                    entries.append({
                        "name": bt_match.group(1),
                        "url": bt_match.group(3),
                        "description": bt_match.group(2).rstrip("."),
                        "subsection": current_subsection or "",
                    })

    # Don't forget the last section
    if current_section and entries:
        sections.append({"title": current_section, "entries": entries})

    return sections

def _build_featured_by_category(featured_repos):
    """Build a dict of category_name -> list of featured app entries from 123fzero repos."""
    by_cat = {}
    for repo_key, repo_info in featured_repos.items():
        cat_name = FEATURED_REPO_CATEGORIES.get(repo_key)
        if not cat_name:
            continue
        by_cat.setdefault(cat_name, []).append({
            "name": repo_info["name"],
            "description": repo_info["description"],
            "author": FEATURED_OWNER,
            "url": repo_info["url"],
        })
    return by_cat


def generate_readme(categories, catalog_apps, awesome_sections, featured_repos):
    """Generate the full README.md content."""
    lines = []
    featured_by_cat = _build_featured_by_category(featured_repos)

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
        cat_name = cat["name"]
        apps = catalog_apps.get(cat_id, [])
        featured = featured_by_cat.get(cat_name, [])

        lines.append(f"## {cat_name}")
        lines.append("")

        if not apps and not featured:
            lines.append("*No apps in this category.*")
            lines.append("")
            continue

        # Table header
        lines.append("| | App | Description | Author | Link |")
        lines.append("|---|-----|-------------|--------|------|")

        # Featured 123fzero apps first
        for app in featured:
            lines.append(
                f"| ⭐ | **[{app['name']}]({app['url']})** | "
                f"{app['description']} | {app['author']} | [GitHub]({app['url']}) |"
            )

        # All catalog apps
        for app in apps:
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

                for entry in entries:
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
