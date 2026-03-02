#!/usr/bin/env python3
"""Generates README.md catalog of Flipper Zero apps."""

import os
import re
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

CATALOG_API = "https://catalog.flipperzero.one/api/v0"
AWESOME_RAW_URL = "https://raw.githubusercontent.com/djsime1/awesome-flipperzero/main/README.md"
GITHUB_API = "https://api.github.com"
FEATURED_OWNER = "123fzero"
LAB_URL = "https://lab.flipper.net/apps"
README_PATH = Path(__file__).resolve().parent.parent / "README.md"
REQUEST_TIMEOUT = 30
PAGE_LIMIT = 100
OFFICIAL_EMOJI = "🏛️"
COMMUNITY_EMOJI = "💎"

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

# Community sections whose subsection names should be merged into official categories.
AWESOME_APP_SECTION_TITLES = {
    "Applications & Plugins",
    "Applications and Plugins",
}

SECTION_NAME_ALIASES = {
    "subghz": "Sub-GHz",
    "sub-ghz": "Sub-GHz",
    "rf": "Sub-GHz",
    "lfrfid": "RFID",
    "125 khz rfid": "RFID",
    "infra-red": "Infrared",
    "infra red": "Infrared",
    "ibutton / 1-wire": "iButton",
    "1-wire": "iButton",
    "1 wire": "iButton",
    "usb / badusb": "USB",
    "badusb": "USB",
    "ble": "Bluetooth",
}


def _github_headers():
    headers = {"Accept": "application/vnd.github.v3+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"token {token}"
    return headers


def _sanitize_table_cell(text):
    """Remove characters that break markdown tables."""
    return str(text or "").replace("\n", " ").replace("\r", "").replace("|", "/").strip()


def _make_anchor(text):
    """Generate a GitHub-compatible markdown anchor from heading text."""
    anchor = text.lower()
    anchor = re.sub(r"[^\w\s-]", "", anchor)
    anchor = re.sub(r"\s+", "-", anchor)
    return anchor


def _normalize_name(text):
    return re.sub(r"[^a-z0-9]+", "", str(text or "").lower())


def _normalize_section_name(name):
    clean = _sanitize_table_cell(name)
    alias = SECTION_NAME_ALIASES.get(clean.lower())
    return alias or clean


def _normalize_url(url):
    clean = (url or "").strip()
    if not clean:
        return ""
    clean = clean.rstrip("/")
    if clean.endswith(".git"):
        clean = clean[:-4]
    return clean


def _extract_github_repo(url):
    parsed = urlparse(url or "")
    if parsed.netloc.lower() not in {"github.com", "www.github.com"}:
        return None
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2:
        return None
    owner, repo = parts[0], parts[1]
    if repo.endswith(".git"):
        repo = repo[:-4]
    return f"{owner}/{repo}"


def _extract_catalog_repo_url(app, current_version):
    """Best-effort extraction of source repo URL from catalog payload variations."""
    candidate_sets = [
        current_version.get("links") or [],
        app.get("links") or [],
    ]
    for links in candidate_sets:
        for link in links:
            if not isinstance(link, dict):
                continue
            url = link.get("url") or link.get("href")
            if not url:
                continue
            link_type = str(link.get("type") or link.get("title") or "").lower()
            if "source" in link_type or "github" in link_type:
                return _normalize_url(url)

    candidates = [
        current_version.get("source_code_url"),
        app.get("source_code_url"),
        current_version.get("github"),
        app.get("github"),
        current_version.get("source"),
        app.get("source"),
    ]
    for candidate in candidates:
        if candidate:
            return _normalize_url(candidate)
    return ""


def _extract_catalog_rating(app, current_version):
    """Best-effort extraction of a displayable rating from catalog payload variations."""
    candidates = [
        current_version.get("rating"),
        app.get("rating"),
        current_version.get("score"),
        app.get("score"),
        current_version.get("stars"),
        app.get("stars"),
    ]
    for candidate in candidates:
        if candidate in (None, ""):
            continue
        if isinstance(candidate, (int, float)):
            return f"{candidate:g}"
        return _sanitize_table_cell(candidate)
    return ""


def _format_stars(count):
    if count is None:
        return ""
    if count >= 1000:
        value = round(count / 1000, 1)
        text = f"{value:g}k"
    else:
        text = str(count)
    return f"⭐ {text}"


def _merge_text(preferred, fallback):
    preferred = _sanitize_table_cell(preferred)
    fallback = _sanitize_table_cell(fallback)
    return preferred or fallback


def fetch_123fzero_repos():
    """Fetch public repos for 123fzero. Returns dict of lowercase repo name -> repo info."""
    url = f"{GITHUB_API}/users/{FEATURED_OWNER}/repos"
    params = {"per_page": 100, "type": "public"}
    resp = requests.get(
        url,
        params=params,
        headers=_github_headers(),
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    repos = {}
    for repo in resp.json():
        repos[repo["name"].lower()] = {
            "name": repo["name"],
            "description": _sanitize_table_cell(repo.get("description") or ""),
            "url": _normalize_url(repo["html_url"]),
            "stars": repo.get("stargazers_count"),
        }
    return repos


def fetch_official_catalog():
    """Fetch all categories and apps from the official Flipper catalog API."""
    resp = requests.get(f"{CATALOG_API}/category", timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    categories = sorted(resp.json(), key=lambda c: c.get("priority", 0))

    apps_by_category = {}
    for category in categories:
        category_id = category["_id"]
        apps = []
        offset = 0
        while True:
            params = {
                "category_id": category_id,
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
                current_version = app.get("current_version", {})
                app_url = f"{LAB_URL}/{app.get('alias', '')}"
                repo_url = _extract_catalog_repo_url(app, current_version)
                apps.append({
                    "name": _sanitize_table_cell(
                        current_version.get("name", app.get("alias", "Unknown"))
                    ),
                    "description": _sanitize_table_cell(
                        current_version.get("short_description", "")
                    ),
                    "author": _sanitize_table_cell(app.get("author", "")),
                    "official_url": app_url,
                    "repo_url": repo_url,
                    "rating": _extract_catalog_rating(app, current_version),
                })

            offset += PAGE_LIMIT
            if len(batch) < PAGE_LIMIT:
                break
            time.sleep(0.2)

        apps.sort(key=lambda item: item["name"].lower())
        apps_by_category[category_id] = apps

    return categories, apps_by_category


def fetch_awesome_list():
    """Fetch and parse awesome-flipperzero README into sections."""
    resp = requests.get(AWESOME_RAW_URL, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()

    sections = []
    current_section = None
    current_subsection = ""
    entries = []

    for raw_line in resp.text.splitlines():
        line = raw_line.strip()

        h2_match = re.match(r"^## (.+?)(?:\s*<small>.*)?$", line)
        if h2_match:
            if current_section and entries:
                sections.append({"title": current_section, "entries": entries})
            current_section = _sanitize_table_cell(h2_match.group(1))
            current_subsection = ""
            entries = []
            continue

        h3_match = re.match(r"^### (.+)$", line)
        if h3_match and current_section:
            current_subsection = _sanitize_table_cell(h3_match.group(1).strip("*"))
            continue

        if not current_section:
            continue

        entry_match = re.match(
            r"^-\s+\[([^\]]+)\]\(([^)]+)\)\s*[-–—]\s*(.+)$",
            line,
        )
        if not entry_match:
            entry_match = re.match(
                r"^-\s+\[`([^`]+)`\s+(.+?)\]\(([^)]+)\)$",
                line,
            )
            if entry_match:
                name, description, url = entry_match.groups()
            else:
                continue
        else:
            name, url, description = entry_match.groups()

        clean_url = _normalize_url(url)
        entries.append({
            "name": _sanitize_table_cell(name),
            "description": _sanitize_table_cell(description).rstrip("."),
            "section": current_section,
            "subsection": current_subsection,
            "community_url": clean_url,
            "repo_url": clean_url if _extract_github_repo(clean_url) else "",
            "author": "",
            "rating": "",
        })

    if current_section and entries:
        sections.append({"title": current_section, "entries": entries})

    return sections


def _build_featured_by_category(featured_repos):
    by_category = {}
    for repo_key, repo_info in featured_repos.items():
        category_name = FEATURED_REPO_CATEGORIES.get(repo_key)
        if not category_name:
            continue
        description = repo_info["description"] or f"Flipper Zero app by {FEATURED_OWNER}"
        by_category.setdefault(category_name, []).append({
            "name": repo_info["name"],
            "description": description,
            "author": FEATURED_OWNER,
            "community_url": repo_info["url"],
            "repo_url": repo_info["url"],
            "rating": _format_stars(repo_info.get("stars")),
        })
    return by_category


def _section_order(categories, awesome_sections):
    ordered = [_sanitize_table_cell(category["name"]) for category in categories]
    seen = {_normalize_name(name) for name in ordered}

    for section in awesome_sections:
        title = _sanitize_table_cell(section["title"])
        if title in AWESOME_APP_SECTION_TITLES:
            for entry in section["entries"]:
                if not entry.get("subsection"):
                    continue
                target = _normalize_section_name(entry["subsection"])
                key = _normalize_name(target)
                if key not in seen:
                    ordered.append(target)
                    seen.add(key)
        else:
            key = _normalize_name(title)
            if key not in seen:
                ordered.append(title)
                seen.add(key)

    return ordered


def _entry_key(section_name, entry):
    for candidate in (
        entry.get("repo_url"),
        entry.get("official_url"),
        entry.get("community_url"),
    ):
        normalized = _normalize_url(candidate)
        if normalized:
            return f"url:{normalized}"
    return f"name:{_normalize_name(section_name)}:{_normalize_name(entry.get('name', ''))}"


def _empty_row(section_name):
    return {
        "section": section_name,
        "name": "",
        "description": "",
        "author": "",
        "rating": "",
        "official_url": "",
        "community_url": "",
        "repo_url": "",
        "sources": set(),
        "subsection": "",
    }


def _merge_entry(rows_by_section, section_name, incoming):
    section_rows = rows_by_section.setdefault(section_name, {})
    key = _entry_key(section_name, incoming)
    row = section_rows.get(key)
    if row is None:
        row = _empty_row(section_name)
        section_rows[key] = row

    row["name"] = _merge_text(row["name"], incoming.get("name"))
    row["description"] = _merge_text(row["description"], incoming.get("description"))
    row["author"] = _merge_text(row["author"], incoming.get("author"))
    row["rating"] = _merge_text(row["rating"], incoming.get("rating"))
    row["official_url"] = _merge_text(row["official_url"], incoming.get("official_url"))
    row["community_url"] = _merge_text(row["community_url"], incoming.get("community_url"))
    row["repo_url"] = _merge_text(row["repo_url"], incoming.get("repo_url"))
    row["subsection"] = _merge_text(row["subsection"], incoming.get("subsection"))
    row["sources"].update(incoming.get("sources", set()))


def _collect_rows(categories, catalog_apps, awesome_sections, featured_repos):
    rows_by_section = {}
    section_order = _section_order(categories, awesome_sections)
    featured_by_category = _build_featured_by_category(featured_repos)

    for category in categories:
        section_name = _sanitize_table_cell(category["name"])

        for featured in featured_by_category.get(section_name, []):
            _merge_entry(
                rows_by_section,
                section_name,
                {
                    **featured,
                    "sources": {"community"},
                },
            )

        for app in catalog_apps.get(category["_id"], []):
            _merge_entry(
                rows_by_section,
                section_name,
                {
                    **app,
                    "sources": {"official"},
                },
            )

    for section in awesome_sections:
        title = _sanitize_table_cell(section["title"])
        for entry in section["entries"]:
            if title in AWESOME_APP_SECTION_TITLES and entry.get("subsection"):
                target_section = _normalize_section_name(entry["subsection"])
                subsection = ""
            else:
                target_section = title
                subsection = entry.get("subsection", "")

            if _normalize_name(target_section) not in {
                _normalize_name(name) for name in section_order
            }:
                section_order.append(target_section)

            _merge_entry(
                rows_by_section,
                target_section,
                {
                    **entry,
                    "subsection": subsection,
                    "sources": {"community"},
                },
            )

    return section_order, rows_by_section


def _fill_missing_ratings(rows_by_section):
    cache = {}
    for section_rows in rows_by_section.values():
        for row in section_rows.values():
            if row["rating"] or not row["repo_url"]:
                continue
            repo = _extract_github_repo(row["repo_url"])
            if not repo:
                continue
            if repo not in cache:
                try:
                    resp = requests.get(
                        f"{GITHUB_API}/repos/{repo}",
                        headers=_github_headers(),
                        timeout=REQUEST_TIMEOUT,
                    )
                    resp.raise_for_status()
                    cache[repo] = _format_stars(resp.json().get("stargazers_count"))
                except requests.RequestException:
                    cache[repo] = ""
            row["rating"] = cache[repo]
            time.sleep(0.1)


def _source_badges(row):
    badges = []
    if "official" in row["sources"]:
        badges.append(OFFICIAL_EMOJI)
    if "community" in row["sources"]:
        badges.append(COMMUNITY_EMOJI)
    return " ".join(badges)


def _format_app_cell(row):
    primary_url = row["repo_url"] or row["official_url"] or row["community_url"]
    if primary_url:
        return f"[{row['name']}]({primary_url})"
    return row["name"]


def _format_links(row):
    links = []
    seen = set()

    if row["official_url"]:
        links.append(f"[Official]({row['official_url']})")
        seen.add(row["official_url"])

    if row["repo_url"] and row["repo_url"] not in seen:
        links.append(f"[GitHub]({row['repo_url']})")
        seen.add(row["repo_url"])

    if row["community_url"] and row["community_url"] not in seen:
        links.append(f"[Community]({row['community_url']})")

    return " / ".join(links)


def _sorted_rows(section_rows):
    rows = list(section_rows.values())
    rows.sort(
        key=lambda row: (
            0 if row["author"].lower() == FEATURED_OWNER.lower() else 1,
            row["name"].lower(),
        )
    )
    return rows


def _append_table(lines, rows):
    lines.append("| Source | App | Description | Author | Rating | Links |")
    lines.append("|--------|-----|-------------|--------|--------|-------|")

    for row in rows:
        lines.append(
            f"| {_source_badges(row)} | {_format_app_cell(row)} | "
            f"{row['description']} | {row['author']} | {row['rating']} | {_format_links(row)} |"
        )
    lines.append("")


def generate_readme(categories, catalog_apps, awesome_sections, featured_repos):
    """Generate the full README.md content."""
    section_order, rows_by_section = _collect_rows(
        categories,
        catalog_apps,
        awesome_sections,
        featured_repos,
    )
    _fill_missing_ratings(rows_by_section)

    lines = []
    lines.append("# Flipper Zero Awesome Catalog")
    lines.append("")
    lines.append(
        "A curated, auto-updated collection of the best Flipper Zero apps, tools, games, "
        "and community resources in one place. This project combines the official app catalog "
        "with standout picks from the community, then organizes everything into a single index "
        "so it is easier to discover what is useful, maintained, and worth trying."
    )
    lines.append("")
    lines.append(
        f"`{OFFICIAL_EMOJI}` = Official Flipper App Catalog, "
        f"`{COMMUNITY_EMOJI}` = From awesome-flipperzero."
    )
    lines.append("")

    lines.append("## Table of Contents")
    lines.append("")
    for section_name in section_order:
        lines.append(f"- [{section_name}](#{_make_anchor(section_name)})")
    lines.append(f"- [Sources](#{_make_anchor('Sources')})")
    lines.append("")
    lines.append("---")
    lines.append("")

    for section_name in section_order:
        section_rows = rows_by_section.get(section_name, {})
        if not section_rows:
            continue

        lines.append(f"## {section_name}")
        lines.append("")

        grouped = {}
        for row in _sorted_rows(section_rows):
            grouped.setdefault(row["subsection"], []).append(row)

        if set(grouped) == {""}:
            _append_table(lines, grouped[""])
            continue

        for subsection_name, rows in grouped.items():
            if subsection_name:
                lines.append(f"### {subsection_name}")
                lines.append("")
            _append_table(lines, rows)

    lines.append("## Sources")
    lines.append("")
    lines.append(f"- Official: [Official Flipper App Catalog]({LAB_URL})")
    lines.append(
        "- Community: [awesome-flipperzero]"
        "(https://github.com/djsime1/awesome-flipperzero)"
    )
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(
        "*This catalog is auto-generated. "
        "Run `python scripts/update_catalog.py` to refresh the data.*"
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
