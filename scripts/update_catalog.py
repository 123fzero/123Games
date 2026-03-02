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
    """Stub."""
    return []

def generate_readme(categories, catalog_apps, awesome_sections, featured_repos):
    """Stub."""
    return "# 123 Games\n\nCatalog coming soon.\n"


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
